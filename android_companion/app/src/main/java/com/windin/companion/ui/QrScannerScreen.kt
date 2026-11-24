package com.windin.companion.ui

import android.annotation.SuppressLint
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.windin.companion.network.WinDinSocketService
import com.windin.companion.storage.SecurePrefs
import org.json.JSONObject
import java.util.concurrent.Executors

@Composable
fun QrScannerScreen(
    onDismiss: () -> Unit,
    onScanSuccess: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var hasProcessed by remember { mutableStateOf(false) }
    var scanError by remember { mutableStateOf<String?>(null) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(WinDinBlack)
    ) {
        AndroidView(
            factory = { ctx ->
                val previewView = PreviewView(ctx)
                val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                val executor = Executors.newSingleThreadExecutor()

                cameraProviderFuture.addListener({
                    val cameraProvider = cameraProviderFuture.get()
                    val preview = Preview.Builder().build().also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }

                    val scanner = BarcodeScanning.getClient()
                    val analysis = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()

                    analysis.setAnalyzer(executor) { imageProxy ->
                        processImageProxy(
                            scanner = scanner,
                            imageProxy = imageProxy,
                            onResult = { rawData ->
                                if (!hasProcessed) {
                                    val trimmed = rawData.trim()
                                    var host = "WinDin PC"
                                    var ip = ""
                                    var port = 8765
                                    var service = "_windin._tcp.local."
                                    var token: String? = null

                                    try {
                                        if (trimmed.startsWith("{")) {
                                            val json = JSONObject(trimmed)
                                            token = json.optString("token").takeIf { it.isNotEmpty() }
                                            host = json.optString("host", "WinDin PC")
                                            ip = json.optString("ip", "")
                                            port = json.optInt("port", 8765)
                                            service = json.optString("service", "_windin._tcp.local.")
                                        } else if (trimmed.startsWith("http://", ignoreCase = true) ||
                                                   trimmed.startsWith("https://", ignoreCase = true) ||
                                                   trimmed.startsWith("ws://", ignoreCase = true) ||
                                                   trimmed.startsWith("wss://", ignoreCase = true)) {
                                            val uri = android.net.Uri.parse(trimmed)
                                            ip = uri.host.orEmpty()
                                            port = if (uri.port != -1) uri.port else 8765
                                            token = uri.getQueryParameter("token")
                                        }

                                        if (!token.isNullOrEmpty()) {
                                            hasProcessed = true
                                            val prefs = SecurePrefs(ctx)
                                            prefs.savePairing(host, ip, port, service, token)
                                            WinDinSocketService.startOrReconnect(ctx)

                                            ContextCompat.getMainExecutor(ctx).execute {
                                                onScanSuccess()
                                            }
                                        } else {
                                            scanError = "QR did not contain a valid WinDin token"
                                        }
                                    } catch (e: Exception) {
                                        scanError = "Failed to parse QR code: ${e.message}"
                                    }
                                }
                            }
                        )
                    }

                    try {
                        cameraProvider.unbindAll()
                        cameraProvider.bindToLifecycle(
                            lifecycleOwner,
                            CameraSelector.DEFAULT_BACK_CAMERA,
                            preview,
                            analysis
                        )
                    } catch (e: Exception) {
                        scanError = "Failed to open camera: ${e.message}"
                    }
                }, ContextCompat.getMainExecutor(ctx))

                previewView
            },
            modifier = Modifier.fillMaxSize()
        )

        // Overlay with scanner frame
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            Box(
                modifier = Modifier
                    .size(260.dp)
                    .border(2.5.dp, WinDinLime, RoundedCornerShape(20.dp))
            )
        }

        // Top bar with close button
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Scan WinDin QR",
                color = Color.White,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
            IconButton(
                onClick = onDismiss,
                modifier = Modifier.background(WinDinCard.copy(alpha = 0.8f), RoundedCornerShape(12.dp))
            ) {
                Icon(
                    imageVector = Icons.Default.Close,
                    contentDescription = "Close",
                    tint = Color.White
                )
            }
        }

        if (scanError != null) {
            Surface(
                color = WinDinRed.copy(alpha = 0.9f),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 60.dp)
                    .padding(horizontal = 24.dp)
            ) {
                Text(
                    text = scanError!!,
                    color = Color.White,
                    modifier = Modifier.padding(12.dp)
                )
            }
        }
    }
}

@SuppressLint("UnsafeOptInUsageError")
private fun processImageProxy(
    scanner: com.google.mlkit.vision.barcode.BarcodeScanner,
    imageProxy: ImageProxy,
    onResult: (String) -> Unit
) {
    val mediaImage = imageProxy.image
    if (mediaImage != null) {
        val image = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
        scanner.process(image)
            .addOnSuccessListener { barcodes ->
                for (barcode in barcodes) {
                    val rawValue = barcode.rawValue
                    if (!rawValue.isNullOrBlank()) {
                        onResult(rawValue)
                        break
                    }
                }
            }
            .addOnCompleteListener {
                imageProxy.close()
            }
    } else {
        imageProxy.close()
    }
}
