package com.windin.companion.network

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.OpenableColumns
import android.widget.Toast
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
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.TimeUnit

class WinDinSocketService : Service() {

    companion object {
        const val ACTION_RECONNECT = "com.windin.companion.ACTION_RECONNECT"
        const val ACTION_PUSH_CLIPBOARD = "com.windin.companion.ACTION_PUSH_CLIPBOARD"
        const val ACTION_UPLOAD_FILE = "com.windin.companion.ACTION_UPLOAD_FILE"
        const val ACTION_SEND_ACTION = "com.windin.companion.ACTION_SEND_ACTION"
        const val ACTION_SEND_NOTIFICATION = "com.windin.companion.ACTION_SEND_NOTIFICATION"
        const val ACTION_BATTERY_SYNC = "com.windin.companion.ACTION_BATTERY_SYNC"

        const val EXTRA_TEXT = "extra_text"
        const val EXTRA_URI = "extra_uri"
        const val EXTRA_FILENAME = "extra_filename"
        const val EXTRA_MIME = "extra_mime"
        const val EXTRA_ACTION = "extra_action"
        const val EXTRA_PARAM = "extra_param"
        const val EXTRA_APP = "extra_app"
        const val EXTRA_TITLE = "extra_title"
        const val EXTRA_MESSAGE = "extra_message"

        private val _status = MutableStateFlow<ConnectionStatus>(ConnectionStatus.Unpaired)
        val status: StateFlow<ConnectionStatus> = _status.asStateFlow()

        private val _recentItems = MutableStateFlow<List<ReceivedItem>>(emptyList())
        val recentItems: StateFlow<List<ReceivedItem>> = _recentItems.asStateFlow()

        private val _uploadProgress = MutableStateFlow<Float?>(null)
        val uploadProgress: StateFlow<Float?> = _uploadProgress.asStateFlow()

        private val _uploadStatus = MutableStateFlow<String?>(null)
        val uploadStatus: StateFlow<String?> = _uploadStatus.asStateFlow()

        private val _phoneBattery = MutableStateFlow<Pair<Int, Boolean>>(Pair(100, false))
        val phoneBattery: StateFlow<Pair<Int, Boolean>> = _phoneBattery.asStateFlow()

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

        fun uploadFile(context: Context, uri: Uri, filename: String, mimeType: String) {
            val intent = Intent(context, WinDinSocketService::class.java).apply {
                action = ACTION_UPLOAD_FILE
                putExtra(EXTRA_URI, uri.toString())
                putExtra(EXTRA_FILENAME, filename)
                putExtra(EXTRA_MIME, mimeType)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun sendPcAction(context: Context, pcAction: String, param: String = "") {
            val intent = Intent(context, WinDinSocketService::class.java).apply {
                this.action = ACTION_SEND_ACTION
                putExtra(EXTRA_ACTION, pcAction)
                putExtra(EXTRA_PARAM, param)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun sendNotification(context: Context, app: String, title: String, message: String) {
            val intent = Intent(context, WinDinSocketService::class.java).apply {
                action = ACTION_SEND_NOTIFICATION
                putExtra(EXTRA_APP, app)
                putExtra(EXTRA_TITLE, title)
                putExtra(EXTRA_MESSAGE, message)
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
        .writeTimeout(15, TimeUnit.SECONDS)
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

    private var lastReportedBattery: Int = -1
    private var lastReportedCharging: Boolean = false

    private val batteryReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == Intent.ACTION_BATTERY_CHANGED) {
                val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
                val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                val isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                        status == BatteryManager.BATTERY_STATUS_FULL
                val batteryPct = if (level >= 0 && scale > 0) (level * 100 / scale) else level
                _phoneBattery.value = Pair(batteryPct, isCharging)

                // Only send update if level or charging state actually changed
                if (batteryPct >= 0 && webSocket != null &&
                    (batteryPct != lastReportedBattery || isCharging != lastReportedCharging)) {
                    lastReportedBattery = batteryPct
                    lastReportedCharging = isCharging
                    val payload = JSONObject().apply {
                        put("type", "battery_sync")
                        put("level", batteryPct)
                        put("charging", isCharging)
                        put("device_name", Build.MODEL)
                    }
                    webSocket?.send(payload.toString())
                }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        prefs = SecurePrefs(this)
        createNotificationChannels()
        startForeground(101, buildStatusNotification("WinDin-Link: Initializing..."))

        try {
            val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            registerReceiver(batteryReceiver, filter)
        } catch (e: Exception) {
            // Ignored
        }

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
            ACTION_UPLOAD_FILE -> {
                val uriStr = intent.getStringExtra(EXTRA_URI)
                val filename = intent.getStringExtra(EXTRA_FILENAME) ?: "uploaded_file"
                val mime = intent.getStringExtra(EXTRA_MIME) ?: "application/octet-stream"
                if (!uriStr.isNullOrBlank()) {
                    performFileUpload(Uri.parse(uriStr), filename, mime)
                }
            }
            ACTION_SEND_ACTION -> {
                val actionName = intent.getStringExtra(EXTRA_ACTION).orEmpty()
                val param = intent.getStringExtra(EXTRA_PARAM).orEmpty()
                if (actionName.isNotBlank()) {
                    val payload = JSONObject().apply {
                        put("type", "pc_action")
                        put("action", actionName)
                        put("param", param)
                    }
                    webSocket?.send(payload.toString())
                }
            }
            ACTION_SEND_NOTIFICATION -> {
                val app = intent.getStringExtra(EXTRA_APP).orEmpty()
                val title = intent.getStringExtra(EXTRA_TITLE).orEmpty()
                val message = intent.getStringExtra(EXTRA_MESSAGE).orEmpty()
                val payload = JSONObject().apply {
                    put("type", "notification_push")
                    put("app", app)
                    put("title", title)
                    put("message", message)
                }
                webSocket?.send(payload.toString())
            }
            else -> {
                val config = prefs.getPairing()
                if (config == null) {
                    _status.value = ConnectionStatus.Unpaired
                    updateStatusNotification("WinDin-Link: Tap to pair with PC")
                } else if (config.ip.isNotEmpty() && webSocket == null && !isConnecting) {
                    connectToHost(config.ip, config.port)
                }
            }
        }
        return START_STICKY
    }

    private fun performFileUpload(uri: Uri, filename: String, mime: String) {
        Thread {
            try {
                _uploadStatus.value = "Preparing $filename..."
                _uploadProgress.value = 0.01f

                val pfd = contentResolver.openFileDescriptor(uri, "r")
                val fileSize = pfd?.statSize ?: 0L
                pfd?.close()

                val txId = "tx_" + UUID.randomUUID().toString().replace("-", "").substring(0, 8)
                val offer = JSONObject().apply {
                    put("type", "phone_file_offer")
                    put("transfer_id", txId)
                    put("filename", filename)
                    put("mime", mime)
                    put("size", fileSize)
                }
                webSocket?.send(offer.toString())

                contentResolver.openInputStream(uri)?.use { stream ->
                    val buffer = ByteArray(64 * 1024)
                    val digest = MessageDigest.getInstance("SHA-256")
                    var totalSent = 0L

                    while (true) {
                        val bytesRead = stream.read(buffer)
                        if (bytesRead <= 0) break
                        digest.update(buffer, 0, bytesRead)
                        val chunk = buffer.toByteString(0, bytesRead)
                        webSocket?.send(chunk)
                        totalSent += bytesRead

                        if (fileSize > 0) {
                            _uploadProgress.value = (totalSent.toFloat() / fileSize).coerceIn(0.02f, 0.99f)
                            _uploadStatus.value = "Streaming $filename (${(totalSent * 100 / fileSize)}%)..."
                        }
                    }

                    val hashStr = digest.digest().joinToString("") { "%02x".format(it) }
                    val endMsg = JSONObject().apply {
                        put("type", "phone_file_end")
                        put("transfer_id", txId)
                        put("sha256", hashStr)
                    }
                    webSocket?.send(endMsg.toString())
                    _uploadProgress.value = 0.99f
                    _uploadStatus.value = "Verifying with PC..."
                } ?: run {
                    _uploadStatus.value = "Failed to read file"
                    mainHandler.postDelayed({ _uploadProgress.value = null; _uploadStatus.value = null }, 2000)
                }
            } catch (e: Exception) {
                _uploadStatus.value = "Upload error: ${e.localizedMessage}"
                mainHandler.postDelayed({ _uploadProgress.value = null; _uploadStatus.value = null }, 3000)
            }
        }.start()
    }

    private fun connectToHost(ip: String, port: Int) {
        val config = prefs.getPairing() ?: return
        if (webSocket != null && !isConnecting) {
            return
        }
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

                // Sync current battery status
                val batt = _phoneBattery.value
                lastReportedBattery = batt.first
                lastReportedCharging = batt.second
                val payload = JSONObject().apply {
                    put("type", "battery_sync")
                    put("level", batt.first)
                    put("charging", batt.second)
                    put("device_name", Build.MODEL)
                }
                ws.send(payload.toString())
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
            "phone_file_ack" -> {
                val status = json.optString("status")
                if (status == "saved") {
                    _uploadProgress.value = 1.0f
                    _uploadStatus.value = "Sent to PC successfully!"
                    mainHandler.post {
                        Toast.makeText(this@WinDinSocketService, "File saved on WinDin PC!", Toast.LENGTH_SHORT).show()
                    }
                } else {
                    _uploadStatus.value = "Transfer integrity failed"
                }
                mainHandler.postDelayed({
                    _uploadProgress.value = null
                    _uploadStatus.value = null
                }, 2200)
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
        try {
            unregisterReceiver(batteryReceiver)
        } catch (e: Exception) {
            // Ignored
        }
        mdns.stop()
        webSocket?.close(1000, "Service stopped")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
