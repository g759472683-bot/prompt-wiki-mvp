@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.promptwiki.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import android.support.v4.media.session.MediaSessionCompat
import android.support.v4.media.session.PlaybackStateCompat

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()
    private lateinit var mediaSession: MediaSessionCompat

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        mediaSession = MediaSessionCompat(this, "PromptWiki").apply {
            setFlags(
                MediaSessionCompat.FLAG_HANDLES_MEDIA_BUTTONS or
                    MediaSessionCompat.FLAG_HANDLES_TRANSPORT_CONTROLS
            )
            setCallback(object : MediaSessionCompat.Callback() {
                override fun onPlay() = viewModel.trigger()
                override fun onPause() = viewModel.trigger()
            })
            isActive = true
            setPlaybackState(
                PlaybackStateCompat.Builder()
                    .setActions(
                        PlaybackStateCompat.ACTION_PLAY or PlaybackStateCompat.ACTION_PAUSE
                    )
                    .setState(PlaybackStateCompat.STATE_PLAYING, 0L, 1f)
                    .build()
            )
        }

        setContent {
            PromptWikiTheme {
                PromptWikiApp(viewModel)
            }
        }
    }

    override fun onDestroy() {
        mediaSession.release()
        super.onDestroy()
    }
}

@Composable
private fun PromptWikiTheme(content: @Composable () -> Unit) {
    val colors = darkColorScheme(
        primary = Color(0xFF7BD88F),
        onPrimary = Color(0xFF08210F),
        background = Color(0xFF0E1114),
        onBackground = Color(0xFFE6EDF3),
        surface = Color(0xFF171C21),
        onSurface = Color(0xFFE6EDF3),
        surfaceVariant = Color(0xFF222A31),
        onSurfaceVariant = Color(0xFFB7C2CC),
        error = Color(0xFFFF8A80),
    )
    MaterialTheme(colorScheme = colors) {
        Surface(color = colors.background, contentColor = colors.onBackground) {
            content()
        }
    }
}

