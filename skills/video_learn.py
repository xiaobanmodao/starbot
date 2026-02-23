"""Video learning skill — multi-platform video comprehension with subtitle, Whisper transcription,
thumbnail vision analysis, playlist support, and deduplication.

Pipeline:
    URL → yt-dlp metadata → subtitle attempt → (Whisper fallback if no subs) →
    thumbnail vision description → LLM summarization → memory storage

Supported platforms (via yt-dlp, 1000+):
    YouTube, Bilibili, Twitter/X, TikTok, Douyin, Weibo, Vimeo, Twitch, etc.
"""

META = {
    "name": "video_learn",
    "version": "1.0.0",
    "description": (
        "视频学习系统：自动提取字幕或语音转写（Whisper），结合画面理解，"
        "提炼知识存入记忆库。支持 1000+ 平台、播放列表批量学习、去重检测"
    ),
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "video_info",
            "description": (
                "获取视频基本信息：标题、频道、时长、字幕语言列表、平台，"
                "用于在学习前了解视频概况"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "视频 URL（YouTube、Bilibili、Twitter等均可）"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learn_video_plus",
            "description": (
                "完整学习一个视频并存入记忆库。\n"
                "处理流程：\n"
                "1. 获取视频元数据（标题/频道/时长）\n"
                "2. 尝试获取字幕（支持手动字幕 + 自动字幕）\n"
                "3. 若无字幕：自动下载音频并用 Whisper 语音转写\n"
                "4. 下载视频封面，发给视觉模型描述画面内容\n"
                "5. LLM 综合字幕/转写 + 画面描述，提炼结构化笔记\n"
                "6. 按标签存入记忆库（可检索）"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "视频 URL"},
                    "topic": {
                        "type": "string",
                        "description": "学习主题/标签，便于记忆库检索，如 'Python异步编程'",
                        "default": "",
                    },
                    "lang": {
                        "type": "string",
                        "description": "优先字幕语言：zh（中文）/ en（英文）/ auto（自动），默认 auto",
                        "default": "auto",
                    },
                    "whisper_model": {
                        "type": "string",
                        "description": "Whisper 模型大小（无字幕时启用）：tiny/base/small/medium，默认 base（首次使用自动下载）",
                        "default": "base",
                    },
                    "analyze_thumbnail": {
                        "type": "boolean",
                        "description": "是否用视觉模型分析视频封面，默认 true",
                        "default": True,
                    },
                    "force_relearn": {
                        "type": "boolean",
                        "description": "若已学过此视频，是否强制重新学习，默认 false",
                        "default": False,
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learn_playlist",
            "description": "批量学习播放列表或频道中的多个视频，逐个处理并存入记忆库",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "播放列表或频道 URL（YouTube playlist、Bilibili 合集等）",
                    },
                    "max_videos": {
                        "type": "integer",
                        "description": "最多学习几个视频，默认 5，最多 20",
                        "default": 5,
                    },
                    "topic": {
                        "type": "string",
                        "description": "统一学习主题标签",
                        "default": "",
                    },
                    "lang": {
                        "type": "string",
                        "description": "字幕优先语言，默认 auto",
                        "default": "auto",
                    },
                    "skip_learned": {
                        "type": "boolean",
                        "description": "是否跳过已学过的视频，默认 true",
                        "default": True,
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_video_learned",
            "description": "检查某个视频是否已经学习过（查询记忆库），避免重复学习",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "视频 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transcribe_audio",
            "description": (
                "仅对视频/音频进行语音转写（不存入记忆），返回完整文字稿。"
                "适合需要原始转写文本再做进一步处理的场景"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "视频/音频 URL，或本地文件路径"},
                    "model": {
                        "type": "string",
                        "description": "Whisper 模型：tiny/base/small/medium，默认 base",
                        "default": "base",
                    },
                    "language": {
                        "type": "string",
                        "description": "指定语言（留空自动检测）：zh / en / ja / ko / fr 等",
                        "default": "",
                    },
                },
                "required": ["url"],
            },
        },
    },
]

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

log = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORK_DIR = os.path.join(_BASE_DIR, "logs", "video_learn")

_LEARNED_URLS: set[str] = set()   # in-memory dedup cache (also checks DB)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_proxies_env() -> dict[str, str]:
    """Return proxy env vars for subprocess calls."""
    try:
        from config import config
        proxy = getattr(config, "PROXY", None)
        if proxy:
            return {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, **os.environ}
    except Exception:
        pass
    return os.environ.copy()


def _url_id(url: str) -> str:
    """Short hash of URL for filenames and dedup."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _ytdlp_cmd() -> list[str]:
    """Prefer system yt-dlp; fall back to python -m yt_dlp."""
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]
    return [sys.executable, "-m", "yt_dlp"]


def _ytdlp(*args, timeout: int = 120, extra_opts: list | None = None) -> subprocess.CompletedProcess:
    env = _get_proxies_env()
    cmd = _ytdlp_cmd() + (extra_opts or []) + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def _is_youtube(url: str) -> bool:
    return any(d in url for d in ("youtube.com", "youtu.be", "yt.be"))


def _is_bilibili(url: str) -> bool:
    return any(d in url for d in ("bilibili.com", "b23.tv"))


def _ytdlp_with_cookie_fallback(*args, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run yt-dlp; on YouTube auth/rate-limit errors retry with browser cookies."""
    res = _ytdlp(*args, timeout=timeout)
    if res.returncode == 0:
        return res

    stderr_low = res.stderr.lower()
    blocked = any(kw in stderr_low for kw in (
        "sign in", "429", "too many requests", "bot", "verify you are human",
        "private video", "confirm your age",
    ))
    if not blocked:
        return res

    log.info("yt-dlp blocked, retrying with browser cookies...")
    for browser in ("chrome", "firefox", "edge", "chromium"):
        res2 = _ytdlp("--cookies-from-browser", browser, *args, timeout=timeout)
        if res2.returncode == 0:
            log.info("Cookie retry succeeded with browser: %s", browser)
            return res2
    log.warning("All cookie fallbacks failed")
    return res  # return original failure


def _get_mem():
    from memory.store import MemoryStore
    return MemoryStore()


def _get_llm():
    from config import config
    from core.adapter import UniversalLLM
    return UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)


def _is_learned(url: str) -> bool:
    if url in _LEARNED_URLS:
        return True
    mem = _get_mem()
    results = mem.search(f"视频URL:{url[:60]}", limit=3)
    if any(url[:50] in r.get("content", "") for r in results):
        _LEARNED_URLS.add(url)
        return True
    return False


def _fmt_duration(seconds: int | float) -> str:
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── Step 1: Video metadata ────────────────────────────────────────────────────

def _fetch_info(url: str) -> dict:
    """Get video metadata via yt-dlp --dump-json."""
    res = _ytdlp_with_cookie_fallback(
        "--dump-json", "--no-download", "--no-playlist",
        "--extractor-retries", "3", url, timeout=45,
    )
    if res.returncode != 0 or not res.stdout.strip():
        log.warning("video_info failed: %s", res.stderr[:300])
        return {}
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return {}


def _info_summary(info: dict) -> str:
    title = info.get("title", "未知标题")
    channel = info.get("uploader") or info.get("channel") or "未知频道"
    duration = info.get("duration")
    dur_str = _fmt_duration(duration) if duration else "未知"
    upload = (info.get("upload_date") or "")[:8]
    views = info.get("view_count")
    platform = info.get("extractor_key") or info.get("extractor") or "未知平台"
    sub_langs = list((info.get("subtitles") or {}).keys())
    auto_sub_langs = list((info.get("automatic_captions") or {}).keys())
    desc = (info.get("description") or "")[:200]

    parts = [
        f"📺 {title}",
        f"   频道：{channel}  |  时长：{dur_str}  |  平台：{platform}",
    ]
    if upload:
        parts.append(f"   上传日期：{upload[:4]}-{upload[4:6]}-{upload[6:]}")
    if views:
        parts.append(f"   播放量：{views:,}")
    if sub_langs:
        parts.append(f"   手动字幕：{', '.join(sub_langs[:8])}")
    if auto_sub_langs:
        parts.append(f"   自动字幕：{', '.join(auto_sub_langs[:8])}")
    if not sub_langs and not auto_sub_langs:
        parts.append("   字幕：无（将使用 Whisper 语音转写）")
    if desc.strip():
        parts.append(f"   简介：{desc}{'…' if len(info.get('description',''))>200 else ''}")
    return "\n".join(parts)


