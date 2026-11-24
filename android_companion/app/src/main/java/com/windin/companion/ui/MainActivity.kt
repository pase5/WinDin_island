package com.windin.companion.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.OpenableColumns
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
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
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

enum class NavigationTab(val label: String) {
    CONTINUITY("Continuity"),
    REMOTE("Remote Deck"),
    SYSTEM("System")
}

@Composable
fun MainDashboardScreen() {
    val context = LocalContext.current
    val status by WinDinSocketService.status.collectAsState()
    val recentItems by WinDinSocketService.recentItems.collectAsState()
    val uploadProgress by WinDinSocketService.uploadProgress.collectAsState()
    val uploadStatus by WinDinSocketService.uploadStatus.collectAsState()
    val batteryInfo by WinDinSocketService.phoneBattery.collectAsState()

    var currentTab by remember { mutableStateOf(NavigationTab.CONTINUITY) }
    var showScanner by remember { mutableStateOf(false) }

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
        },
        bottomBar = {
            NavigationBar(
                containerColor = WinDinCard,
                contentColor = WinDinTextPrimary,
                tonalElevation = 8.dp,
                modifier = Modifier.border(
                    width = 1.dp,
                    color = WinDinCardBorder,
                    shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp)
                )
            ) {
                NavigationBarItem(
                    selected = currentTab == NavigationTab.CONTINUITY,
                    onClick = { currentTab = NavigationTab.CONTINUITY },
                    icon = { Icon(Icons.Default.CloudSync, contentDescription = "Continuity") },
                    label = { Text("Continuity", fontSize = 11.sp, fontWeight = FontWeight.SemiBold) },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = Color.Black,
                        selectedTextColor = WinDinLime,
                        indicatorColor = WinDinLime,
                        unselectedIconColor = WinDinTextSecondary,
                        unselectedTextColor = WinDinTextSecondary
                    )
                )
                NavigationBarItem(
                    selected = currentTab == NavigationTab.REMOTE,
                    onClick = { currentTab = NavigationTab.REMOTE },
                    icon = { Icon(Icons.Default.Tune, contentDescription = "Remote Deck") },
                    label = { Text("Remote Deck", fontSize = 11.sp, fontWeight = FontWeight.SemiBold) },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = Color.Black,
                        selectedTextColor = WinDinLime,
                        indicatorColor = WinDinLime,
                        unselectedIconColor = WinDinTextSecondary,
                        unselectedTextColor = WinDinTextSecondary
                    )
                )
                NavigationBarItem(
                    selected = currentTab == NavigationTab.SYSTEM,
                    onClick = { currentTab = NavigationTab.SYSTEM },
                    icon = { Icon(Icons.Default.SettingsSuggest, contentDescription = "System") },
                    label = { Text("System", fontSize = 11.sp, fontWeight = FontWeight.SemiBold) },
                    colors = NavigationBarItemDefaults.colors(
                        selectedIconColor = Color.Black,
                        selectedTextColor = WinDinLime,
                        indicatorColor = WinDinLime,
                        unselectedIconColor = WinDinTextSecondary,
                        unselectedTextColor = WinDinTextSecondary
                    )
                )
            }
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when (currentTab) {
                NavigationTab.CONTINUITY -> ContinuityTab(
                    status = status,
                    recentItems = recentItems,
                    uploadProgress = uploadProgress,
                    uploadStatus = uploadStatus,
                    onOpenScanner = {
                        val hasCam = ContextCompat.checkSelfPermission(
                            context, Manifest.permission.CAMERA
                        ) == PackageManager.PERMISSION_GRANTED
                        if (hasCam) {
                            showScanner = true
                        } else {
                            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    }
                )
                NavigationTab.REMOTE -> RemoteDeckTab(status = status)
                NavigationTab.SYSTEM -> SystemDiagnosticsTab(
                    status = status,
                    batteryLevel = batteryInfo.first,
                    isCharging = batteryInfo.second,
                    onOpenScanner = {
                        val hasCam = ContextCompat.checkSelfPermission(
                            context, Manifest.permission.CAMERA
                        ) == PackageManager.PERMISSION_GRANTED
                        if (hasCam) {
                            showScanner = true
                        } else {
                            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    }
                )
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────
// 1. CONTINUITY TAB (File Drops & Universal Clipboard)
// ─────────────────────────────────────────────────────────────

@Composable
fun ContinuityTab(
    status: ConnectionStatus,
    recentItems: List<ReceivedItem>,
    uploadProgress: Float?,
    uploadStatus: String?,
    onOpenScanner: () -> Unit
) {
    val context = LocalContext.current
    var clipboardText by remember { mutableStateOf("") }
    val clipboardManager = LocalClipboardManager.current

    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            val (filename, mime) = resolveUriDetails(context, uri)
            WinDinSocketService.uploadFile(context, uri, filename, mime)
            Toast.makeText(context, "Streaming $filename to WinDin PC...", Toast.LENGTH_SHORT).show()
        }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Spacer(modifier = Modifier.height(6.dp)) }

        // Host Connection Banner
        item {
            val currentPairing = remember(status) { SecurePrefs(context).getPairing() }
            if (currentPairing != null) {
                Surface(
                    color = WinDinCard,
                    shape = RoundedCornerShape(14.dp),
                    border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                    modifier = Modifier.fillMaxWidth()
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
                            TextButton(onClick = { WinDinSocketService.startOrReconnect(context) }) {
                                Text("Retry", color = WinDinLime, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                            }
                        }
                    }
                }
            } else {
                Button(
                    onClick = onOpenScanner,
                    colors = ButtonDefaults.buttonColors(containerColor = WinDinLime),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.QrCodeScanner, contentDescription = "Scan", tint = Color.Black)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Scan WinDin QR on PC to Connect", color = Color.Black, fontWeight = FontWeight.Bold)
                }
            }
        }

        // Send File / Photo Card (Bi-directional AirDrop)
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column {
                            Text(
                                text = "Drop File or Photo to PC",
                                color = WinDinTextPrimary,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = "Streams instantly to WinDin Downloads folder",
                                color = WinDinTextSecondary,
                                fontSize = 12.sp
                            )
                        }
                        Box(
                            modifier = Modifier
                                .size(36.dp)
                                .background(WinDinBlack, RoundedCornerShape(10.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(Icons.Default.UploadFile, contentDescription = null, tint = WinDinLime, modifier = Modifier.size(20.dp))
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    if (uploadProgress != null) {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            LinearProgressIndicator(
                                progress = { uploadProgress },
                                color = WinDinLime,
                                trackColor = WinDinBlack,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(8.dp)
                                    .clip(RoundedCornerShape(4.dp))
                            )
                            Text(
                                text = uploadStatus.orEmpty(),
                                color = WinDinLime,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    } else {
                        Button(
                            onClick = { filePickerLauncher.launch("*/*") },
                            colors = ButtonDefaults.buttonColors(containerColor = WinDinLime),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth(),
                            enabled = status is ConnectionStatus.Connected
                        ) {
                            Icon(Icons.Default.AddPhotoAlternate, contentDescription = null, tint = Color.Black)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Select Photo or Document", color = Color.Black, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }

        // Push to PC Clipboard Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Universal Clipboard",
                            color = WinDinTextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        TextButton(
                            onClick = {
                                val text = clipboardManager.getText()?.text
                                if (!text.isNullOrBlank()) {
                                    clipboardText = text
                                }
                            }
                        ) {
                            Text("Paste from Phone", color = WinDinLime, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = clipboardText,
                            onValueChange = { clipboardText = it },
                            placeholder = { Text("Paste note, link, or snippet...", color = WinDinTextSecondary, fontSize = 13.sp) },
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
                            enabled = status is ConnectionStatus.Connected && clipboardText.isNotBlank(),
                            modifier = Modifier
                                .size(48.dp)
                                .background(if (clipboardText.isNotBlank()) WinDinLime else WinDinCardBorder, RoundedCornerShape(12.dp))
                        ) {
                            Icon(Icons.Default.Send, contentDescription = "Send", tint = Color.Black)
                        }
                    }
                }
            }
        }

        // Section Title: Gallery Drops Received
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Recent Drops from PC",
                    color = WinDinTextPrimary,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "${recentItems.size} items",
                    color = WinDinTextSecondary,
                    fontSize = 12.sp
                )
            }
        }

        if (recentItems.isEmpty()) {
            item {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(140.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.CloudDownload,
                            contentDescription = null,
                            tint = WinDinCardBorder,
                            modifier = Modifier.size(44.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "No files received yet",
                            color = WinDinTextSecondary,
                            fontSize = 13.sp
                        )
                        Text(
                            text = "Drag any file onto the WinDin pill on PC",
                            color = WinDinTextSecondary.copy(alpha = 0.6f),
                            fontSize = 11.sp
                        )
                    }
                }
            }
        } else {
            items(recentItems, key = { it.id }) { item ->
                ReceivedItemCard(item = item)
            }
        }

        item { Spacer(modifier = Modifier.height(20.dp)) }
    }
}

