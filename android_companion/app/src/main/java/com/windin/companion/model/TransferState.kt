package com.windin.companion.model

import android.net.Uri

sealed interface ConnectionStatus {
    data object Unpaired : ConnectionStatus
    data object Searching : ConnectionStatus
    data class Connected(val hostName: String, val ip: String) : ConnectionStatus
    data class Receiving(val filename: String, val bytesReceived: Long, val totalBytes: Long) : ConnectionStatus
    data class Error(val message: String) : ConnectionStatus
}

data class ReceivedItem(
    val id: String,
    val filename: String,
    val mimeType: String,
    val uri: Uri,
    val timestamp: Long = System.currentTimeMillis()
)
