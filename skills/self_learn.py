"""Self-learning skill — knowledge management, gap analysis, and LLM-powered distillation."""

META = {
    "name": "self_learn",
    "version": "1.0.0",
    "description": "自我学习系统：知识库分析、学习计划生成、LLM 知识提炼、学习目标跟踪",
    "author": "starbot",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "knowledge_map",
            "description": "查看当前记忆库中已掌握的知识分布：各类别条目数量、最近学习的主题",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_topic",
            "description": (
                "分析某个主题的已知程度：从记忆库检索相关知识，"
                "评估知识覆盖深度，列出可能的知识空白（gaps），"
                "推荐下一步应重点学习的子主题"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "要分析的主题，如 '量子计算'、'Python 异步编程'"},
                    "depth": {
                        "type": "string",
                        "description": "分析深度：quick（快速）/ deep（深度），默认 quick",
                        "default": "quick",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "distill_knowledge",
            "description": (
                "用 LLM 从原始文本中提炼核心知识点并自动存入记忆库。"
                "适合处理长篇文章、网页内容、视频字幕等，"
                "自动去掉冗余只保留精华，每条知识点独立完整可检索"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "知识所属主题/标签"},
                    "raw_text": {"type": "string", "description": "待提炼的原始文本（最多约 8000 字符）"},
                    "source": {"type": "string", "description": "来源说明，如 URL 或书名", "default": ""},
                    "category": {
                        "type": "string",
                        "description": "存入记忆的类别：knowledge / skill / preference，默认 knowledge",
                        "default": "knowledge",
                    },
                },
                "required": ["topic", "raw_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_learning_goal",
            "description": "设置一个学习目标，记录到记忆库，便于后续追踪进度",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "学习目标，如 '掌握 Rust 所有权机制'"},
                    "deadline": {"type": "string", "description": "目标截止日期（可选），如 '2025-03-01'", "default": ""},
                    "subtopics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "拆解的子主题列表（可选）",
                    },
                },
                "required": ["goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "review_knowledge",
            "description": "检索并汇总记忆库中关于某个主题的所有已知知识，便于复习",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "要复习的主题"},
                    "limit": {"type": "integer", "description": "最多返回条目数，默认 20", "default": 20},
                },
                "required": ["topic"],
            },
        },
    },
]

import sqlite3

_mem_path: str | None = None


def _get_mem():
    """Lazy-import MemoryStore to avoid circular imports at load time."""
    from memory.store import MemoryStore
    return MemoryStore()


def _get_llm():
    """Lazy-init LLM client."""
    from config import config
    from core.adapter import UniversalLLM
    return UniversalLLM(config.LLM_API_KEY, config.LLM_API_BASE, config.LLM_MODEL)


def _db_stats() -> dict:
    """Query memory DB for category stats directly."""
    from memory.store import DB_PATH
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        rows = con.execute(
            "SELECT category, COUNT(*) as n, MAX(created_at) as last "
            "FROM memories GROUP BY category ORDER BY n DESC"
        ).fetchall()
        con.close()
        return {r[0]: {"count": r[1], "last": r[2]} for r in rows}
    except Exception:
        return {}


def _db_recent(n: int = 10) -> list[dict]:
    from memory.store import DB_PATH
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        rows = con.execute(
            "SELECT category, content, created_at FROM memories "
            "ORDER BY created_at DESC LIMIT ?", (n,)
        ).fetchall()
        con.close()
        return [{"category": r[0], "content": r[1], "created_at": r[2]} for r in rows]
    except Exception:
        return []


