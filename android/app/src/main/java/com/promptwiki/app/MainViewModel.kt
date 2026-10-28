package com.promptwiki.app

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Screen { SETUP, HOME, REVIEW, LIVE, SETTINGS }

data class AppUiState(
    val screen: Screen = Screen.SETUP,
    val baseUrl: String = "",
    val invite: String = "",
    val name: String = "",
    val busy: Boolean = false,
    val status: String = "",
    val progress: Int = 0,
    val pages: Int = 0,
    val cards: Int = 0,
    val collisions: List<String> = emptyList(),
    val pack: Pack? = null,
    val runId: String? = null,
    val runIds: List<String> = emptyList(),
    val batchTotal: Int = 0,
    val batchDone: Int = 0,
    val query: String = "",
    val transcript: String = "",
    val matched: PromptCard? = null,
    val asking: Boolean = false,
    val degraded: Boolean = false,
    val showL3: Boolean = false,
    val showCitations: Boolean = false,
    val message: String? = null,
    val error: String? = null,
    val feedback: Int = 0,
    val checkingUpdate: Boolean = false,
    val update: AppUpdate? = null,
    val restoringPack: Boolean = false,
    val consistency: ConsistencySummary? = null,
    val allowUngrounded: Boolean = false,
)

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val store = AppStore(application)
    private var api: ApiClient? = store.token()?.let { ApiClient(store.baseUrl(), it) }
    private val cachedPack = store.loadPack()?.let {
        runCatching { parsePack(it) }.getOrNull()
    }

    private val _state = MutableStateFlow(
        AppUiState(
            screen = if (store.token().isNullOrBlank()) Screen.SETUP else Screen.HOME,
            baseUrl = store.baseUrl(),
            invite = store.invite(),
            name = store.name(),
            pack = cachedPack,
            message = if (cachedPack != null) "已加载上次卡包（${cachedPack.cards.size} 张）" else null,
            allowUngrounded = store.allowUngrounded(),
        )
    )
    val state: StateFlow<AppUiState> = _state.asStateFlow()

    init {
        if (!store.token().isNullOrBlank() &&
            (cachedPack == null || !hasRichPoints(cachedPack))
        ) {
            restoreLatestPack()
        }
        if (!store.token().isNullOrBlank()) {
            refreshConsistency()
        }
    }

    fun setQuery(value: String) {
        _state.update { it.copy(query = value) }
    }

    fun onTranscript(value: String) {
        if (value.isBlank()) return
        _state.update { it.copy(transcript = value.takeLast(300)) }
    }

    fun onSpeechError(message: String) {
        _state.update { it.copy(message = message) }
    }

    fun onSpeechStatus(message: String) {
        _state.update { it.copy(message = message) }
    }

    fun login(baseUrl: String, invite: String, name: String) {
        val cleaned = baseUrl.trim().trimEnd('/')
        if (cleaned.isBlank()) {
            _state.update { it.copy(error = "请填后端地址") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(busy = true, error = null, status = "登录中") }
            try {
                val client = ApiClient(cleaned, null)
                val token = withContext(Dispatchers.IO) {
                    client.login(store.deviceId(), invite.trim(), name.trim())
                }
                client.token = token
                api = client
                store.saveBaseUrl(cleaned)
                store.saveAuth(token, invite.trim(), name.trim())
                _state.update {
                    it.copy(
                        screen = Screen.HOME,
                        baseUrl = cleaned,
                        invite = invite.trim(),
                        name = name.trim(),
                        busy = false,
                        status = "",
                    )
                }
                if (_state.value.pack == null) restoreLatestPack()
                refreshConsistency()
            } catch (exc: Exception) {
                fail(exc)
            }
        }
    }

    fun uploadAndCompile(uris: List<Uri>) {
        if (uris.isEmpty()) return
        val client = api ?: run {
            _state.update { it.copy(error = "请先登录") }
            return
        }
        val resolver = getApplication<Application>().contentResolver
        viewModelScope.launch {
            _state.update {
                it.copy(
                    busy = true,
                    error = null,
                    message = null,
                    progress = 1,
                    status = "准备上传",
                    runIds = emptyList(),
                    pages = 0,
                    cards = 0,
                    batchTotal = uris.size,
                    batchDone = 0,
                )
            }
            val runs = mutableListOf<String>()
            var pages = 0
            var cards = 0
            try {
                uris.forEachIndexed { index, uri ->
                    val prefix = "第 ${index + 1}/${uris.size} 份"
                    _state.update { it.copy(status = "$prefix · 上传", progress = index * 100 / uris.size) }
                    val docId = withContext(Dispatchers.IO) {
                        client.uploadDocument(resolver, uri)
                    }
                    _state.update { it.copy(status = "$prefix · 生成") }
                    val jobId = withContext(Dispatchers.IO) {
                        client.createCompileJob(docId)
                    }
                    val job = pollJob(client, jobId, prefix, index, uris.size)
                    if (job == null) return@launch
                    val runId = job.runId
                    if (runId.isNullOrBlank()) {
                        failMessage("生成完成但没有 run_id")
                        return@launch
                    }
                    runs.add(runId)
                    pages += job.pages
                    cards += job.cards
                    _state.update {
                        it.copy(
                            runIds = runs.toList(),
                            runId = runId,
                            pages = pages,
                            cards = cards,
                            batchDone = index + 1,
                            progress = (index + 1) * 100 / uris.size,
                        )
                    }
                }
                val review = runs.lastOrNull()?.let { run ->
                    runCatching {
                        withContext(Dispatchers.IO) { client.getReview(run) }
                    }.getOrNull()
                }
                _state.update {
                    it.copy(
                        screen = Screen.REVIEW,
                        busy = false,
                        runIds = runs,
                        pages = pages,
                        cards = cards,
                        collisions = review?.collisions ?: emptyList(),
                        status = "",
                        progress = 100,
                    )
                }
            } catch (exc: Exception) {
                fail(exc)
            }
        }
    }

    fun uploadAndCompile(uri: Uri) = uploadAndCompile(listOf(uri))

    private suspend fun pollJob(
        client: ApiClient,
        jobId: String,
        prefix: String,
        index: Int,
        total: Int,
    ): JobState? {
        for (attempt in 0 until 150) {
            delay(2_000)
            val job = withContext(Dispatchers.IO) { client.getJob(jobId) }
            val overall = ((index * 100) + job.progress) / total
            _state.update {
                it.copy(
                    progress = overall.coerceIn(0, 99),
                    status = "$prefix · " + when (job.status) {
                        "queued" -> "排队中"
                        "running" -> "生成中 ${job.progress}%"
                        "succeeded" -> "完成"
                        "failed" -> "失败"
                        else -> job.status
                    },
                )
            }
            when (job.status) {
                "succeeded" -> return job
                "failed" -> {
                    failMessage(job.error ?: "生成失败")
                    return null
                }
            }
        }
        failMessage("生成超时（5 分钟）")
        return null
    }

    fun approveAndStart(replace: Boolean = false) {
        val client = api ?: return
        val runIds = _state.value.runIds.ifEmpty {
            listOfNotNull(_state.value.runId)
        }
        if (runIds.isEmpty()) {
            _state.update { it.copy(error = "没有可批准的 run") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(busy = true, error = null, status = "批准中") }
            try {
                val merged = linkedMapOf<String, PromptCard>()
                runIds.forEachIndexed { index, runId ->
                    _state.update { it.copy(status = "批准 ${index + 1}/${runIds.size}") }
                    val packId = withContext(Dispatchers.IO) {
                        client.approve(runId, replace = replace)
                    }
                    val response = withContext(Dispatchers.IO) { client.getPack(packId) }
                    response.pack.cards.forEach { card ->
                        merged.putIfAbsent(card.qaId + "|" + card.question, card)
                    }
                }
                val cards = merged.values.take(20)
                if (cards.isEmpty()) {
                    failMessage("批准成功但没有卡片")
                    return@launch
                }
                val packId = "pack-batch-${System.currentTimeMillis()}"
                store.savePack(packJson(cards, packId))
                _state.update {
                    it.copy(
                        pack = Pack(packId, cards),
                        screen = Screen.LIVE,
                        busy = false,
                        status = "",
                        cards = cards.size,
                        message = "卡包已就绪：${cards.size} 张（合并 ${runIds.size} 个来源）",
                        matched = null,
                        asking = false,
                        degraded = false,
                        showL3 = false,
                        showCitations = false,
                    )
                }
            } catch (exc: Exception) {
                fail(exc)
            }
        }
    }

    fun openCachedPack() {
        val pack = _state.value.pack ?: return
        _state.update {
            it.copy(
                screen = Screen.LIVE,
                matched = null,
                message = "已打开 ${pack.cards.size} 张卡",
            )
        }
    }

    fun restoreLatestPack() {
        val client = api ?: return
        if (_state.value.restoringPack) return
        viewModelScope.launch {
            _state.update { it.copy(restoringPack = true, message = null) }
            try {
                val packs = withContext(Dispatchers.IO) { client.listPacks() }
                if (packs.isEmpty()) {
                    _state.update {
                        it.copy(restoringPack = false, message = "服务器上还没有已发布卡包")
                    }
                    return@launch
                }
                val response = withContext(Dispatchers.IO) {
                    client.getPack(packs.first().packId)
                }
                store.savePack(response.raw)
                _state.update {
                    it.copy(
                        pack = response.pack,
                        restoringPack = false,
                        message = "已恢复卡包：${response.pack.cards.size} 张",
                    )
                }
            } catch (exc: Exception) {
                _state.update {
                    it.copy(
                        restoringPack = false,
                        message = "查找卡包失败：${exc.message ?: "网络错误"}",
                    )
                }
            }
        }
    }

    fun trigger() {
        val current = _state.value
        val pack = current.pack ?: return
        val query = current.transcript.ifBlank { current.query }
        if (query.isBlank()) {
            _state.update { it.copy(message = "没有听到问题：先手动输入，或再按一次") }
            return
        }
        val local = matchCard(pack, query)
        if (local != null) {
            _state.update {
                it.copy(
                    matched = local,
                    asking = false,
                    degraded = false,
                    showL3 = false,
                    showCitations = false,
                    message = null,
                )
            }
            return
        }
        if (current.asking) return
        val client = api ?: return
        _state.update {
            it.copy(
                matched = null,
                asking = true,
                degraded = true,
                showL3 = false,
                showCitations = false,
                message = "没命中卡片，正在召回原文…",
            )
        }
        viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) {
                    client.ask(query, current.allowUngrounded)
                }
                _state.update {
                    it.copy(
                        matched = result.card,
                        asking = false,
                        degraded = result.degraded,
                        message = result.notice ?: "现场组装 · ${result.card.citations.size} 条引用",
                    )
                }
            } catch (exc: Exception) {
                _state.update {
                    it.copy(
                        asking = false,
                        message = "现场召回失败，先按兜底说：${exc.message ?: "网络错误"}",
                    )
                }
            }
        }
    }

    fun toggleL3() {
        _state.update { it.copy(showL3 = !it.showL3) }
    }

    fun openCitations() {
        _state.update { it.copy(showCitations = true) }
    }

    fun closeCitations() {
        _state.update { it.copy(showCitations = false) }
    }

    fun feedback(label: String) {
        val current = _state.value
        val pack = current.pack
        val card = current.matched
        if (pack != null && card != null) {
            val apiLabel = when (label) {
                "有用" -> "useful"
                "没用" -> "not_useful"
                else -> "fallback"
            }
            viewModelScope.launch {
                runCatching {
                    withContext(Dispatchers.IO) {
                        api?.sendFeedback(
                            packId = pack.packId,
                            qaId = card.qaId,
                            question = card.question,
                            label = apiLabel,
                            confidence = card.confidence,
                        )
                    }
                }
            }
        }
        _state.update {
            it.copy(
                feedback = it.feedback + 1,
                message = "已记录：$label",
            )
        }
    }

    fun pinPoint(point: CardPoint, summary: String, detail: String) {
        val current = _state.value
        val pack = current.pack ?: return
        val card = current.matched ?: return
        val client = api ?: return
        if (card.qaId == "ask") {
            _state.update { it.copy(message = "现场组装的卡片不能固定，回编译卡再改") }
            return
        }
        val newSummary = summary.trim().ifBlank { point.summary }
        val newDetail = detail.trim().ifBlank { point.detail }
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    client.pinPoint(card.qaId, point.index, newSummary, newDetail)
                }
                val updatedCard = card.copy(
                    points = card.points.map {
                        if (it.index == point.index) {
                            it.copy(
                                summary = newSummary,
                                detail = newDetail,
                                pinned = true,
                            )
                        } else {
                            it
                        }
                    }
                )
                val updatedPack = pack.copy(
                    cards = pack.cards.map {
                        if (it.qaId == card.qaId) updatedCard else it
                    }
                )
                store.savePack(packJson(updatedPack.cards, updatedPack.packId))
                _state.update {
                    it.copy(
                        pack = updatedPack,
                        matched = updatedCard,
                        message = "已固定第 ${point.index} 条",
                    )
                }
            } catch (exc: Exception) {
                _state.update { it.copy(error = "固定失败：${exc.message}") }
            }
        }
    }

    fun saveBaseUrl(value: String) {
        val cleaned = value.trim().trimEnd('/')
        store.saveBaseUrl(cleaned)
        api = store.token()?.let { ApiClient(cleaned, it) }
        _state.update { it.copy(baseUrl = cleaned, message = "后端地址已保存") }
    }

    fun checkUpdate() {
        val client = api ?: run {
            _state.update { it.copy(message = "请先登录") }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(checkingUpdate = true, message = null) }
            try {
                val latest = withContext(Dispatchers.IO) { client.latestRelease() }
                if (latest == null || latest.versionCode <= BuildConfig.VERSION_CODE) {
                    _state.update { it.copy(checkingUpdate = false, message = "已是最新版本") }
                } else {
                    _state.update { it.copy(checkingUpdate = false, update = latest) }
                }
            } catch (exc: Exception) {
                _state.update {
                    it.copy(checkingUpdate = false, message = "检查更新失败：${exc.message}")
                }
            }
        }
    }

    fun dismissUpdate() {
        _state.update { it.copy(update = null) }
    }

    fun refreshConsistency() {
        val client = api ?: return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { client.consistency() }
            }.onSuccess { summary ->
                _state.update { it.copy(consistency = summary) }
            }
        }
    }

    fun setAllowUngrounded(value: Boolean) {
        store.setAllowUngrounded(value)
        _state.update { it.copy(allowUngrounded = value) }
    }

    fun logout() {
        store.clearAuth()
        store.clearPack()
        api = null
        _state.update {
            AppUiState(
                screen = Screen.SETUP,
                baseUrl = it.baseUrl,
                invite = it.invite,
                name = it.name,
            )
        }
    }

    fun clearPack() {
        store.clearPack()
        _state.update { it.copy(pack = null, screen = Screen.HOME, message = "本地卡包已清除") }
    }

    fun goHome() {
        _state.update { it.copy(screen = Screen.HOME, busy = false) }
    }

    fun goSettings() {
        _state.update { it.copy(screen = Screen.SETTINGS) }
    }

    private fun fail(exc: Exception) {
        _state.update {
            it.copy(
                busy = false,
                asking = false,
                error = exc.message ?: "请求失败",
                status = "",
            )
        }
    }

    private fun failMessage(message: String) {
        _state.update { it.copy(busy = false, asking = false, error = message, status = "") }
    }
}