// ─────────────────────────────────────────────────────────────
// 2. REMOTE DECK TAB (PC Controls, Media Player & Island Edge)
// ─────────────────────────────────────────────────────────────

@Composable
fun RemoteDeckTab(status: ConnectionStatus) {
    val context = LocalContext.current
    val isConnected = status is ConnectionStatus.Connected

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Spacer(modifier = Modifier.height(6.dp)) }

        // Media Player Controller Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "PC Media Player",
                        color = WinDinTextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Control Windows System Media Transport",
                        color = WinDinTextSecondary,
                        fontSize = 12.sp
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        IconButton(
                            onClick = { WinDinSocketService.sendPcAction(context, "prev") },
                            enabled = isConnected,
                            modifier = Modifier.size(48.dp).background(WinDinBlack, CircleShape)
                        ) {
                            Icon(Icons.Default.SkipPrevious, contentDescription = "Prev", tint = WinDinTextPrimary)
                        }

                        IconButton(
                            onClick = { WinDinSocketService.sendPcAction(context, "play_pause") },
                            enabled = isConnected,
                            modifier = Modifier.size(60.dp).background(WinDinLime, CircleShape)
                        ) {
                            Icon(Icons.Default.PlayArrow, contentDescription = "Play/Pause", tint = Color.Black, modifier = Modifier.size(32.dp))
                        }

                        IconButton(
                            onClick = { WinDinSocketService.sendPcAction(context, "next") },
                            enabled = isConnected,
                            modifier = Modifier.size(48.dp).background(WinDinBlack, CircleShape)
                        ) {
                            Icon(Icons.Default.SkipNext, contentDescription = "Next", tint = WinDinTextPrimary)
                        }
                    }
                }
            }
        }

        // PC System Control Actions Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "PC Quick Controls",
                        color = WinDinTextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Trigger Windows hardware and security actions",
                        color = WinDinTextSecondary,
                        fontSize = 12.sp
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        RemoteActionButton(
                            icon = Icons.Default.Lock,
                            label = "Lock PC",
                            enabled = isConnected,
                            modifier = Modifier.weight(1f)
                        ) {
                            WinDinSocketService.sendPcAction(context, "lock_pc")
                            Toast.makeText(context, "PC Locked", Toast.LENGTH_SHORT).show()
                        }

                        RemoteActionButton(
                            icon = Icons.Default.PhotoCamera,
                            label = "Screenshot",
                            enabled = isConnected,
                            modifier = Modifier.weight(1f)
                        ) {
                            WinDinSocketService.sendPcAction(context, "screenshot")
                            Toast.makeText(context, "Screenshot captured on PC", Toast.LENGTH_SHORT).show()
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        RemoteActionButton(
                            icon = Icons.Default.VolumeMute,
                            label = "Mute / Unmute",
                            enabled = isConnected,
                            modifier = Modifier.weight(1f)
                        ) {
                            WinDinSocketService.sendPcAction(context, "toggle_mute")
                        }

                        RemoteActionButton(
                            icon = Icons.Default.VerticalAlignTop,
                            label = "Toggle Island",
                            enabled = isConnected,
                            modifier = Modifier.weight(1f)
                        ) {
                            WinDinSocketService.sendPcAction(context, "toggle_island")
                        }
                    }
                }
            }
        }

        // Dynamic Island Dock Position Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Island Dock Edge",
                        color = WinDinTextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Reposition the Dynamic Island on your desktop",
                        color = WinDinTextSecondary,
                        fontSize = 12.sp
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        listOf("top" to "Top", "bottom" to "Bottom", "left" to "Left", "right" to "Right", "floating" to "Floating").forEach { (edge, name) ->
                            OutlinedButton(
                                onClick = {
                                    WinDinSocketService.sendPcAction(context, "dock_edge", edge)
                                    Toast.makeText(context, "Docked to $name", Toast.LENGTH_SHORT).show()
                                },
                                enabled = isConnected,
                                shape = RoundedCornerShape(10.dp),
                                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                                modifier = Modifier.weight(1f),
                                contentPadding = PaddingValues(horizontal = 2.dp, vertical = 6.dp)
                            ) {
                                Text(name, fontSize = 11.sp, color = WinDinTextPrimary, maxLines = 1)
                            }
                        }
                    }
                }
            }
        }

        // Quick Notification Simulator Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Send Toast to Island",
                        color = WinDinTextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Test notification rendering with live brand icons",
                        color = WinDinTextSecondary,
                        fontSize = 12.sp
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                WinDinSocketService.sendNotification(context, "WhatsApp", "Alex", "Meeting in 5 minutes on Teams!")
                            },
                            enabled = isConnected,
                            shape = RoundedCornerShape(10.dp),
                            border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("WhatsApp", fontSize = 11.sp, color = WinDinTextPrimary)
                        }

                        OutlinedButton(
                            onClick = {
                                WinDinSocketService.sendNotification(context, "Messages", "Verification Code", "Your 2FA security code is: 482 910")
                            },
                            enabled = isConnected,
                            shape = RoundedCornerShape(10.dp),
                            border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("2FA OTP", fontSize = 11.sp, color = WinDinTextPrimary)
                        }

                        OutlinedButton(
                            onClick = {
                                WinDinSocketService.sendNotification(context, "Phone", "Mom", "Incoming Call • Mobile")
                            },
                            enabled = isConnected,
                            shape = RoundedCornerShape(10.dp),
                            border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                            modifier = Modifier.weight(1f)
                        ) {
                            Text("Call", fontSize = 11.sp, color = WinDinTextPrimary)
                        }
                    }
                }
            }
        }

        item { Spacer(modifier = Modifier.height(20.dp)) }
    }
}

