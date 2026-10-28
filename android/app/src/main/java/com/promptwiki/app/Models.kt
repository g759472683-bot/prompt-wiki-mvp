package com.promptwiki.app

import org.json.JSONArray
import org.json.JSONObject

data class Citation(
    val source: String,
    val block: String,
    val quote: String,
    val pageLabel: String,
)

data class Followup(
    val question: String,
    val answer: String,
)

data class CardPoint(
    val index: Int,
    val summary: String,
    val detail: String,
    val confidence: String,
    val score: Int,
    val citations: List<Citation>,
    val followups: List<Followup>,
    val pinned: Boolean = false,
    val pinUpdatedAt: String? = null,
)

data class PromptCard(
    val qaId: String,
    val question: String,
    val variants: List<String>,
    val l1: List<String>,
    val l2: List<String>,
    val l3: String,
    val fallback: String,
    val confidence: String,
    val confidenceScore: Int,
    val calibrated: Boolean,
    val calibrationSamples: Int,
    val citations: List<Citation>,
    val doNotSay: List<String>,
    val points: List<CardPoint>,
    val ungrounded: Boolean = false,
)

data class Pack(
    val packId: String,
    val cards: List<PromptCard>,
)

data class Review(
    val runId: String,
    val pageCount: Int,
    val cardCount: Int,
    val collisions: List<String>,
)

data class JobState(
    val id: String,
    val status: String,
    val progress: Int,
    val error: String?,
    val runId: String?,
    val pages: Int,
    val cards: Int,
)

data class PackResponse(
    val raw: String,
    val pack: Pack,
)

data class AskResult(
    val card: PromptCard,
    val degraded: Boolean,
    val hitPath: String,
    val notice: String?,
)

data class AppUpdate(
    val versionCode: Int,
    val versionName: String,
    val notes: String?,
    val downloadUrl: String,
)

data class PackSummary(
    val packId: String,
    val cardCount: Int,
    val approvedAt: String?,
)

data class ConsistencySummary(
    val high: Int,
    val medium: Int,
    val total: Int,
)

private fun JSONArray.strings(): List<String> =
    (0 until length()).map { optString(it) }.filter { it.isNotBlank() }

private fun levelScore(level: String): Int = when (level) {
    "green" -> 85
    "red" -> 30
    else -> 60
}

private fun parseCitations(array: JSONArray?): List<Citation> {
    val out = mutableListOf<Citation>()
    if (array == null) return out
    for (i in 0 until array.length()) {
        val item = array.optJSONObject(i) ?: continue
        out.add(
            Citation(
                source = item.optString("source"),
                block = item.optString("block"),
                quote = item.optString("quote"),
                pageLabel = item.optString("page_label"),
            )
        )
    }
    return out
}

private fun parseFollowups(array: JSONArray?): List<Followup> {
    val out = mutableListOf<Followup>()
    if (array == null) return out
    for (i in 0 until array.length()) {
        val item = array.optJSONObject(i) ?: continue
        val question = item.optString("question").trim()
        val answer = item.optString("answer").trim()
        if (question.isNotBlank()) out.add(Followup(question, answer))
    }
    return out
}

private fun parsePoints(
    array: JSONArray?,
    l2: List<String>,
    fallbackCitations: List<Citation>,
    fallbackLevel: String,
    fallbackScore: Int,
): List<CardPoint> {
    val parsed = mutableListOf<CardPoint>()
    if (array != null) {
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: continue
            val summary = item.optString("summary").trim().ifBlank {
                l2.getOrNull(i).orEmpty()
            }
            val detail = item.optString("detail").trim().ifBlank { summary }
            val confidence = item.optJSONObject("confidence")
            val level = confidence?.optString("level")?.takeIf { it.isNotBlank() }
                ?: fallbackLevel
            val score = confidence?.optInt("score")?.takeIf { it > 0 }
                ?: levelScore(level)
            parsed.add(
                CardPoint(
                    index = item.optInt("index", i + 1),
                    summary = summary,
                    detail = detail,
                    confidence = level,
                    score = score,
                    citations = parseCitations(item.optJSONArray("citations"))
                        .ifEmpty { fallbackCitations },
                    followups = parseFollowups(item.optJSONArray("followups")),
                    pinned = item.optBoolean("pinned", false),
                    pinUpdatedAt = item.optString("pin_updated_at")
                        .takeIf { it.isNotBlank() },
                )
            )
        }
    }
    if (parsed.isNotEmpty()) return parsed
    return l2.mapIndexed { index, line ->
        CardPoint(
            index = index + 1,
            summary = line,
            detail = line,
            confidence = fallbackLevel,
            score = fallbackScore,
            citations = fallbackCitations,
            followups = emptyList(),
        )
    }
}

fun parseAsk(root: JSONObject): AskResult {
    val cardObj = root.optJSONObject("card") ?: JSONObject()
    val confidenceObj = cardObj.optJSONObject("confidence")
    val level = confidenceObj?.optString("level")?.takeIf { it.isNotBlank() } ?: "red"
    val score = confidenceObj?.optInt("score")?.takeIf { it > 0 } ?: levelScore(level)
    val citations = parseCitations(cardObj.optJSONArray("citations"))
    val l2 = cardObj.optJSONArray("l2")?.strings() ?: emptyList()
    val card = PromptCard(
        qaId = "ask",
        question = root.optString("question"),
        variants = emptyList(),
        l1 = cardObj.optJSONArray("l1")?.strings() ?: emptyList(),
        l2 = l2,
        l3 = cardObj.optString("l3"),
        fallback = cardObj.optString("fallback"),
        confidence = level,
        confidenceScore = score,
        calibrated = confidenceObj?.optBoolean("calibrated", false) ?: false,
        calibrationSamples = confidenceObj?.optInt("calibration_samples", 0) ?: 0,
        citations = citations,
        doNotSay = cardObj.optJSONArray("do_not_say")?.strings() ?: emptyList(),
        points = parsePoints(
            cardObj.optJSONArray("points"),
            l2,
            citations,
            level,
            score,
        ),
        ungrounded = root.optBoolean("ungrounded", false),
    )
    return AskResult(
        card = card,
        degraded = root.optBoolean("degraded", true),
        hitPath = root.optString("hit_path"),
        notice = root.optJSONArray("notices")?.strings()?.firstOrNull(),
    )
}

