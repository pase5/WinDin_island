package com.windin.companion.network

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import com.windin.companion.model.ConnectionStatus
import com.windin.companion.model.ReceivedItem
import com.windin.companion.storage.MediaStoreSaver
import com.windin.companion.storage.SecurePrefs
import com.windin.companion.ui.MainActivity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.*
import okio.ByteString
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

class WinDinSocketService : Service() {

    companion object {
        const val ACTION_RECONNECT = "com.windin.companion.ACTION_RECONNECT"
        const val ACTION_PUSH_CLIPBOARD = "com.windin.companion.ACTION_PUSH_CLIPBOARD"
        const val EXTRA_TEXT = "extra_text"

        private val _status = MutableStateFlow<ConnectionStatus>(ConnectionStatus.Unpaired)
        val status: StateFlow<ConnectionStatus> = _status.asStateFlow()

        private val _recentItems = MutableStateFlow<List<ReceivedItem>>(emptyList())
        val recentItems: StateFlow<List<ReceivedItem>> = _recentItems.asStateFlow()

        fun startOrReconnect(context: Context) {
            val intent = Intent(context, WinDinSocketService::class.java).apply {
                action = ACTION_RECONNECT
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun pushClipboardText(context: Context, text: String) {
            val intent = Intent(context, WinDinSocketService::class.java).apply {
                action = ACTION_PUSH_CLIPBOARD
                putExtra(EXTRA_TEXT, text)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }
    }

    private lateinit var prefs: SecurePrefs
    private lateinit var mdns: MdnsResolver
    private val mainHandler = Handler(Looper.getMainLooper())
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .pingInterval(10, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private var webSocket: WebSocket? = null
    private var isConnecting = false

    private var activeTxId: String? = null
    private var activeFilename: String = ""
    private var activeMime: String = "application/octet-stream"
    private var activeTotalBytes: Long = 0L
    private var activeReceivedBytes: Long = 0L
    private var tempFile: File? = null
    private var tempOut: FileOutputStream? = null
    private var sha256: MessageDigest? = null

    override fun onCreate() {
        super.onCreate()
        prefs = SecurePrefs(this)
        createNotificationChannels()
        startForeground(101, buildStatusNotification("WinDin-Link: Initializing..."))

        mdns = MdnsResolver(this) { resolvedIp, resolvedPort ->
            val current = prefs.getPairing()
            if (current != null) {
                prefs.updateResolvedEndpoint(resolvedIp, resolvedPort)
                if (webSocket == null && !isConnecting) {
                    connectToHost(resolvedIp, resolvedPort)
                }
            }
        }
        mdns.start()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_PUSH_CLIPBOARD -> {
                val text = intent.getStringExtra(EXTRA_TEXT).orEmpty()
                if (text.isNotBlank()) {
                    val payload = JSONObject().apply {
                        put("type", "clipboard_push")
                        put("text", text)
                    }
                    webSocket?.send(payload.toString())
                }
            }
            else -> {
                val config = prefs.getPairing()
                if (config == null) {
                    _status.value = ConnectionStatus.Unpaired
                    updateStatusNotification("WinDin-Link: Tap to pair with PC")
                } else if (config.ip.isNotEmpty()) {
                    connectToHost(config.ip, config.port)
                }
            }
        }
        return START_STICKY
    }

    private fun connectToHost(ip: String, port: Int) {
        val config = prefs.getPairing() ?: return
        isConnecting = true
        _status.value = ConnectionStatus.Searching
        webSocket?.cancel()

        val request = Request.Builder().url("ws://$ip:$port/ws").build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                isConnecting = false
                val auth = JSONObject().apply {
                    put("type", "auth")
                    put("token", config.token)
                    put("device_id", config.deviceId)
                    put("device_name", Build.MODEL)
                }
                ws.send(auth.toString())
            }

            override fun onMessage(ws: WebSocket, text: String) {
                handleJsonControl(ws, JSONObject(text), ip)
            }

            override fun onMessage(ws: WebSocket, bytes: ByteString) {
                val data = bytes.toByteArray()
                tempOut?.write(data)
                sha256?.update(data)
                activeReceivedBytes += data.size
                _status.value = ConnectionStatus.Receiving(
                    filename = activeFilename,
                    bytesReceived = activeReceivedBytes,
                    totalBytes = activeTotalBytes
                )
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                isConnecting = false
                webSocket = null
                if (code == 4001) {
                    _status.value = ConnectionStatus.Error("PC rejected pairing — check QR or rescan")
                    updateStatusNotification("Pairing error — retrying connection...")
                    scheduleReconnect(delayMs = 5000L)
                } else {
                    scheduleReconnect(delayMs = 3000L)
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                isConnecting = false
                webSocket = null
                scheduleReconnect(delayMs = 3000L)
            }
        })
    }

    private fun scheduleReconnect(delayMs: Long = 3000L) {
        val config = prefs.getPairing() ?: return
        _status.value = ConnectionStatus.Searching
        updateStatusNotification("Searching for ${config.host}...")
        mainHandler.removeCallbacksAndMessages(null)
        mainHandler.postDelayed({
            val latest = prefs.getPairing()
            if (latest != null && webSocket == null && !isConnecting) {
                connectToHost(latest.ip, latest.port)
            }
        }, delayMs)
    }

    private fun handleJsonControl(ws: WebSocket, json: JSONObject, connectedIp: String) {
        when (json.optString("type")) {
            "auth_ok" -> {
                val host = json.optString("host", "WinDin PC")
                _status.value = ConnectionStatus.Connected(host, connectedIp)
                updateStatusNotification("Connected to $host")
            }
            "auth_error" -> {
                _status.value = ConnectionStatus.Error("Auth failed — retrying...")
                scheduleReconnect(delayMs = 5000L)
            }
            "file_offer" -> {
                activeTxId = json.getString("transfer_id")
                activeFilename = json.getString("filename")
                activeMime = json.optString("mime", "application/octet-stream")
                activeTotalBytes = json.optLong("size", 0L)
                activeReceivedBytes = 0L

                tempFile = File(cacheDir, activeTxId ?: "windin_tx")
                tempOut = FileOutputStream(tempFile)
                sha256 = MessageDigest.getInstance("SHA-256")
            }
            "file_end" -> {
                val expectedHash = json.getString("sha256")
                tempOut?.flush()
                tempOut?.close()
                tempOut = null

                val actualHash = sha256?.digest()?.joinToString("") { "%02x".format(it) }.orEmpty()
                val file = tempFile
                val savedUri: Uri? = if (file != null && actualHash.equals(expectedHash, ignoreCase = true)) {
                    MediaStoreSaver.saveToDevice(this, file, activeFilename, activeMime)
                } else {
                    null
                }
                file?.delete()

                val ack = JSONObject().apply {
                    put("type", "file_ack")
                    put("transfer_id", activeTxId)
                    put("status", if (savedUri != null) "saved" else "hash_mismatch")
                }
                ws.send(ack.toString())

                if (savedUri != null) {
                    val item = ReceivedItem(
                        id = activeTxId ?: System.currentTimeMillis().toString(),
                        filename = activeFilename,
                        mimeType = activeMime,
                        uri = savedUri
                    )
                    _recentItems.value = listOf(item) + _recentItems.value.take(19)
                    notifyFileSaved(activeFilename, activeMime, savedUri)
                }

                val cfg = prefs.getPairing()
                _status.value = if (cfg != null) {
                    ConnectionStatus.Connected(cfg.host, connectedIp)
                } else {
                    ConnectionStatus.Unpaired
                }
            }
        }
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(NotificationManager::class.java)
            mgr.createNotificationChannel(
                NotificationChannel("windin_status", "WinDin Background Link", NotificationManager.IMPORTANCE_LOW)
            )
            mgr.createNotificationChannel(
                NotificationChannel("windin_drops", "Received Files", NotificationManager.IMPORTANCE_DEFAULT)
            )
        }
    }

    private fun buildStatusNotification(text: String) =
        NotificationCompat.Builder(this, "windin_status")
            .setContentTitle("WinDin-Link")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .setOngoing(true)
            .setContentIntent(
                PendingIntent.getActivity(
                    this, 0, Intent(this, MainActivity::class.java),
                    PendingIntent.FLAG_IMMUTABLE
                )
            )
            .build()

    private fun updateStatusNotification(text: String) {
        val mgr = getSystemService(NotificationManager::class.java)
        mgr.notify(101, buildStatusNotification(text))
    }

    private fun notifyFileSaved(filename: String, mimeType: String, uri: Uri) {
        val viewIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mimeType)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        val pending = PendingIntent.getActivity(
            this, uri.hashCode(), viewIntent, PendingIntent.FLAG_IMMUTABLE
        )
        val notif = NotificationCompat.Builder(this, "windin_drops")
            .setContentTitle("Received from WinDin")
            .setContentText(filename)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        getSystemService(NotificationManager::class.java).notify(uri.hashCode(), notif)
    }

    override fun onDestroy() {
        mdns.stop()
        webSocket?.close(1000, "Service stopped")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
