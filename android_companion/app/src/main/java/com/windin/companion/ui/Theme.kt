package com.windin.companion.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val WinDinBlack = Color(0xFF0A0A0A)
val WinDinCard = Color(0xFF141416)
val WinDinCardBorder = Color(0xFF26262A)
val WinDinLime = Color(0xFFA3E635)
val WinDinLimeDull = Color(0xFF4D7C0F)
val WinDinTextPrimary = Color(0xFFF5F5F5)
val WinDinTextSecondary = Color(0xFFA1A1AA)
val WinDinRed = Color(0xFFEF4444)

private val DarkColorScheme = darkColorScheme(
    primary = WinDinLime,
    onPrimary = Color.Black,
    primaryContainer = WinDinLimeDull,
    onPrimaryContainer = WinDinLime,
    surface = WinDinCard,
    onSurface = WinDinTextPrimary,
    background = WinDinBlack,
    onBackground = WinDinTextPrimary,
    error = WinDinRed
)

@Composable
fun WinDinTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        content = content
    )
}
