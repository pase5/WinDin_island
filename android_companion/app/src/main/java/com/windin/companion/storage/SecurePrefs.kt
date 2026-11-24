package com.windin.companion.storage

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.util.UUID

data class PairingConfig(
    val host: String,
    val ip: String,
    val port: Int,
    val service: String,
    val token: String,
    val deviceId: String
)

class SecurePrefs(context: Context) {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "windin_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    fun savePairing(host: String, ip: String, port: Int, service: String, token: String) {
        val deviceId = prefs.getString("device_id", null) ?: UUID.randomUUID().toString()
        prefs.edit()
            .putString("host", host)
            .putString("ip", ip)
            .putInt("port", port)
            .putString("service", service)
            .putString("token", token)
            .putString("device_id", deviceId)
            .apply()
    }

    fun updateResolvedEndpoint(ip: String, port: Int) {
        prefs.edit().putString("ip", ip).putInt("port", port).apply()
    }

    fun getPairing(): PairingConfig? {
        val token = prefs.getString("token", null) ?: return null
        return PairingConfig(
            host = prefs.getString("host", "WinDin PC") ?: "WinDin PC",
            ip = prefs.getString("ip", "") ?: "",
            port = prefs.getInt("port", 8765),
            service = prefs.getString("service", "_windin._tcp.local.") ?: "_windin._tcp.local.",
            token = token,
            deviceId = prefs.getString("device_id", UUID.randomUUID().toString())!!
        )
    }

    fun clearPairing() {
        prefs.edit().clear().apply()
    }
}