# ── Step 2: Subtitle extraction ───────────────────────────────────────────────

def _fetch_subtitles(url: str, lang: str, work_dir: str) -> str | None:
    """Download subtitles. Returns cleaned text or None.

    Handles platform differences:
    - YouTube: zh-Hans / en auto-captions
    - Bilibili: zh / ai-zh (AI-generated) — no zh-Hans
    - Others: best-effort
    """
    sub_dir = os.path.join(work_dir, "subs")
    os.makedirs(sub_dir, exist_ok=True)
    for f in os.listdir(sub_dir):
        try:
            os.remove(os.path.join(sub_dir, f))
        except OSError:
            pass

    bilibili = _is_bilibili(url)

    # Language priority per platform
    if lang == "auto":
        if bilibili:
            # Bilibili uses plain "zh" codes; "ai-zh" is their AI-generated CC
            try_langs = ["zh", "zh-CN", "ai-zh", "en"]
        else:
            try_langs = ["zh-Hans", "zh", "zh-CN", "zh-TW", "en"]
    else:
        try_langs = [lang, "en"] if lang != "en" else ["en"]

    # Extra args for Bilibili
    bili_extra: list[str] = (
        ["--extractor-args", "bilibili:prefer_multi_lang_subtitle=True"]
        if bilibili else []
    )

    srt_files: list[str] = []
    for try_lang in try_langs:
        _ytdlp(
            "--skip-download",
            "--write-sub", "--write-auto-sub",
            "--sub-lang", try_lang,
            "--sub-format", "srt/vtt/json3",   # prefer srt, accept vtt or json3
            "--convert-subs", "srt",
            "--no-playlist",
            "--extractor-retries", "3",
            "-o", os.path.join(sub_dir, "sub"),
            url,
            extra_opts=bili_extra,
            timeout=90,
        )
        srt_files = [f for f in os.listdir(sub_dir) if f.endswith(".srt")]
        if srt_files:
            break

    # Also accept any subtitle format if SRT conversion failed
    if not srt_files:
        all_subs = [
            f for f in os.listdir(sub_dir)
            if f.endswith((".vtt", ".ass", ".json3", ".lrc"))
        ]
        if all_subs:
            log.info("No SRT found but got %s, attempting parse", all_subs[0])
            srt_files = all_subs

    if not srt_files:
        return None

    sub_path = os.path.join(sub_dir, srt_files[0])
    with open(sub_path, encoding="utf-8", errors="ignore") as fh:
        raw = fh.read()

    # Clean SRT/VTT formatting
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.isdigit():
            continue
        # Timestamp lines: 00:00:01,000 --> or 00:00:01.000 -->
        if re.match(r"\d{1,2}:\d{2}:\d{2}[,\.]\d{3}\s*-->", stripped):
            continue
        if re.match(r"<\d{2}:\d{2}:\d{2}", stripped):
            continue
        if stripped.startswith("WEBVTT") or stripped.startswith("NOTE "):
            continue
        # Remove inline tags: <i>, </i>, <c.colorName>, {\\an8} etc.
        cleaned = re.sub(r"<[^>]+>", "", stripped)
        cleaned = re.sub(r"\{[^}]+\}", "", cleaned).strip()
        if cleaned:
            lines.append(cleaned)

    # Deduplicate consecutive identical lines
    deduped: list[str] = []
    prev = None
    for line in lines:
        if line != prev:
            deduped.append(line)
            prev = line

    text = "\n".join(deduped)
    return text if len(text) > 50 else None