@Composable
private fun PromptWikiApp(viewModel: MainViewModel) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    var speechOn by remember { mutableStateOf(false) }

    val speech = remember {
        VoskSpeechController(
            context = context,
            onText = viewModel::onTranscript,
            onError = { message ->
                speechOn = false
                viewModel.onSpeechError(message)
            },
            onStatus = viewModel::onSpeechStatus,
        )
    }
    DisposableEffect(Unit) {
        onDispose { speech.destroy() }
    }
    LaunchedEffect(state.screen) {
        if (state.screen != Screen.LIVE && speechOn) {
            speech.stop()
            speechOn = false
        }
    }

    val audioPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            speech.start()
            speechOn = true
        } else {
            viewModel.onSpeechError("需要麦克风权限")
        }
    }
    val bluetoothPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }
    LaunchedEffect(Unit) {
        if (Build.VERSION.SDK_INT >= 31 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.BLUETOOTH_CONNECT) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            bluetoothPermission.launch(Manifest.permission.BLUETOOTH_CONNECT)
        }
    }

    val picker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenMultipleDocuments()
    ) { uris ->
        if (uris.isNotEmpty()) viewModel.uploadAndCompile(uris)
    }

    val toggleSpeech: () -> Unit = {
        if (speechOn) {
            speech.stop()
            speechOn = false
        } else if (!speech.isAvailable) {
            viewModel.onSpeechError("这台设备没有语音识别服务，请用输入框")
        } else if (ContextCompat.checkSelfPermission(
                context, Manifest.permission.RECORD_AUDIO
            ) == PackageManager.PERMISSION_GRANTED
        ) {
            speech.start()
            speechOn = true
        } else {
            audioPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    when (state.screen) {
        Screen.SETUP -> SetupScreen(state, viewModel::login)
        Screen.HOME -> HomeScreen(
            state = state,
            onPick = {
                picker.launch(
                    arrayOf(
                        "application/pdf",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "text/plain",
                        "text/markdown",
                    )
                )
            },
            onOpenPack = viewModel::openCachedPack,
            onRestore = viewModel::restoreLatestPack,
            onSettings = viewModel::goSettings,
        )
        Screen.REVIEW -> ReviewScreen(
            state = state,
            onApprove = viewModel::approveAndStart,
            onApproveReplace = { viewModel.approveAndStart(true) },
            onHome = viewModel::goHome,
        )
        Screen.LIVE -> LiveScreen(
            state = state,
            speechOn = speechOn,
            speechAvailable = speech.isAvailable,
            onToggleSpeech = toggleSpeech,
            onTrigger = viewModel::trigger,
            onQueryChange = viewModel::setQuery,
            onToggleL3 = viewModel::toggleL3,
            onOpenCitations = viewModel::openCitations,
            onCloseCitations = viewModel::closeCitations,
            onFeedback = viewModel::feedback,
            onPinPoint = viewModel::pinPoint,
            onSettings = viewModel::goSettings,
        )
        Screen.SETTINGS -> SettingsScreen(
            state = state,
            onSave = viewModel::saveBaseUrl,
            onLogout = viewModel::logout,
            onClearPack = viewModel::clearPack,
            onBack = viewModel::goHome,
            onCheckUpdate = viewModel::checkUpdate,
            onDismissUpdate = viewModel::dismissUpdate,
            onToggleUngrounded = viewModel::setAllowUngrounded,
        )
    }
}

@Composable
private fun SetupScreen(state: AppUiState, onLogin: (String, String, String) -> Unit) {
    var baseUrl by rememberSaveable { mutableStateOf(state.baseUrl) }
    var invite by rememberSaveable { mutableStateOf(state.invite) }
    var name by rememberSaveable { mutableStateOf(state.name) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text("提词卡", fontSize = 34.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text(
            "会前编译，会中 1 秒开口。\n先连上你电脑上的后端，再上传一份材料。",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(28.dp))

        OutlinedTextField(
            value = baseUrl,
            onValueChange = { baseUrl = it },
            label = { Text("后端地址") },
            placeholder = { Text("http://192.168.1.100:8000") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = invite,
            onValueChange = { invite = it },
            label = { Text("邀请码") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("你的名字（可空）") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(20.dp))
        Button(
            onClick = { onLogin(baseUrl, invite, name) },
            enabled = !state.busy,
            modifier = Modifier.fillMaxWidth().height(52.dp),
        ) {
            if (state.busy) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(10.dp))
            }
            Text("连接并登录")
        }
        Spacer(Modifier.height(12.dp))
        ErrorText(state.error)
        Text(
            "手机和电脑必须同一 Wi-Fi。地址填电脑局域网 IP，不是 127.0.0.1。",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun HomeScreen(
    state: AppUiState,
    onPick: () -> Unit,
    onOpenPack: () -> Unit,
    onRestore: () -> Unit,
    onSettings: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(20.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("提词卡", fontSize = 26.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onSettings) { Text("设置") }
        }
        Spacer(Modifier.height(20.dp))
        Text("今天要做什么？", fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(6.dp))
        state.consistency?.let { check ->
            Text(
                if (check.high > 0) {
                    "跨文档检查：${check.high} 个高危 / ${check.medium} 个中危，去 Web 后台看"
                } else {
                    "跨文档检查：未发现高危冲突"
                },
                fontSize = 11.sp,
                color = if (check.high > 0) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
            Spacer(Modifier.height(8.dp))
        }

        val pack = state.pack
        if (pack != null) {
            Text(
                "已有卡包 · ${pack.cards.size} 张卡",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = onOpenPack,
                enabled = !state.busy,
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) { Text("进入已有卡包") }
            Spacer(Modifier.height(10.dp))
            OutlinedButton(
                onClick = onPick,
                enabled = !state.busy,
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) { Text("上传新资料，生成新卡包") }
            TextButton(
                onClick = onRestore,
                enabled = !state.busy && !state.restoringPack,
                modifier = Modifier.align(Alignment.CenterHorizontally),
            ) {
                if (state.restoringPack) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(6.dp))
                }
                Text("刷新服务器上的最新卡包")
            }
        } else {
            Text(
                "还没有卡包。先上传资料，或从服务器找回已发布的卡包。",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = onPick,
                enabled = !state.busy,
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) { Text("上传资料，生成第一个卡包") }
            Spacer(Modifier.height(10.dp))
            OutlinedButton(
                onClick = onRestore,
                enabled = !state.busy && !state.restoringPack,
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) {
                if (state.restoringPack) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text("从服务器查找已发布卡包")
            }
        }

        if (state.busy) {
            Spacer(Modifier.height(16.dp))
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            Text(state.status, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(4.dp))
            Text(
                "可多选 1–5 份；全部生成后合并成一个卡包（最多 20 张）。",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Spacer(Modifier.height(16.dp))
        ErrorText(state.error)
        MessageText(state.message)
    }
}

@Composable
private fun ReviewScreen(
    state: AppUiState,
    onApprove: () -> Unit,
    onApproveReplace: () -> Unit,
    onHome: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text("卡包已生成", fontSize = 28.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        Text(
            "${state.runIds.size} 个来源 · 页面 ${state.pages} · 提词卡 ${state.cards} 张",
            fontSize = 18.sp,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            "Demo 会全量批准；下一版再加逐张编辑和 Pin。",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (state.collisions.isNotEmpty()) {
            Spacer(Modifier.height(12.dp))
            Text(
                "有页面已存在：${state.collisions.joinToString()}",
                color = MaterialTheme.colorScheme.error,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "覆盖后旧页面会被这次结果替换，旧卡包仍保留在 Web 后台。",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.height(24.dp))
        if (state.collisions.isNotEmpty()) {
            Button(
                onClick = onApproveReplace,
                enabled = !state.busy,
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) {
                if (state.busy) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp))
                }
                Text("覆盖旧页面并批准")
            }
        } else {
            Button(
                onClick = onApprove,
                enabled = !state.busy,
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) {
                if (state.busy) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp))
                }
                Text("批准全部并开始")
            }
        }
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = onHome) { Text("返回首页") }
        ErrorText(state.error)
    }
}

