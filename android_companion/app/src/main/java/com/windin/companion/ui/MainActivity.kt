package com.windin.companion.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.windin.companion.model.ConnectionStatus
import com.windin.companion.model.ReceivedItem
import com.windin.companion.network.WinDinSocketService
import com.windin.companion.storage.SecurePrefs
import java.text.SimpleDateFormat
import java.util.*

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Request notification permission on Android 13+
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1001)
            }
        }

        // Boot or reconnect background continuity service
        WinDinSocketService.startOrReconnect(this)

        setContent {
            WinDinTheme {
                MainDashboardScreen()
            }
        }
    }
}

@Composable
fun MainDashboardScreen() {
    val context = LocalContext.current
    val status by WinDinSocketService.status.collectAsState()
    val recentItems by WinDinSocketService.recentItems.collectAsState()

    var showScanner by remember { mutableStateOf(false) }
    var clipboardText by remember { mutableStateOf("") }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            showScanner = true
        } else {
            Toast.makeText(context, "Camera permission needed to scan QR", Toast.LENGTH_SHORT).show()
        }
    }

    if (showScanner) {
        QrScannerScreen(
            onDismiss = { showScanner = false },
            onScanSuccess = {
                showScanner = false
                Toast.makeText(context, "Paired successfully with WinDin!", Toast.LENGTH_SHORT).show()
            }
        )
        return
    }

    Scaffold(
        containerColor = WinDinBlack,
        topBar = {
            TopAppBarIsland(status = status)
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp)
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            val currentPairing = remember(status) { SecurePrefs(context).getPairing() }
            if (currentPairing != null) {
                Surface(
                    color = WinDinCard,
                    shape = RoundedCornerShape(14.dp),
                    border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column {
                            Text(
                                text = "Paired PC: ${currentPairing.host}",
                                color = WinDinTextPrimary,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold
                            )
                            Text(
                                text = "Target: ${currentPairing.ip}:${currentPairing.port}",
                                color = WinDinTextSecondary,
                                fontSize = 11.sp
                            )
                        }
                        if (status !is ConnectionStatus.Connected) {
                            TextButton(
                                onClick = { WinDinSocketService.startOrReconnect(context) }
                            ) {
                                Text("Retry", color = WinDinLime, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                            }
                        }
                    }
                }
            }

            // Action Buttons Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Button(
                    onClick = {
                        val hasCam = ContextCompat.checkSelfPermission(
                            context, Manifest.permission.CAMERA
                        ) == PackageManager.PERMISSION_GRANTED
                        if (hasCam) {
                            showScanner = true
                        } else {
                            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = WinDinLime),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(
                        imageVector = Icons.Default.QrCodeScanner,
                        contentDescription = "Scan",
                        tint = Color.Black
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Pair New PC", color = Color.Black, fontWeight = FontWeight.Bold)
                }

                OutlinedButton(
                    onClick = {
                        SecurePrefs(context).clearPairing()
                        WinDinSocketService.startOrReconnect(context)
                        Toast.makeText(context, "Pairing cleared", Toast.LENGTH_SHORT).show()
                    },
                    shape = RoundedCornerShape(14.dp),
                    border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = WinDinTextSecondary)
                ) {
                    Text("Unpair")
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Push to PC Clipboard Box
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Push Text or Link to PC",
                        color = WinDinTextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = clipboardText,
                            onValueChange = { clipboardText = it },
                            placeholder = { Text("Paste note, URL, or code snippet...", color = WinDinTextSecondary, fontSize = 13.sp) },
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = WinDinLime,
                                unfocusedBorderColor = WinDinCardBorder,
                                focusedTextColor = Color.White,
                                unfocusedTextColor = Color.White
                            ),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.weight(1f)
                        )
                        IconButton(
                            onClick = {
                                if (clipboardText.isNotBlank()) {
                                    WinDinSocketService.pushClipboardText(context, clipboardText)
                                    Toast.makeText(context, "Pushed to WinDin clipboard!", Toast.LENGTH_SHORT).show()
                                    clipboardText = ""
                                }
                            },
                            modifier = Modifier
                                .size(48.dp)
                                .background(WinDinLime, RoundedCornerShape(12.dp))
                        ) {
                            Icon(
                                imageVector = Icons.Default.Send,
                                contentDescription = "Send",
                                tint = Color.Black
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Recent Drops Section Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Recent Gallery Drops",
                    color = WinDinTextPrimary,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "${recentItems.size} items",
                    color = WinDinTextSecondary,
                    fontSize = 12.sp
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (recentItems.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.CloudDownload,
                            contentDescription = null,
                            tint = WinDinCardBorder,
                            modifier = Modifier.size(54.dp)
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "No files received yet",
                            color = WinDinTextSecondary,
                            fontSize = 14.sp
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Drag any file onto the WinDin pill on PC",
                            color = WinDinTextSecondary.copy(alpha = 0.6f),
                            fontSize = 12.sp
                        )
                    }
                }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    items(recentItems, key = { it.id }) { item ->
                        ReceivedItemCard(item = item)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Composable
fun TopAppBarIsland(status: ConnectionStatus) {
    val (statusText, dotColor) = when (status) {
        is ConnectionStatus.Connected -> "Connected • ${status.hostName}" to WinDinLime
        is ConnectionStatus.Receiving -> {
            val pct = if (status.totalBytes > 0) (status.bytesReceived * 100 / status.totalBytes) else 0
            "Receiving ${status.filename} (${pct}%)" to WinDinLime
        }
        is ConnectionStatus.Searching -> "Searching for PC..." to Color(0xFFFBBF24)
        is ConnectionStatus.Error -> status.message to WinDinRed
        is ConnectionStatus.Unpaired -> "Tap to pair with PC" to Color.Gray
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(top = 12.dp, bottom = 4.dp),
        contentAlignment = Alignment.Center
    ) {
        Surface(
            color = WinDinCard,
            shape = RoundedCornerShape(24.dp),
            border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
            modifier = Modifier.padding(horizontal = 24.dp)
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(dotColor)
                )
                Text(
                    text = statusText,
                    color = WinDinTextPrimary,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
fun ReceivedItemCard(item: ReceivedItem) {
    val context = LocalContext.current
    val timeStr = remember(item.timestamp) {
        SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date(item.timestamp))
    }

    Card(
        colors = CardDefaults.cardColors(containerColor = WinDinCard),
        shape = RoundedCornerShape(16.dp),
        border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
        modifier = Modifier
            .fillMaxWidth()
            .clickable {
                val intent = Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(item.uri, item.mimeType)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(intent)
            }
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            val icon = if (item.mimeType.startsWith("image/")) {
                Icons.Default.Image
            } else {
                Icons.Default.InsertDriveFile
            }

            Box(
                modifier = Modifier
                    .size(42.dp)
                    .background(WinDinBlack, RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = WinDinLime,
                    modifier = Modifier.size(24.dp)
                )
            }

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = item.filename,
                    color = WinDinTextPrimary,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = "Saved to Gallery / Downloads • $timeStr",
                    color = WinDinTextSecondary,
                    fontSize = 11.sp
                )
            }

            Icon(
                imageVector = Icons.Default.OpenInNew,
                contentDescription = "Open",
                tint = WinDinTextSecondary,
                modifier = Modifier.size(18.dp)
            )
        }
    }
}