fun packJson(cards: List<PromptCard>, packId: String): String {
    val array = JSONArray()
    for (card in cards) {
        val citations = JSONArray()
        for (citation in card.citations) {
            citations.put(citationJson(citation))
        }
        val points = JSONArray()
        for (point in card.points) {
            val pointCitations = JSONArray()
            for (citation in point.citations) {
                pointCitations.put(citationJson(citation))
            }
            val followups = JSONArray()
            for (followup in point.followups) {
                followups.put(
                    JSONObject()
                        .put("question", followup.question)
                        .put("answer", followup.answer)
                )
            }
            points.put(
                JSONObject()
                    .put("index", point.index)
                    .put("summary", point.summary)
                    .put("detail", point.detail)
                    .put(
                        "confidence",
                        JSONObject()
                            .put("level", point.confidence)
                            .put("score", point.score)
                            .put("reasons", JSONArray(listOf("batch_merge"))),
                    )
                    .put("citations", pointCitations)
                    .put("followups", followups)
                    .put("pinned", point.pinned)
                    .put("pin_updated_at", point.pinUpdatedAt ?: "")
            )
        }
        array.put(
            JSONObject()
                .put("qa_id", card.qaId)
                .put("question", card.question)
                .put("variants", JSONArray(card.variants))
                .put("l1", JSONArray(card.l1))
                .put("l2", JSONArray(card.l2))
                .put("points", points)
                .put("l3_markdown", card.l3)
                .put("fallback", card.fallback)
                    .put(
                        "confidence",
                        JSONObject()
                            .put("level", card.confidence)
                            .put("score", card.confidenceScore)
                            .put("calibrated", card.calibrated)
                            .put("calibration_samples", card.calibrationSamples)
                            .put("reasons", JSONArray(listOf("batch_merge"))),
                    )
                .put("citations", citations)
                .put("do_not_say", JSONArray(card.doNotSay))
                .put("ungrounded", card.ungrounded)
        )
    }
    return JSONObject()
        .put("schema_version", "1.0")
        .put("pack_id", packId)
        .put("version", 1)
        .put("approved", true)
        .put("cards", array)
        .toString()
}

private fun citationJson(citation: Citation): JSONObject =
    JSONObject()
        .put("source", citation.source)
        .put("block", citation.block)
        .put("quote", citation.quote)
        .put("page_label", citation.pageLabel)

fun parsePack(raw: String): Pack {
    val root = JSONObject(raw)
    val cards = mutableListOf<PromptCard>()
    val array = root.optJSONArray("cards") ?: JSONArray()
    for (i in 0 until array.length()) {
        val item = array.optJSONObject(i) ?: continue
        val confidenceObj = item.optJSONObject("confidence")
        val level = confidenceObj?.optString("level")?.takeIf { it.isNotBlank() }
            ?: "yellow"
        val score = confidenceObj?.optInt("score")?.takeIf { it > 0 }
            ?: levelScore(level)
        val citations = parseCitations(item.optJSONArray("citations"))
        val l2 = item.optJSONArray("l2")?.strings() ?: emptyList()
        cards.add(
            PromptCard(
                qaId = item.optString("qa_id"),
                question = item.optString("question"),
                variants = item.optJSONArray("variants")?.strings() ?: emptyList(),
                l1 = item.optJSONArray("l1")?.strings() ?: emptyList(),
                l2 = l2,
                l3 = item.optString("l3_markdown"),
                fallback = item.optString("fallback"),
                confidence = level,
                confidenceScore = score,
                calibrated = confidenceObj?.optBoolean("calibrated", false) ?: false,
                calibrationSamples = confidenceObj?.optInt("calibration_samples", 0) ?: 0,
                citations = citations,
                doNotSay = item.optJSONArray("do_not_say")?.strings() ?: emptyList(),
                points = parsePoints(
                    item.optJSONArray("points"),
                    l2,
                    citations,
                    level,
                    score,
                ),
                ungrounded = item.optBoolean("ungrounded", false),
            )
        )
    }
    return Pack(
        packId = root.optString("pack_id"),
        cards = cards,
    )
}

fun parseJob(root: JSONObject): JobState {
    val result = root.optJSONObject("result")
    return JobState(
        id = root.optString("id"),
        status = root.optString("status", "unknown"),
        progress = root.optInt("progress", 0),
        error = root.optString("error").takeIf { it.isNotBlank() && it != "null" },
        runId = result?.optString("run_id")?.takeIf { it.isNotBlank() },
        pages = result?.optJSONArray("pages")?.length() ?: 0,
        cards = result?.optJSONArray("cards")?.length() ?: 0,
    )
}

fun parseReview(root: JSONObject): Review {
    return Review(
        runId = root.optString("run_id"),
        pageCount = root.optJSONArray("pages")?.length() ?: 0,
        cardCount = root.optJSONArray("cards")?.length() ?: 0,
        collisions = root.optJSONArray("collisions")?.strings() ?: emptyList(),
    )
}