private fun normalize(text: String): String =
    text.lowercase().filter { it.isLetterOrDigit() }

private fun hasRichPoints(pack: Pack): Boolean =
    pack.cards.any { card ->
        card.points.any { point ->
            point.detail.isNotBlank() && point.detail != point.summary
        }
    }

private fun bigrams(text: String): Set<String> {
    if (text.length < 2) return setOf(text)
    return (0 until text.length - 1).map { text.substring(it, it + 2) }.toSet()
}

private fun similarity(left: String, right: String): Double {
    val a = bigrams(left)
    val b = bigrams(right)
    if (a.isEmpty() || b.isEmpty()) return 0.0
    val overlap = a.intersect(b).size
    return 2.0 * overlap / (a.size + b.size)
}

fun matchCard(pack: Pack, rawQuery: String): PromptCard? {
    val query = normalize(rawQuery)
    if (query.length < 2) return null
    var best: PromptCard? = null
    var bestScore = 0.0
    for (card in pack.cards) {
        val candidates = buildList {
            add(card.question)
            addAll(card.variants)
        }
        for (candidate in candidates) {
            val variant = normalize(candidate)
            if (variant.length < 3) continue
            val score = when {
                query == variant -> 1.0
                query.length >= 4 && query.contains(variant) -> 0.95
                variant.length >= 4 && variant.contains(query) -> 0.9
                else -> similarity(query.takeLast(80), variant)
            }
            if (score > bestScore) {
                bestScore = score
                best = card
            }
        }
    }
    return if (bestScore >= 0.45) best else null
}
