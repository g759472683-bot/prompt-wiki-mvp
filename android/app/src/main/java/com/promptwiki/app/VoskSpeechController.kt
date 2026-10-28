package com.promptwiki.app

import android.content.Context
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import org.vosk.android.StorageService

/**
 * Offline Chinese ASR using Vosk.
 *
 * The small Chinese model is bundled in assets/model-cn and copied to external
 * files on first use, because the native decoder needs a real filesystem path.
 */
class VoskSpeechController(
    private val context: Context,
    private val onText: (String) -> Unit,
    private val onError: (String) -> Unit,
    private val onStatus: (String) -> Unit = {},
) {
    private var model: Model? = null
    private var recognizer: Recognizer? = null
    private var service: SpeechService? = null
    private var loading = false
    private var pendingStart = false
    private var listening = false
    private var destroyed = false

    val isAvailable: Boolean = true
    val isReady: Boolean get() = model != null

    fun start() {
        if (destroyed) return
        listening = true
        if (model != null) {
            startService()
        } else {
            pendingStart = true
            loadModel()
        }
    }

    fun stop() {
        listening = false
        pendingStart = false
        runCatching { service?.stop() }
        runCatching { service?.shutdown() }
        service = null
        runCatching { recognizer?.close() }
        recognizer = null
    }

    fun destroy() {
        destroyed = true
        stop()
        runCatching { model?.close() }
        model = null
    }

    private fun loadModel() {
        if (loading || model != null) return
        loading = true
        onStatus("正在加载离线语音模型…")
        StorageService.unpack(
            context,
            "model-cn",
            "vosk",
            { loaded ->
                loading = false
                if (destroyed) {
                    runCatching { loaded.close() }
                } else {
                    model = loaded
                    onStatus("离线语音就绪")
                    if (pendingStart && listening) {
                        pendingStart = false
                        startService()
                    }
                }
            },
            { error ->
                loading = false
                pendingStart = false
                listening = false
                onError("离线语音模型加载失败：${error.message ?: "未知错误"}")
            },
        )
    }

    private fun startService() {
        if (service != null) return
        val current = model ?: return
        try {
            val rec = Recognizer(current, 16000.0f)
            recognizer = rec
            val svc = SpeechService(rec, 16000.0f)
            service = svc
            val started = svc.startListening(listener)
            if (!started) {
                onError("语音已经在运行")
                return
            }
            onStatus("正在聆听，请说话")
        } catch (exc: Exception) {
            listening = false
            onError("语音启动失败：${exc.message ?: "未知错误"}")
            stop()
        }
    }

    private fun emit(json: String, key: String) {
        val text = runCatching { JSONObject(json).optString(key) }
            .getOrNull()
            ?.trim()
            .orEmpty()
        if (text.isNotBlank()) onText(text)
    }

    private val listener = object : RecognitionListener {
        override fun onPartialResult(hypothesis: String?) {
            if (hypothesis != null) emit(hypothesis, "partial")
        }

        override fun onResult(hypothesis: String?) {
            if (hypothesis != null) emit(hypothesis, "text")
        }

        override fun onFinalResult(hypothesis: String?) {
            if (hypothesis != null) emit(hypothesis, "text")
        }

        override fun onError(exception: Exception?) {
            listening = false
            onError("语音识别失败：${exception?.message ?: "未知错误"}")
        }

        override fun onTimeout() = Unit
    }
}
