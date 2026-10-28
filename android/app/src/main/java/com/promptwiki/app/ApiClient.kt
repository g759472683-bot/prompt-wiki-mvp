package com.promptwiki.app

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ApiException(message: String) : Exception(message)

class ApiClient(baseUrl: String, var token: String? = null) {
    private val base = baseUrl.trim().trimEnd('/')
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(300, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .build()

    fun login(deviceId: String, inviteCode: String, name: String): String {
        val body = JSONObject()
            .put("device_id", deviceId)
            .put("invite_code", inviteCode)
            .put("name", name)
        val response = execute(
            request("$base/v1/auth/device").post(body.toString().toRequestBody(JSON))
        )
        val value = response.optString("token")
        if (value.isBlank()) throw ApiException("登录失败：服务端没有返回 token")
        token = value
        return value
    }

    fun uploadDocument(resolver: ContentResolver, uri: Uri): String {
        val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw ApiException("无法读取文件")
        if (bytes.isEmpty()) throw ApiException("文件为空")
        if (bytes.size > 20 * 1024 * 1024) throw ApiException("文件超过 20MB")
        val name = displayName(resolver, uri) ?: "upload"
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", name, bytes.toRequestBody(mime.toMediaTypeOrNull()))
            .addFormDataPart("doc_type", "resume")
            .addFormDataPart("trust", "high")
            .build()
        val response = execute(request("$base/v1/documents").post(body))
        val id = response.optString("id")
        if (id.isBlank()) throw ApiException("上传失败：服务端没有返回文档 id")
        return id
    }

    fun createCompileJob(documentId: String): String {
        val body = JSONObject()
            .put("document_id", documentId)
            .put("with_cards", true)
        val response = execute(
            request("$base/v1/compile-jobs").post(body.toString().toRequestBody(JSON))
        )
        val id = response.optString("id")
        if (id.isBlank()) throw ApiException("入队失败：服务端没有返回 job id")
        return id
    }

    fun getJob(jobId: String): JobState =
        parseJob(execute(request("$base/v1/jobs/$jobId").get()))

    fun getReview(runId: String): Review =
        parseReview(execute(request("$base/v1/runs/$runId/review").get()))

    fun approve(runId: String, replace: Boolean = false): String {
        val suffix = if (replace) "?replace=true" else ""
        val response = execute(
            request("$base/v1/runs/$runId/approve$suffix").post(EMPTY)
        )
        val collisions = response.optJSONArray("collisions")
        if (collisions != null && collisions.length() > 0) {
            val ids = (0 until collisions.length()).joinToString { collisions.optString(it) }
            throw ApiException("有页面已存在，批准被拒绝：$ids")
        }
        val packPath = response.optString("pack_path")
        if (packPath.isBlank()) throw ApiException("批准成功但没有返回卡包")
        return packPath.substringAfterLast('/').removeSuffix(".json")
    }

    fun getPack(packId: String): PackResponse {
        val response = execute(request("$base/v1/packs/$packId").get())
        val raw = response.toString()
        return PackResponse(raw = raw, pack = parsePack(raw))
    }

    fun listPacks(): List<PackSummary> {
        val array = executeArray(request("$base/v1/packs").get())
        val out = mutableListOf<PackSummary>()
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            out.add(
                PackSummary(
                    packId = item.optString("pack_id"),
                    cardCount = item.optInt("card_count"),
                    approvedAt = item.optString("approved_at").takeIf { it.isNotBlank() },
                )
            )
        }
        return out
    }

    fun ask(question: String, allowUngrounded: Boolean = false): AskResult {
        val body = JSONObject()
            .put("question", question)
            .put("allow_ungrounded", allowUngrounded)
        val response = execute(
            request("$base/v1/ask").post(body.toString().toRequestBody(JSON))
        )
        return parseAsk(response)
    }

    fun latestRelease(): AppUpdate? {
        val response = try {
            execute(request("$base/v1/app/latest").get())
        } catch (exc: ApiException) {
            if (exc.message?.startsWith("HTTP 404") == true) return null
            throw exc
        }
        return AppUpdate(
            versionCode = response.optInt("version_code"),
            versionName = response.optString("version_name"),
            notes = response.optString("notes").takeIf { it.isNotBlank() },
            downloadUrl = response.optString("download_url"),
        )
    }

    fun pinPoint(qaId: String, index: Int, summary: String, detail: String) {
        val body = JSONObject()
            .put("qa_id", qaId)
            .put("point_index", index)
            .put("summary", summary)
            .put("detail", detail)
        execute(
            request("$base/v1/pins/point")
                .put(body.toString().toRequestBody(JSON))
        )
    }

    fun sendFeedback(
        packId: String,
        qaId: String,
        question: String,
        label: String,
        confidence: String,
    ) {
        val body = JSONObject()
            .put("pack_id", packId)
            .put("qa_id", qaId)
            .put("question", question)
            .put("label", label)
            .put("confidence", confidence)
        execute(
            request("$base/v1/feedback")
                .post(body.toString().toRequestBody(JSON))
        )
    }

    fun consistency(): ConsistencySummary {
        val response = execute(request("$base/v1/consistency").get())
        val conflicts = response.optJSONArray("conflicts")
        return ConsistencySummary(
            high = response.optInt("high"),
            medium = response.optInt("medium"),
            total = conflicts?.length() ?: 0,
        )
    }

    private fun request(url: String): Request.Builder {
        val builder = Request.Builder().url(url)
        token?.takeIf { it.isNotBlank() }?.let {
            builder.header("Authorization", "Bearer $it")
        }
        return builder
    }

    private fun execute(request: Request.Builder): JSONObject {
        http.newCall(request.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw ApiException(errorMessage(text, response.code))
            }
            return if (text.isBlank()) JSONObject() else JSONObject(text)
        }
    }

    private fun executeArray(request: Request.Builder): JSONArray {
        http.newCall(request.build()).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                throw ApiException(errorMessage(text, response.code))
            }
            return if (text.isBlank()) JSONArray() else JSONArray(text)
        }
    }

    private fun errorMessage(body: String, code: Int): String {
        val detail = runCatching {
            val json = JSONObject(body)
            val value = json.opt("detail")
            when (value) {
                is JSONObject -> value.toString()
                is JSONArray -> value.toString()
                null -> ""
                else -> value.toString()
            }
        }.getOrNull()
        val message = detail?.takeIf { it.isNotBlank() } ?: body.take(200)
        return "HTTP $code：$message"
    }

    private fun displayName(resolver: ContentResolver, uri: Uri): String? {
        resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
            if (it.moveToFirst()) {
                val index = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) return it.getString(index)
            }
        }
        return null
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
        private val EMPTY = ByteArray(0).toRequestBody(null)
    }
}