@Composable
private fun LiveScreen(
    state: AppUiState,
    speechOn: Boolean,
    speechAvailable: Boolean,
    onToggleSpeech: () -> Unit,
    onTrigger: () -> Unit,
    onQueryChange: (String) -> Unit,
    onToggleL3: () -> Unit,
    onOpenCitations: () -> Unit,
    onCloseCitations: () -> Unit,
    onFeedback: (String) -> Unit,
    onPinPoint: (CardPoint, String, String) -> Unit,
    onSettings: () -> Unit,
) {
    val haptic = LocalHapticFeedback.current
    var selectedPoint by remember(state.matched?.qaId) {
        mutableStateOf<CardPoint?>(null)
    }
    var editingPoint by remember(state.matched?.qaId) {
        mutableStateOf<CardPoint?>(null)
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("提词卡", fontSize = 22.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onSettings) { Text("设置") }
        }

        val transcript = state.transcript.takeLast(120)
        Text(
            if (transcript.isNotBlank()) "听到：$transcript" else "未在听 · 可手动输入问题",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )

        Spacer(Modifier.height(12.dp))
        if (state.asking) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(bottom = 8.dp),
            ) {
                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
                Text("没命中卡片，正在召回原文…", fontSize = 12.sp)
            }
        }
        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            val card = state.matched
            if (card != null) {
                Column(
                    modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
                ) {
                    if (state.degraded) {
                        Text(
                            "现场组装 · 未命中预编译卡，引用 ${card.citations.size} 条",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(bottom = 8.dp),
                        )
                    }
                    if (card.ungrounded) {
                        Text(
                            "无原文依据 · LLM 通用回答，可能不可靠，重要口径请核对",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.padding(bottom = 8.dp),
                        )
                    }
                    PromptCardView(
                        card = card,
                        showL3 = state.showL3,
                        onToggleL3 = onToggleL3,
                        onOpenCitations = onOpenCitations,
                        onFeedback = onFeedback,
                        onPoint = { selectedPoint = it },
                    )
                }
            } else {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        state.message ?: "按下面的按钮，或直接输入对方的问题",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = state.query,
                onValueChange = onQueryChange,
                placeholder = { Text("手动输入问题") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            OutlinedButton(onClick = onTrigger) { Text("提词") }
        }

        Spacer(Modifier.height(10.dp))
        Button(
            onClick = {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                onTrigger()
            },
            enabled = !state.asking,
            modifier = Modifier.fillMaxWidth().height(64.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.primary,
            ),
        ) {
            Text("请求提词", fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = onToggleSpeech,
                modifier = Modifier.weight(1f),
            ) {
                Text(
                    when {
                        speechOn -> "聆听中 · 点击停止"
                        !speechAvailable -> "语音不可用"
                        else -> "开始离线语音"
                    }
                )
            }
            Text(
                "耳机键也可触发",
                fontSize = 11.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.align(Alignment.CenterVertically),
            )
        }
        Text(
            "离线语音首次使用会加载模型（约几秒）；听不到就用输入框。",
            fontSize = 10.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 2.dp),
        )
        ErrorText(state.error)
        MessageText(state.message)

        val card = state.matched
        if (state.showCitations && card != null) {
            CitationSheet(citations = card.citations, onDismiss = onCloseCitations)
        }
        selectedPoint?.let { point ->
            PointDetailSheet(
                point = point,
                onEdit = { editingPoint = point },
                onDismiss = { selectedPoint = null },
            )
        }
        editingPoint?.let { point ->
            EditPointDialog(
                point = point,
                onSave = { summary, detail ->
                    onPinPoint(point, summary, detail)
                    editingPoint = null
                    selectedPoint = null
                },
                onDismiss = { editingPoint = null },
            )
        }
    }
}

