package com.windin.companion.network

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager

class MdnsResolver(
    context: Context,
    private val onResolved: (ip: String, port: Int) -> Unit
) {
    private val nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private var multicastLock: WifiManager.MulticastLock? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var isDiscovering = false

    fun start() {
        if (isDiscovering) return
        multicastLock = wifiManager.createMulticastLock("windin_mdns_lock").apply {
            setReferenceCounted(true)
            acquire()
        }

        discoveryListener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(regType: String) { isDiscovering = true }
            override fun onServiceFound(service: NsdServiceInfo) {
                if (service.serviceType.contains("_windin._tcp")) {
                    @Suppress("DEPRECATION")
                    nsdManager.resolveService(service, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {}
                        override fun onServiceResolved(info: NsdServiceInfo) {
                            @Suppress("DEPRECATION")
                            val ip = info.host?.hostAddress ?: return
                            onResolved(ip, info.port)
                        }
                    })
                }
            }
            override fun onServiceLost(service: NsdServiceInfo) {}
            override fun onDiscoveryStopped(serviceType: String) { isDiscovering = false }
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) { isDiscovering = false }
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) { isDiscovering = false }
        }

        runCatching {
            nsdManager.discoverServices("_windin._tcp.", NsdManager.PROTOCOL_DNS_SD, discoveryListener)
        }
    }

    fun stop() {
        discoveryListener?.let { runCatching { nsdManager.stopServiceDiscovery(it) } }
        isDiscovering = false
        multicastLock?.let { if (it.isHeld) it.release() }
    }
}
