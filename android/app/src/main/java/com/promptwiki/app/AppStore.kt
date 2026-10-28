package com.promptwiki.app

import android.content.Context
import android.content.SharedPreferences
import java.io.File
import java.util.UUID

class AppStore(context: Context) {
    private val prefs: SharedPreferences =
        context.getSharedPreferences("promptwiki", Context.MODE_PRIVATE)
    private val packFile = File(context.filesDir, "packs/latest.json")

    fun baseUrl(): String = prefs.getString("base_url", DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL
    fun token(): String? = prefs.getString("token", null)
    fun invite(): String = prefs.getString("invite", "W1-DEMO") ?: "W1-DEMO"
    fun name(): String = prefs.getString("name", "") ?: ""

    fun allowUngrounded(): Boolean = prefs.getBoolean("allow_ungrounded", false)

    fun setAllowUngrounded(value: Boolean) {
        prefs.edit().putBoolean("allow_ungrounded", value).apply()
    }

    fun saveBaseUrl(value: String) {
        prefs.edit().putString("base_url", value.trimEnd('/')).apply()
    }

    fun saveAuth(token: String, invite: String, name: String) {
        prefs.edit()
            .putString("token", token)
            .putString("invite", invite)
            .putString("name", name)
            .apply()
    }

    fun clearAuth() {
        prefs.edit().remove("token").apply()
    }

    fun deviceId(): String {
        prefs.getString("device_id", null)?.let { return it }
        val secureId = android.provider.Settings.Secure.getString(
            prefsContext.contentResolver,
            android.provider.Settings.Secure.ANDROID_ID,
        )
        val id = "dev-" + (secureId?.takeIf { it.isNotBlank() } ?: UUID.randomUUID().toString())
        prefs.edit().putString("device_id", id).apply()
        return id
    }

    fun savePack(raw: String) {
        packFile.parentFile?.mkdirs()
        packFile.writeText(raw)
    }

    fun loadPack(): String? =
        if (packFile.exists()) runCatching { packFile.readText() }.getOrNull() else null

    fun clearPack() {
        if (packFile.exists()) packFile.delete()
    }

    private val prefsContext: Context = context.applicationContext

    companion object {
        const val DEFAULT_BASE_URL = "http://192.168.137.1:8000"
    }
}