@Composable
private fun PromptCardView(
    card: PromptCard,
    showL3: Boolean,
    onToggleL3: () -> Unit,
    onOpenCitations: () -> Unit,
    onFeedback: (String) -> Unit,
    onPoint: (CardPoint) -> Unit,
) {
    var showL2 by remember(card.qaId) { mutableStateOf(card.confidence != "red") }
    val color = confidenceColor(card.confidence)

    Row(verticalAlignment = Alignment.Top) {
        Box(
            modifier = Modifier
                .padding(top = 6.dp)
                .size(9.dp)
                .background(color, RoundedCornerShape(50)),
        )
        Spacer(Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(card.question, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Text(
                (if (card.calibrated) "实测" else "规则") +
                    "置信度 ${card.confidenceScore}% · 依据 ${card.citations.size} 条",
                fontSize = 11.sp,
                color = color,
            )
        }
    }
    Spacer(Modifier.height(10.dp))

    if (card.confidence == "red" && !showL2 && !card.ungrounded) {
        Surface(
            color = Color(0xFF3A1E1E),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(Modifier.padding(14.dp)) {
                Text("先兜底", color = Color(0xFFFFB4AB), fontSize = 12.sp)
                Spacer(Modifier.height(6.dp))
                Text(card.fallback, color = Color(0xFFFFDAD6))
                Spacer(Modifier.height(6.dp))
                TextButton(onClick = { showL2 = true }) { Text("展开骨架") }
            }
        }
        Spacer(Modifier.height(10.dp))
    }

    Row(
        modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        card.l1.forEach { keyword ->
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(50),
            ) {
                Text(
                    keyword,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    fontSize = 13.sp,
                )
            }
        }
    }

    if (showL2) {
        Spacer(Modifier.height(12.dp))
        card.l2.forEachIndexed { index, line ->
            val point = card.points.getOrNull(index)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(enabled = point != null) {
                        point?.let(onPoint)
                    }
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.Top,
            ) {
                Text(
                    "${index + 1}.",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.width(22.dp),
                )
                Text(
                    line,
                    fontSize = 16.sp,
                    lineHeight = 23.sp,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f),
                )
                if (point != null) {
                    Text(
                        "展开 ›",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(start = 6.dp, top = 2.dp),
                    )
                }
            }
        }
    }

    Spacer(Modifier.height(12.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        TextButton(onClick = onOpenCitations) {
            Text("查看依据 (${card.citations.size})")
        }
        TextButton(onClick = onToggleL3) {
            Text(if (showL3) "收起全文" else "展开全文")
        }
    }

    if (showL3) {
        Surface(
            color = MaterialTheme.colorScheme.surface,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                cleanMarkdown(card.l3),
                modifier = Modifier.padding(14.dp),
                fontSize = 14.sp,
                lineHeight = 21.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
    }

    if (card.doNotSay.isNotEmpty()) {
        Spacer(Modifier.height(8.dp))
        Text(
            "不要说：${card.doNotSay.joinToString(" / ")}",
            color = MaterialTheme.colorScheme.error,
            fontSize = 12.sp,
        )
    }

    Spacer(Modifier.height(10.dp))
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        TextButton(onClick = { onFeedback("有用") }) { Text("有用") }
        TextButton(onClick = { onFeedback("没用") }) { Text("没用") }
        TextButton(onClick = { onFeedback("用了兜底") }) { Text("用了兜底") }
    }
}