def execute(name: str, args: dict) -> dict:

    # ── knowledge_map ────────────────────────────────────────────────────────
    if name == "knowledge_map":
        stats = _db_stats()
        if not stats:
            return {"ok": True, "result": "记忆库为空，还没有学过任何知识。"}

        total = sum(v["count"] for v in stats.values())
        lines = [f"🧠 知识库概览（共 {total} 条）", ""]
        icons = {"knowledge": "📚", "skill": "🛠️", "preference": "❤️", "goal": "🎯"}
        for cat, info in stats.items():
            icon = icons.get(cat, "📝")
            lines.append(
                f"  {icon} {cat:<14} {info['count']:>4} 条   "
                f"最近: {info['last'][:10] if info['last'] else 'N/A'}"
            )

        recent = _db_recent(5)
        if recent:
            lines += ["", "📌 最近学习:"]
            for r in recent:
                snippet = r["content"][:60].replace("\n", " ")
                lines.append(f"  [{r['category']}] {snippet}…")

        return {"ok": True, "result": "\n".join(lines)}

    # ── analyze_topic ────────────────────────────────────────────────────────
    if name == "analyze_topic":
        topic = args["topic"]
        depth = args.get("depth", "quick")
        mem = _get_mem()

        # Search memory for existing knowledge
        known = mem.search(topic, limit=20)
        k_count = len(known)

        lines = [f"🔍 主题分析：{topic}", ""]

        if k_count == 0:
            lines += [
                "📊 已知程度：空白（记忆库中无相关内容）",
                "",
                "💡 建议：",
                f"  1. 用 web_research 工具搜索 '{topic}' 基础资料",
                f"  2. 用 learn_url 工具阅读相关网页",
                f"  3. 用 distill_knowledge 工具提炼关键内容到记忆库",
            ]
            return {"ok": True, "result": "\n".join(lines)}

        # Coverage assessment
        snippets = [r["content"][:80] for r in known[:5]]
        level = "初步了解" if k_count < 5 else ("有一定了解" if k_count < 15 else "较深入掌握")

        lines += [
            f"📊 已知程度：{level}（记忆库共 {k_count} 条相关记录）",
            "",
            "📚 已知内容样本：",
        ]
        for s in snippets:
            lines.append(f"  • {s}…")

        if depth == "deep" and k_count > 0:
            # Use LLM to analyze gaps
            try:
                llm = _get_llm()
                known_text = "\n".join(r["content"] for r in known[:15])
                prompt = (
                    f"我对「{topic}」已了解以下内容：\n{known_text}\n\n"
                    "请分析：\n"
                    "1. 知识是否系统完整？有哪些明显的知识空白（gaps）？\n"
                    "2. 推荐3-5个应该深入学习的子主题（具体、可搜索）\n"
                    "3. 推荐1-2个学习资源类型（书/视频/文档）\n"
                    "用简洁的中文回答，不超过300字。"
                )
                analysis = llm.chat(prompt)
                lines += ["", "🤖 AI 分析：", analysis]
            except Exception as e:
                lines += ["", f"⚠️ AI 分析暂不可用: {e}"]
        else:
            lines += [
                "",
                "💡 可能的知识空白（建议搜索）：",
                f"  • {topic} 原理与底层机制",
                f"  • {topic} 最佳实践与常见误区",
                f"  • {topic} 最新进展（2024-2025）",
                f"  • {topic} 实际案例与应用",
            ]

        return {"ok": True, "result": "\n".join(lines)}

    # ── distill_knowledge ────────────────────────────────────────────────────
    if name == "distill_knowledge":
        topic = args["topic"]
        raw_text = args["raw_text"][:8000]
        source = args.get("source", "")
        category = args.get("category", "knowledge")

        if len(raw_text.strip()) < 50:
            return {"ok": False, "result": "文本内容太短，无法提炼"}

        try:
            llm = _get_llm()
            source_hint = f"（来源：{source}）" if source else ""
            prompt = (
                f"请从以下关于「{topic}」的文章中提炼核心知识点{source_hint}。\n\n"
                "要求：\n"
                "- 提取5-10个最重要、最独特的知识点\n"
                "- 每条知识点：1-3句话，独立完整，脱离原文也能理解\n"
                "- 去除废话、广告、导航文字等噪声\n"
                "- 仅输出JSON数组格式，如：[\"知识点1\", \"知识点2\", ...]\n\n"
                f"文章内容：\n{raw_text}"
            )
            raw_result = llm.chat(prompt)
        except Exception as e:
            return {"ok": False, "result": f"LLM 调用失败: {e}"}

        # Parse JSON array from LLM response
        import re, json
        match = re.search(r"\[.*?\]", raw_result, re.DOTALL)
        if not match:
            return {"ok": False, "result": f"LLM 输出格式异常，无法解析:\n{raw_result[:300]}"}

        try:
            points: list[str] = json.loads(match.group())
        except json.JSONDecodeError:
            return {"ok": False, "result": f"JSON 解析失败:\n{match.group()[:200]}"}

        if not points:
            return {"ok": True, "result": "未从文本中提炼到有效知识点"}

        mem = _get_mem()
        saved = 0
        skipped = 0
        prefix = f"[{topic}]" + (f" [来源:{source[:50]}]" if source else "")
        for point in points:
            if isinstance(point, str) and len(point.strip()) > 10:
                content = f"{prefix} {point.strip()}"
                if mem.save(category, content):
                    saved += 1
                else:
                    skipped += 1

        lines = [
            f"✅ 知识提炼完成：{topic}",
            f"  提炼知识点：{len(points)} 条",
            f"  新增入库：{saved} 条，已存在跳过：{skipped} 条",
            f"  存入类别：{category}",
            "",
            "📌 提炼内容预览：",
        ]
        for i, p in enumerate(points[:5]):
            lines.append(f"  {i+1}. {p[:100]}")
        if len(points) > 5:
            lines.append(f"  …（共 {len(points)} 条）")

        return {"ok": True, "result": "\n".join(lines)}

    # ── set_learning_goal ────────────────────────────────────────────────────
    if name == "set_learning_goal":
        goal = args["goal"]
        deadline = args.get("deadline", "")
        subtopics = args.get("subtopics", [])

        parts = [f"🎯 学习目标：{goal}"]
        if deadline:
            parts.append(f"截止日期：{deadline}")
        if subtopics:
            parts.append("子主题：" + "、".join(subtopics))

        content = " | ".join(parts)
        mem = _get_mem()
        ok = mem.save("goal", content)

        status = "已记录" if ok else "目标已存在（重复）"
        return {
            "ok": True,
            "result": f"{'✅' if ok else '⚠️'} {status}：{goal}"
                      + (f"\n截止：{deadline}" if deadline else "")
                      + (f"\n子主题：{', '.join(subtopics)}" if subtopics else ""),
        }

    # ── review_knowledge ─────────────────────────────────────────────────────
    if name == "review_knowledge":
        topic = args["topic"]
        limit = min(int(args.get("limit", 20)), 50)
        mem = _get_mem()
        results = mem.search(topic, limit=limit)

        if not results:
            return {
                "ok": True,
                "result": f"记忆库中暂无关于「{topic}」的记录。\n建议先用 distill_knowledge 或 memory_save 积累知识。",
            }

        lines = [f"📖 复习：{topic}（共 {len(results)} 条）", "─" * 50]
        for i, r in enumerate(results, 1):
            cat = r.get("category", "")
            content = r.get("content", "").strip()
            lines.append(f"{i:2}. [{cat}] {content}")
        return {"ok": True, "result": "\n".join(lines)}

    return {"ok": False, "result": f"Unknown tool: {name}"}