@Composable
fun RemoteActionButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Surface(
        color = WinDinBlack,
        shape = RoundedCornerShape(12.dp),
        border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
        modifier = modifier
            .height(56.dp)
            .clickable(enabled = enabled, onClick = onClick)
    ) {
        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Icon(icon, contentDescription = label, tint = if (enabled) WinDinLime else WinDinTextSecondary, modifier = Modifier.size(20.dp))
            Text(label, color = if (enabled) WinDinTextPrimary else WinDinTextSecondary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

// ─────────────────────────────────────────────────────────────
// 3. SYSTEM & DIAGNOSTICS TAB
// ─────────────────────────────────────────────────────────────

@Composable
fun SystemDiagnosticsTab(
    status: ConnectionStatus,
    batteryLevel: Int,
    isCharging: Boolean,
    onOpenScanner: () -> Unit
) {
    val context = LocalContext.current
    val currentPairing = remember(status) { SecurePrefs(context).getPairing() }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Spacer(modifier = Modifier.height(6.dp)) }

        // Live Battery Sync Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .background(WinDinBlack, RoundedCornerShape(12.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = if (isCharging) Icons.Default.BatteryChargingFull else Icons.Default.BatteryStd,
                            contentDescription = null,
                            tint = WinDinLime,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Battery Sync: $batteryLevel%",
                            color = WinDinTextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = if (isCharging) "Charging • Synced to Dynamic Island" else "On Battery • Synced to Dynamic Island",
                            color = WinDinTextSecondary,
                            fontSize = 12.sp
                        )
                    }
                }
            }
        }

        // Connection Diagnostics Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Continuity Bridge Diagnostics",
                        color = WinDinTextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    DiagnosticRow("Status", when (status) {
                        is ConnectionStatus.Connected -> "Active • WebSocket Connected"
                        is ConnectionStatus.Searching -> "Searching on Wi-Fi..."
                        is ConnectionStatus.Error -> "Connection Error"
                        is ConnectionStatus.Receiving -> "Transferring"
                        is ConnectionStatus.Unpaired -> "Unpaired"
                    })
                    DiagnosticRow("Desktop Host", currentPairing?.host ?: "Not configured")
                    DiagnosticRow("Endpoint IP", currentPairing?.ip ?: "—")
                    DiagnosticRow("Port", currentPairing?.port?.toString() ?: "8765")
                    DiagnosticRow("Device Identity", Build.MODEL)
                }
            }
        }

        // Pairing & Lifecycle Controls
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Button(
                    onClick = onOpenScanner,
                    colors = ButtonDefaults.buttonColors(containerColor = WinDinLime),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Default.QrCodeScanner, contentDescription = null, tint = Color.Black)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Re-pair QR", color = Color.Black, fontWeight = FontWeight.Bold)
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
        }

        // About Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = WinDinCard),
                shape = RoundedCornerShape(18.dp),
                border = ButtonDefaults.outlinedButtonBorder.copy(brush = androidx.compose.ui.graphics.SolidColor(WinDinCardBorder)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "WindowLand Dynamic Island",
                        color = WinDinTextPrimary,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Apple-grade hardware notch continuity bridge for Windows 11 & Android. Version 2.0.0",
                        color = WinDinTextSecondary,
                        fontSize = 12.sp,
                        lineHeight = 16.sp
                    )
                }
            }
        }

        item { Spacer(modifier = Modifier.height(20.dp)) }
    }
}

@Composable
fun DiagnosticRow(title: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(title, color = WinDinTextSecondary, fontSize = 12.sp)
        Text(value, color = WinDinTextPrimary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
    }
}

// ─────────────────────────────────────────────────────────────
// SHARED COMPONENTS & UTILITIES
// ─────────────────────────────────────────────────────────────

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
            .padding(top = 10.dp, bottom = 4.dp),
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
                try {
                    val intent = Intent(Intent.ACTION_VIEW).apply {
                        setDataAndType(item.uri, item.mimeType)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    context.startActivity(intent)
                } catch (e: Exception) {
                    Toast.makeText(context, "No app available to open this file", Toast.LENGTH_SHORT).show()
                }
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

fun resolveUriDetails(context: Context, uri: Uri): Pair<String, String> {
    var name = "uploaded_file"
    val mime = context.contentResolver.getType(uri) ?: "application/octet-stream"

    context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
        if (cursor.moveToFirst()) {
            val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (nameIndex != -1) {
                name = cursor.getString(nameIndex) ?: name
            }
        }
    }
    return Pair(name, mime)
}