@Composable
private fun PointDetailSheet(
    point: CardPoint,
    onEdit: () -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "论点 ${point.index}",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (point.pinned) {
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "已固定",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                Spacer(Modifier.weight(1f))
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(50),
                ) {
                    Text(
                        "置信度 ${point.score}%",
                        modifier = Modifier.padding(horizontal = 9.dp, vertical = 3.dp),
                        fontSize = 11.sp,
                        color = confidenceColor(point.confidence),
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(point.summary, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(14.dp))
            Text(
                "展开说明",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                point.detail,
                fontSize = 15.sp,
                lineHeight = 23.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )

            if (point.followups.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                Text(
                    "可能被追问",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.primary,
                )
                point.followups.forEach { followup ->
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Q：${followup.question}",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    if (followup.answer.isNotBlank()) {
                        Text(
                            "A：${followup.answer}",
                            fontSize = 14.sp,
                            lineHeight = 21.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            if (point.citations.isNotEmpty()) {
                Spacer(Modifier.height(16.dp))
                Text(
                    "依据",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.primary,
                )
                point.citations.forEach { citation ->
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "「${citation.quote}」",
                        fontSize = 13.sp,
                        lineHeight = 20.sp,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        citation.pageLabel,
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            TextButton(
                onClick = onEdit,
                modifier = Modifier.align(Alignment.CenterHorizontally),
            ) { Text("编辑并固定这条") }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun EditPointDialog(
    point: CardPoint,
    onSave: (String, String) -> Unit,
    onDismiss: () -> Unit,
) {
    var summary by remember(point.index, point.summary) { mutableStateOf(point.summary) }
    var detail by remember(point.index, point.detail) { mutableStateOf(point.detail) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("编辑论点 ${point.index}") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = summary,
                    onValueChange = { summary = it },
                    label = { Text("摘要") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = detail,
                    onValueChange = { detail = it },
                    label = { Text("展开说明") },
                    minLines = 4,
                    maxLines = 8,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "固定后重编译不会覆盖；会同步到 Web 后台。",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(summary, detail) }) { Text("保存并固定") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        },
    )
}

@Composable
private fun CitationSheet(citations: List<Citation>, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 8.dp),
        ) {
            Text("依据", fontSize = 22.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            if (citations.isEmpty()) {
                Text("这张卡没有可展示的引用", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                LazyColumn(modifier = Modifier.heightIn(max = 480.dp)) {
                    items(citations) { citation ->
                        Column(Modifier.padding(vertical = 10.dp)) {
                            Text(
                                "「${citation.quote}」",
                                fontSize = 15.sp,
                                lineHeight = 22.sp,
                                color = MaterialTheme.colorScheme.onSurface,
                            )
                            Spacer(Modifier.height(4.dp))
                            Text(
                                "${citation.pageLabel} · ${citation.block}",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun SettingsScreen(
    state: AppUiState,
    onSave: (String) -> Unit,
    onLogout: () -> Unit,
    onClearPack: () -> Unit,
    onBack: () -> Unit,
    onCheckUpdate: () -> Unit,
    onDismissUpdate: () -> Unit,
    onToggleUngrounded: (Boolean) -> Unit,
) {
    var baseUrl by rememberSaveable { mutableStateOf(state.baseUrl) }
    val context = LocalContext.current
    state.update?.let { update ->
        AlertDialog(
            onDismissRequest = onDismissUpdate,
            title = { Text("发现新版本 ${update.versionName}") },
            text = {
                Text(
                    (update.notes ?: "有新版本可用。") +
                        "\n\n下载后需要系统确认安装；不会静默覆盖。"
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    val url = state.baseUrl.trimEnd('/') + update.downloadUrl
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    onDismissUpdate()
                }) { Text("下载") }
            },
            dismissButton = {
                TextButton(onClick = onDismissUpdate) { Text("稍后") }
            },
        )
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("设置", fontSize = 26.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onBack) { Text("返回") }
        }
        Spacer(Modifier.height(20.dp))
        OutlinedTextField(
            value = baseUrl,
            onValueChange = { baseUrl = it },
            label = { Text("后端地址") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(10.dp))
        Button(
            onClick = { onSave(baseUrl) },
            modifier = Modifier.fillMaxWidth().height(48.dp),
        ) { Text("保存地址") }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(
            onClick = onCheckUpdate,
            enabled = !state.checkingUpdate,
            modifier = Modifier.fillMaxWidth().height(48.dp),
        ) {
            if (state.checkingUpdate) {
                CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
            }
            Text("检查更新")
        }
        Spacer(Modifier.height(16.dp))
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("无依据也允许 LLM 回答")
                Text(
                    "没召回原文时，用通用知识回答并标红；默认关闭。",
                    fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(
                checked = state.allowUngrounded,
                onCheckedChange = onToggleUngrounded,
            )
        }
        Spacer(Modifier.height(24.dp))
        OutlinedButton(
            onClick = onClearPack,
            modifier = Modifier.fillMaxWidth().height(48.dp),
        ) { Text("清除本地卡包") }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(
            onClick = onLogout,
            modifier = Modifier.fillMaxWidth().height(48.dp),
        ) { Text("退出登录") }
        Spacer(Modifier.height(24.dp))
        Text(
            "API key 只在服务端；App 只保存 token 和最近一次卡包。\n" +
                "局域网 Demo 使用 HTTP，正式环境必须 HTTPS。",
            fontSize = 12.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        MessageText(state.message)
        ErrorText(state.error)
    }
}

@Composable
private fun ErrorText(message: String?) {
    if (message.isNullOrBlank()) return
    Text(
        message,
        color = MaterialTheme.colorScheme.error,
        fontSize = 13.sp,
        modifier = Modifier.padding(top = 8.dp),
    )
}

@Composable
private fun MessageText(message: String?) {
    if (message.isNullOrBlank()) return
    Text(
        message,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        fontSize = 13.sp,
        modifier = Modifier.padding(top = 8.dp),
    )
}

private fun confidenceColor(level: String): Color = when (level) {
    "green" -> Color(0xFF66BB6A)
    "red" -> Color(0xFFEF5350)
    else -> Color(0xFFFFC107)
}

private fun cleanMarkdown(text: String): String =
    text.lines()
        .filterNot { it.startsWith("#") }
        .joinToString("\n")
        .replace("**", "")
        .replace("`", "")
        .trim()