# ── Step 3: Whisper transcription ─────────────────────────────────────────────

def _whisper_transcribe(url_or_path: str, model_size: str = "base", language: str = "") -> str | None:
    """Download audio (if URL) then transcribe with faster-whisper."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        # If it's a URL, download audio first
        if url_or_path.startswith("http"):
            audio_path = os.path.join(tmpdir, "audio.mp3")
            res = _ytdlp_with_cookie_fallback(
                "-x", "--audio-format", "mp3",
                "--audio-quality", "5",  # 128kbps, good enough for speech
                "--no-playlist",
                "--extractor-retries", "3",
                "-o", audio_path,
                url_or_path,
                timeout=300,
            )
            if res.returncode != 0 or not os.path.exists(audio_path):
                # yt-dlp may append file extension; search for any audio file
                audio_files = [
                    f for f in os.listdir(tmpdir)
                    if f.endswith((".mp3", ".m4a", ".webm", ".opus", ".ogg", ".wav"))
                ]
                if not audio_files:
                    log.warning("Audio download failed: %s", res.stderr[:300])
                    return None
                audio_path = os.path.join(tmpdir, audio_files[0])
        else:
            audio_path = url_or_path

        if not os.path.exists(audio_path):
            return None

        log.info("Transcribing %s with faster-whisper model=%s", audio_path, model_size)
        try:
            # Use int8 for CPU efficiency, float16 if GPU available
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            kwargs = {"beam_size": 5}
            if language:
                kwargs["language"] = language

            segments, info = model.transcribe(audio_path, **kwargs)
            detected_lang = getattr(info, "language", "")
            log.info("Detected language: %s", detected_lang)

            text_parts = []
            for seg in segments:
                text_parts.append(seg.text.strip())
            return " ".join(text_parts) if text_parts else None
        except Exception as e:
            log.error("Whisper transcription failed: %s", e)
            return None


# ── Step 4: Thumbnail vision analysis ────────────────────────────────────────

def _analyze_thumbnail(url: str, info: dict, work_dir: str) -> str:
    """Download thumbnail and describe it with vision LLM."""
    thumb_dir = os.path.join(work_dir, "thumb")
    os.makedirs(thumb_dir, exist_ok=True)

    # Try getting thumbnail URL from info first
    thumb_url = info.get("thumbnail") or ""
    if not thumb_url:
        # Check thumbnails list
        thumbs = info.get("thumbnails", [])
        if thumbs:
            # Get highest quality
            thumb_url = max(thumbs, key=lambda t: t.get("width", 0) * t.get("height", 0)).get("url", "")

    if not thumb_url:
        return ""

    try:
        import requests
        r = requests.get(thumb_url, timeout=10)
        r.raise_for_status()
        thumb_path = os.path.join(thumb_dir, "thumb.jpg")
        with open(thumb_path, "wb") as f:
            f.write(r.content)
    except Exception as e:
        log.warning("Thumbnail download failed: %s", e)
        return ""

    # Resize to reduce token usage
    try:
        from PIL import Image
        import io, base64
        img = Image.open(thumb_path)
        img.thumbnail((640, 360))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        img_b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        log.warning("Thumbnail processing failed: %s", e)
        return ""

    # Call vision LLM
    try:
        from config import config
        from core.adapter import UniversalLLM
        llm = UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)

        title = info.get("title", "")
        prompt = (
            f"这是视频《{title}》的封面图片。"
            "请简要描述：1) 画面主要内容；2) 可能的视频类型（教程/讲座/演示等）；"
            "3) 任何可见的文字或关键信息。50字以内。"
        )

        # Build vision message (OpenAI format)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_b64}",
                            "detail": "low",
                        },
                    },
                ],
            }
        ]
        response = llm.client.chat.completions.create(
            model=llm.model,
            messages=messages,
            max_tokens=150,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        log.debug("Vision analysis failed (model may not support images): %s", e)
        return ""


# ── Step 5: LLM summarization ─────────────────────────────────────────────────

def _summarize_video(
    transcript: str,
    info: dict,
    topic: str,
    thumbnail_desc: str,
) -> str:
    """Generate structured notes from transcript + metadata."""
    from core.adapter import UniversalLLM
    from config import config
    llm = UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)

    title = info.get("title", "未知视频")
    channel = info.get("uploader") or info.get("channel") or ""
    duration = info.get("duration")
    dur_str = _fmt_duration(duration) if duration else ""

    # Chunk long transcripts for parallel processing
    chunk_size = 7000
    chunks = [transcript[i:i+chunk_size] for i in range(0, len(transcript), chunk_size)]
    total_chunks = len(chunks)

    def _summarize_chunk(idx_chunk):
        idx, chunk = idx_chunk
        prompt = (
            f"视频：《{title}》（{channel}）{dur_str}\n"
            + (f"学习主题：{topic}\n" if topic else "")
            + (f"画面描述：{thumbnail_desc}\n" if thumbnail_desc and idx == 0 else "")
            + f"\n这是第 {idx+1}/{total_chunks} 段字幕/转写内容：\n{chunk}\n\n"
            "请提炼这段内容的核心知识点（3-8条），每条要点独立完整，可脱离原文理解。"
            "用 JSON 数组格式返回：[\"要点1\", \"要点2\", ...]"
        )
        try:
            resp = llm.chat(prompt)
            m = re.search(r"\[.*?\]", resp, re.DOTALL)
            if m:
                items = json.loads(m.group())
                return [str(s) for s in items if isinstance(s, str)]
        except Exception:
            pass
        return [chunk[:200] + "…"]

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(4, total_chunks)) as ex:
        all_points = []
        for pts in ex.map(_summarize_chunk, enumerate(chunks)):
            all_points.extend(pts)

    # Final synthesis if multiple chunks
    if total_chunks > 1 and len(all_points) > 8:
        try:
            all_text = "\n".join(f"• {p}" for p in all_points)
            final_prompt = (
                f"以下是《{title}》的各段要点汇总：\n{all_text[:5000]}\n\n"
                "请整合为一份结构化学习笔记，要求：\n"
                "1. 按主题分组\n2. 去除重复内容\n3. 保留最核心的8-15个要点\n"
                "输出格式：JSON数组 [\"要点1\", ...]"
            )
            resp = llm.chat(final_prompt)
            m = re.search(r"\[.*?\]", resp, re.DOTALL)
            if m:
                all_points = json.loads(m.group())
        except Exception:
            pass

    return all_points


# ── Core learn function ───────────────────────────────────────────────────────

def _do_learn(url: str, topic: str, lang: str, whisper_model: str,
              analyze_thumbnail: bool, force_relearn: bool) -> dict:
    os.makedirs(_WORK_DIR, exist_ok=True)
    uid = _url_id(url)
    work_dir = os.path.join(_WORK_DIR, uid)
    os.makedirs(work_dir, exist_ok=True)

    # ── Dedup check ──
    if not force_relearn and _is_learned(url):
        return {
            "ok": True,
            "result": f"✅ 此视频已学习过（传 force_relearn=true 可重新学习）\n{url}",
        }

    # ── Metadata ──
    log.info("Fetching video info: %s", url[:80])
    info = _fetch_info(url)
    if not info:
        hint = ""
        if _is_youtube(url):
            hint = "\nYouTube 可能需要登录验证；已自动尝试浏览器 Cookie，若仍失败请确认 Chrome/Firefox 已登录 YouTube"
        elif _is_bilibili(url):
            hint = "\nB站部分视频需要大会员，请确认账号权限"
        return {"ok": False, "result": f"无法获取视频信息，请检查 URL 是否正确：{url}{hint}"}

    title = info.get("title", "未知")
    duration = info.get("duration") or 0
    channel = info.get("uploader") or info.get("channel") or "未知频道"
    summary_lines = [f"📚 开始学习：《{title}》", f"   频道：{channel}  时长：{_fmt_duration(duration)}"]

    # ── Subtitles ──
    transcript_source = ""
    log.info("Trying subtitles for: %s", title)
    transcript = _fetch_subtitles(url, lang, work_dir)

    if transcript and len(transcript.strip()) > 100:
        transcript_source = "字幕"
        summary_lines.append(f"✅ 获取字幕成功（{len(transcript)} 字符）")
    else:
        summary_lines.append("⚠️  无可用字幕，启动 Whisper 语音转写…")
        log.info("No subtitles, starting Whisper transcription (model=%s)", whisper_model)
        transcript = _whisper_transcribe(url, model_size=whisper_model)
        if transcript and len(transcript.strip()) > 50:
            transcript_source = f"Whisper({whisper_model})"
            summary_lines.append(f"✅ 语音转写完成（{len(transcript)} 字符）")
        else:
            return {
                "ok": False,
                "result": (
                    "\n".join(summary_lines)
                    + "\n\n❌ 无法获取视频文字内容（无字幕，语音转写也失败）\n"
                    "可能原因：视频为纯音乐/无语音内容，或 yt-dlp 无法下载音频"
                ),
            }

    # ── Thumbnail analysis ──
    thumb_desc = ""
    if analyze_thumbnail:
        log.info("Analyzing thumbnail for: %s", title)
        thumb_desc = _analyze_thumbnail(url, info, work_dir)
        if thumb_desc:
            summary_lines.append(f"🖼️  封面分析：{thumb_desc}")

    # ── LLM Summarization ──
    log.info("Summarizing %d chars of transcript in %d chunks...", len(transcript), max(1, len(transcript)//7000))
    points = _summarize_video(transcript, info, topic or title, thumb_desc)

    if not points:
        return {"ok": False, "result": "LLM 摘要失败，未能提取知识点"}

    # ── Save to memory ──
    mem = _get_mem()
    tag = topic or title[:40]
    platform = info.get("extractor_key", "video")
    url_short = url[:80]

    prefix = f"[视频学习][{tag}][{platform}] 《{title}》 作者:{channel} | 视频URL:{url_short} |"
    saved, skipped = 0, 0
    for point in points:
        if isinstance(point, str) and len(point.strip()) > 5:
            content = f"{prefix} {point.strip()}"
            if mem.save("knowledge", content):
                saved += 1
            else:
                skipped += 1

    _LEARNED_URLS.add(url)

    summary_lines += [
        f"\n✅ 学习完成！",
        f"   来源：{transcript_source}",
        f"   提炼要点：{len(points)} 条",
        f"   新增记忆：{saved} 条（已存在跳过：{skipped} 条）",
        f"   学习标签：{tag}",
        "",
        "📌 要点预览：",
    ]
    for i, p in enumerate(points[:5], 1):
        summary_lines.append(f"  {i}. {str(p)[:120]}")
    if len(points) > 5:
        summary_lines.append(f"  …（共 {len(points)} 条，已全部存入记忆库）")

    return {"ok": True, "result": "\n".join(summary_lines)}


# ── Playlist helper ───────────────────────────────────────────────────────────

def _get_playlist_urls(url: str, max_n: int) -> list[dict]:
    """Extract individual video URLs from a playlist."""
    res = _ytdlp(
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(max_n),
        url,
        timeout=60,
    )
    if res.returncode != 0:
        return []
    entries = []
    for line in res.stdout.strip().splitlines():
        try:
            d = json.loads(line)
            video_url = d.get("url") or d.get("webpage_url") or ""
            if not video_url.startswith("http"):
                # Reconstruct from ID
                vid_id = d.get("id", "")
                if vid_id:
                    extractor = d.get("ie_key", "").lower()
                    if "youtube" in extractor or not extractor:
                        video_url = f"https://www.youtube.com/watch?v={vid_id}"
                    elif "bilibili" in extractor:
                        video_url = f"https://www.bilibili.com/video/{vid_id}"
            if video_url.startswith("http"):
                entries.append({"url": video_url, "title": d.get("title", "")})
        except json.JSONDecodeError:
            continue
    return entries[:max_n]


# ── Execute ───────────────────────────────────────────────────────────────────

def execute(name: str, args: dict) -> dict:

    if name == "video_info":
        url = args["url"]
        info = _fetch_info(url)
        if not info:
            return {"ok": False, "result": f"无法获取视频信息：{url}\n请检查 URL 是否正确，或 yt-dlp 是否安装"}
        return {"ok": True, "result": _info_summary(info)}

    if name == "learn_video_plus":
        url = args["url"]
        topic = str(args.get("topic", ""))
        lang = str(args.get("lang", "auto"))
        whisper_model = str(args.get("whisper_model", "base"))
        analyze_thumbnail = bool(args.get("analyze_thumbnail", True))
        force_relearn = bool(args.get("force_relearn", False))

        return _do_learn(url, topic, lang, whisper_model, analyze_thumbnail, force_relearn)

    if name == "learn_playlist":
        url = args["url"]
        max_videos = min(int(args.get("max_videos", 5)), 20)
        topic = str(args.get("topic", ""))
        lang = str(args.get("lang", "auto"))
        skip_learned = bool(args.get("skip_learned", True))

        log.info("Fetching playlist: %s (max %d)", url, max_videos)
        entries = _get_playlist_urls(url, max_videos)
        if not entries:
            return {"ok": False, "result": "无法获取播放列表中的视频，请检查 URL 或网络"}

        lines = [f"📋 播放列表共 {len(entries)} 个视频，开始逐个学习…", ""]
        learned, skipped_dup, failed = 0, 0, 0

        for i, entry in enumerate(entries, 1):
            v_url = entry["url"]
            v_title = entry.get("title", v_url)
            lines.append(f"{i}/{len(entries)}. 《{v_title[:60]}》")

            if skip_learned and _is_learned(v_url):
                lines.append("   ⏭️  已学习，跳过")
                skipped_dup += 1
                continue

            result = _do_learn(
                v_url, topic or v_title[:30], lang,
                whisper_model="base",
                analyze_thumbnail=False,   # Skip thumbnails in batch to save time
                force_relearn=False,
            )
            if result["ok"]:
                lines.append("   ✅ 学习完成")
                learned += 1
            else:
                lines.append(f"   ❌ 失败：{result['result'][:80]}")
                failed += 1

            time.sleep(1)  # Be polite

        lines += [
            "",
            f"📊 播放列表学习完毕：",
            f"   ✅ 成功 {learned} 个  ⏭️ 跳过 {skipped_dup} 个  ❌ 失败 {failed} 个",
        ]
        return {"ok": True, "result": "\n".join(lines)}

    if name == "check_video_learned":
        url = args["url"]
        if _is_learned(url):
            return {"ok": True, "result": f"✅ 已学习过此视频\n{url}"}
        return {"ok": True, "result": f"📭 尚未学习此视频\n{url}\n\n可以用 learn_video_plus 来学习它"}

    if name == "transcribe_audio":
        url = args["url"]
        model = str(args.get("model", "base"))
        language = str(args.get("language", ""))

        try:
            from faster_whisper import WhisperModel as _
        except ImportError:
            return {
                "ok": False,
                "result": "faster-whisper 未安装。请运行：uv add faster-whisper",
            }

        log.info("Transcribing: %s (model=%s, lang=%s)", url[:60], model, language or "auto")
        transcript = _whisper_transcribe(url, model_size=model, language=language)
        if not transcript:
            return {"ok": False, "result": "转写失败：无法下载音频或转写结果为空"}

        return {
            "ok": True,
            "result": (
                f"✅ 转写完成（{len(transcript)} 字符）\n"
                f"模型：{model}  语言：{language or '自动检测'}\n\n"
                + transcript[:5000]
                + ("\n…（已截断，全文共 %d 字符）" % len(transcript) if len(transcript) > 5000 else "")
            ),
        }

    return {"ok": False, "result": f"Unknown tool: {name}"}
