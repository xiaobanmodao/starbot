# 🤖 Starbot

**通过 Discord 远程控制你的 Windows 电脑的 AI Agent**

Starbot 是一个运行在本地 Windows 机器上的 AI 自动化代理，通过 Discord 接收自然语言指令，使用大语言模型（LLM）推理，并调用 50+ 内置工具完成各类桌面自动化任务——鼠标点击、键盘输入、文件操作、网页抓取、屏幕识别等，同时具备长期记忆、操作回滚和后台任务能力。

> An AI-powered Windows desktop automation agent controlled via Discord.

---

> Changelog / 更新日志：见 `CHANGELOG.md`（包含外部 Skills 生态、配置向导重构、`/doctor`、`/skill info/update` 等近期更新）
> Release helper / 发布辅助：`python tools/changelog_release.py <version>`（将 `Unreleased` 归档到版本号）
> GUI 客户端（新增，不替代 Discord）：`python start_gui.py`（本地 Tk）
> Web UI 客户端（长期方案，Tauri/Electron-ready）：`python start_webui.py`
> Desktop ??????????? Web UI??`python start_desktop.py`
> Discord 回复/控制功能仍然保留，可继续使用：`python start.py`

## ✨ 功能特性

| 特性 | 描述 |
|------|------|
| 🖱️ **屏幕控制** | 鼠标点击/拖拽/滚动、键盘输入、热键 |
| 👁️ **视觉识别** | 截图、区域截图、OCR 文字识别、图像匹配 |
| 🌐 **网络访问** | 网页搜索、抓取网页、HTTP 请求 |
| 📁 **文件管理** | 读写、列表、搜索、删除、压缩/解压 |
| 🧠 **长期记忆** | SQLite + FTS5 trigram 语义搜索、时间衰减评分、6 类分类 |
| 🎬 **视频学习** | YouTube/B站字幕提取、Whisper 音频转写、学习视频/网页 |
| ⚙️ **系统管理** | 进程管理、注册表操作、电源控制 |
| ⏱️ **后台任务** | 异步执行长任务，不阻塞主对话 |
| ↩️ **操作回滚** | 文件写入/删除前自动备份，支持撤销 |
| 🔄 **双 LLM 容错** | 主/备 LLM 自动切换，支持多种 API |
| 💬 **会话持久** | 每个频道独立会话，跨重启自动续话 |
| 🔁 **ReAct 迭代** | 失败自动重试、规划→执行→复盘 三段式协议 |

---

## 🛠️ 工具列表（50+）

### 鼠标与键盘
| 工具 | 说明 |
|------|------|
| `click` | 鼠标左/右/中键点击 |
| `double_click` | 双击 |
| `move_to` | 移动鼠标到坐标 |
| `drag` | 从一点拖拽到另一点 |
| `scroll` | 滚轮滚动 |
| `type_text` | 输入文字（支持中文/Unicode） |
| `key_press` | 按下单个按键 |
| `hotkey` | 组合快捷键（如 Ctrl+C） |

### 截图与视觉
| 工具 | 说明 |
|------|------|
| `screenshot` | 全屏截图（带坐标网格辅助定位） |
| `screenshot_region` | 区域截图 |
| `screenshot_window` | 指定窗口截图 |
| `read_screen_text` | OCR 识别屏幕文字（需 Tesseract） |
| `find_image` | 在屏幕上查找图片位置 |
| `watch_screen` | 监视屏幕变化 |
| `wait_for_text` | 等待屏幕出现指定文字 |

### 网络与搜索
| 工具 | 说明 |
|------|------|
| `web_search` | 搜索引擎搜索 |
| `fetch_page` | 抓取网页内容（转 Markdown） |
| `open_url` | 在浏览器打开 URL |
| `http_request` | 发送 HTTP 请求 |

### 文件操作
| 工具 | 说明 |
|------|------|
| `file_read` | 读取文件内容 |
| `file_write` | 写入/追加文件（写入前自动备份） |
| `file_list` | 列出目录内容 |
| `file_search` | 搜索文件（支持通配符） |
| `file_delete` | 删除文件或目录（删除前自动备份） |
| `zip_files` | 压缩文件 |
| `unzip` | 解压文件 |

### 记忆系统
| 工具 | 说明 |
|------|------|
| `memory_save` | 保存记忆，支持 6 类分类和重要度权重（1-10） |
| `memory_recall` | 多关键词语义搜索记忆，按重要度×时间衰减排序 |

**记忆分类：**

| 分类 | 用途 |
|------|------|
| `preference` | 用户偏好（自动注入系统提示） |
| `knowledge` | 知识/笔记 |
| `project` | 项目信息 |
| `experience` | 操作经验/踩坑 |
| `bug` | Bug 记录 |
| `todo` | 待办事项 |

### 学习工具
| 工具 | 说明 |
|------|------|
| `get_subtitles` | 提取视频字幕（yt-dlp，支持 YouTube/B站等 1000+ 平台） |
| `learn_video_plus` | 学习视频：自动字幕优先，失败自动 Whisper 转写 |
| `learn_url` | 学习网页内容并记忆 |

### 系统与进程
| 工具 | 说明 |
|------|------|
| `run_command` | 执行 Shell 命令 |
| `process_list` | 列出运行中的进程 |
| `process_kill` | 结束进程 |
| `get_env` | 读取环境变量 |
| `get_screen_size` | 获取屏幕分辨率 |
| `mouse_position` | 获取当前鼠标坐标 |

### 窗口管理
| 工具 | 说明 |
|------|------|
| `window_list` | 列出所有窗口 |
| `window_focus` | 聚焦/切换窗口 |
| `window_resize` | 调整窗口大小和位置 |

### 注册表与电源
| 工具 | 说明 |
|------|------|
| `registry_read` | 读取注册表值 |
| `registry_write` | 写入注册表值（支持 REG_SZ/DWORD/BINARY 等） |
| `registry_delete_value` | 删除注册表值 |
| `registry_list_keys` | 列出注册表子键 |
| `power` | 关机/重启/睡眠/锁屏/取消关机 |

### 剪贴板、通知与任务
| 工具 | 说明 |
|------|------|
| `get_clipboard` | 获取剪贴板内容 |
| `set_clipboard` | 设置剪贴板内容 |
| `notify` | 发送系统桌面通知 |
| `bg_task` | 启动后台任务 |
| `task_status` | 查询后台任务状态 |
| `done` | 标记任务完成并返回结果 |
| `wait` | 等待指定秒数 |

---

## 📋 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11 |
| Python | 3.12+ |
| LLM API | OpenAI 兼容接口（OpenAI / DeepSeek / Claude / 本地模型） |
| Discord Bot | 需要 Bot Token 和频道权限 |
| Tesseract | 可选，`read_screen_text` OCR 功能需要 |
| yt-dlp | 可选，视频学习功能需要 |
| faster-whisper | 可选，无字幕视频转写需要 |

---

## 🚀 安装

### 方法一：使用 uv（推荐）

```bash
# 安装 uv（如果没有）
pip install uv

# 克隆项目
git clone <repo-url>
cd starbot

# 安装依赖
uv sync

# 配置环境
cp .env.template .env
# 编辑 .env 填写配置

# 启动（自动检查依赖）
uv run python start.py
```
> 📌 配置向导与外部 Skills 生态更新（包含重跑配置向导、`skillsmp.com` 支持）：见文末“近期更新（配置向导 / 外部 Skills 生态）”章节。


### 方法二：使用 pip

```bash

pip install -r requirements.txt
python start.py
```


### 方法三：双击启动

直接运行项目目录中的 `启动Starbot.bat`（会自动检查依赖并启动）。

---

## ⚙️ 配置说明

复制 `.env.template` 为 `.env` 并填写以下配置：

> 📌 如果你已经配置过，也可以后续通过命令行重新打开配置向导（支持按步骤跳过或修改）：见文末“近期更新（配置向导 / 外部 Skills 生态）”章节。

```env
# ── 主 LLM 配置 ──────────────────────────────────────
LLM_API_BASE=https://api.openai.com/v1  # API 基础 URL
LLM_API_KEY=sk-xxxxxxxx                  # API 密钥
LLM_MODEL=gpt-4o                         # 模型名称

# ── 备用 LLM（可选，主 LLM 失败时自动切换）────────────
LLM2_API_BASE=https://api.anthropic.com/v1
LLM2_API_KEY=sk-ant-xxxxxxxx
LLM2_MODEL=claude-sonnet-4-6

# ── Discord 配置 ──────────────────────────────────────
DISCORD_BOT_TOKEN=your_discord_bot_token  # Bot Token
DISCORD_OWNER_ID=123456789012345678       # 你的 Discord 用户 ID
DISCORD_CHANNEL_ID=123456789012345678     # 默认通知频道 ID

# ── 代理（可选）──────────────────────────────────────
DISCORD_PROXY=http://127.0.0.1:7890
```

### 支持的 LLM 提供商示例

```env
# OpenAI
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# DeepSeek
LLM_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# Anthropic Claude（通过兼容接口）
LLM_API_BASE=https://api.anthropic.com/v1
LLM_MODEL=claude-sonnet-4-6

# 本地模型（vLLM / Ollama）
LLM_API_BASE=http://localhost:8000/v1
LLM_MODEL=Qwen2.5-72B-Instruct
```

### 创建 Discord Bot

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 创建新应用 → Bot → 复制 Token
3. 在 OAuth2 → URL Generator 中选择 `bot` 并勾选权限：
   - Read Messages / View Channels
   - Send Messages
   - Attach Files
   - Create Public Threads
4. 用生成的链接邀请 Bot 到你的服务器

---

## 💬 使用方法

### Discord 命令

| 命令 | 说明 |
|------|------|
| `/status` | 查看系统状态（CPU/内存/后台任务） |
| `/screenshot` | 立即截图 |
| `/stop` | 停止当前任务 |
| `/model [名称]` | 查看/切换 LLM 模型 |
| `/memory [子命令]` | 管理 AI 记忆（见下表） |
| `/reset` | 清空当前会话上下文 |
| `/usage` | 查看本会话 token 用量 |
| `/tasks` | 查看后台任务列表 |
| `/config [key] [value]` | 查看/修改运行时配置 |
| `/rollback [n]` | 撤销最近 n 次文件写入/删除（默认 1） |
| `/skill` | 查看/安装/删除 skill 插件 |
| `/help` | 查看完整帮助 |

#### `/memory` 子命令

| 子命令 | 说明 |
|--------|------|
| `/memory` 或 `/memory list` | 列出最近 15 条记忆 |
| `/memory list <分类>` | 按分类列出（如 `/memory list knowledge`） |
| `/memory search <关键词>` | 语义搜索记忆 |
| `/memory delete <ID>` | 删除指定 ID 的记忆 |
| `/memory stats` | 查看各分类记忆数量统计 |

### 对话示例

```
用户: 帮我搜索一下 Python asyncio 的最新教程
用户: 打开 Chrome 并访问 github.com
用户: 截图看看现在屏幕上有什么
用户: 把桌面上的 report.docx 读取内容给我看
用户: 后台学习这个视频 https://youtube.com/watch?v=xxx
用户: 记住我喜欢用 VSCode 编辑代码
```

### 会话机制

- 在 Discord 服务器中**任意文字频道**直接发消息即可开始对话
- 每个频道有独立的持久会话，跨重启自动续话
- 新建频道时 Bot 会自动发送欢迎消息
- 使用 `/stop` 命令中断当前任务

---

## 🧠 AI 行为协议

Starbot 遵循三段式任务执行协议：

### 1. 规划 + 进度可视化
涉及 2 步以上的任务，LLM 先输出编号计划再执行：
> 好，分三步：① 先查X ② 再做Y ③ 最后验证Z，开始执行……

Discord 端会自动解析 `①②③` 或 `1. 2. 3.` 格式的步骤，实时渲染进度卡片：
```
✅ 先查X
⏳ 再做Y          ← 当前执行中
⬜ 最后验证Z
────────────────────────
Step 1: 找到 3 个文件
Step 2: 读取中...
```

### 2. 迭代（ReAct 重试）
- 工具调用失败 → 自动分析原因，换方案重试，最多尝试 3 种不同方法
- `_handle()` 在每条工具结果后注入递进式系统提示：
  - 第 1 次失败：`请分析原因并尝试不同方案重试`
  - 第 2 次失败：`换一种完全不同的方案，最后一次机会`
  - 第 3 次失败：`向用户说明情况并询问如何继续`，重置计数

### 3. 危险操作确认
以下工具执行前会弹出 Discord 按钮确认，用户点击 ✅/❌ 后才继续：

| 工具 | 触发原因 |
|------|--------|
| `file_delete` | 文件删除不可逆 |
| `power` | 关机/重启影响整机 |
| `process_kill` | 强制终止进程 |
| `registry_write` | 写注册表有系统风险 |
| `registry_delete_value` | 注册表删除不可逆 |

用户取消后，Bot 把 `{"ok": false, "result": "用户取消了该操作"}` 送回给 LLM，由 LLM 自行决策下一步。

### 4. 复盘
多步任务完成后自动总结：
> ✅ 完成了什么 / ⚠️ 遇到问题怎么解决的 / 📌 值得记住的经验

有价值的经验立即 `memory_save` 持久化。

### 格式规则
- **纯文字问答**：直接流式回复，末尾加 ✦，不调用任何工具
- **多步操作任务**：最后调用 `done` 工具标记完成（result 填一句话结论）
- 流式回答展示完整内容；`done` 的摘要不覆盖已展示的完整回答

---

## 🏗️ 架构

```
starbot/
├── main.py              # 主工作循环（WorkerLoop）
├── start.py             # 启动检查器（自动安装依赖）
├── config.py            # 配置管理（交互式设置向导）
├── core/
│   ├── brain.py         # LLM 推理引擎（ReAct 循环、上下文压缩、token 追踪）
│   ├── adapter.py       # LLM API 适配器（OpenAI 兼容封装）
│   ├── op_log.py        # 操作日志与文件回滚
│   └── notifier.py      # 后台任务通知桥接
├── actions/
│   ├── executor.py      # 工具实现层（50+ 工具）
│   └── input_win32.py   # Win32 低级输入 API
├── comms/
│   └── discord_client.py # Discord Bot 客户端
├── memory/
│   └── store.py         # SQLite + FTS5 trigram 记忆存储
└── skills/              # 可选扩展插件（video_learn 等）
```

### 核心数据流

```
Discord 消息
    ↓
StarBotClient.on_message()
    ↓
Brain（LLM 推理） ← Memory.recall（多关键词搜索相关记忆）
    ↓
Tool Calling（原生 function calling 或文本解析回退）
    ↓
[危险工具确认] → ConfirmView 按钮 → 用户 ✅/❌
    ↓ (确认通过)
Executor（执行工具） → op_log.backup_file（写入/删除前备份）
    ↓
[ReAct 注入] 失败时注入重试提示，最多3次
    ↓
结果 → Discord 进度卡片（计划清单 + 步骤日志）+ Memory.save()
```

### 记忆检索机制

1. 从查询中提取多个关键词（中文 3-6 字 / 英文 3+ 字 / 中文 2 字三层）
2. 每个关键词独立走 **FTS5 trigram 全文检索** → 失败回退 **LIKE 模糊搜索**
3. 结果按 `importance × exp(-age_days / 30)` 时间衰减评分排序
4. 去重合并，返回最相关的 top-N 条

### 上下文压缩策略

当对话接近 30,000 Token 上限时，Brain 自动三阶段压缩：
1. 移除历史消息中的截图（保留最近 4 条）
2. 裁剪中段 tool 结果到 500 字符
3. 保留系统提示 + 最近 12 条消息（跳过孤立 tool 消息）

### 操作回滚机制

- `file_write` 覆盖模式和 `file_delete` 执行前自动调用 `backup_file()`
- 备份存于 `logs/op_backups/`，保留最近 20 个
- 操作记录写入 `logs/op_history.jsonl`（JSONL 格式）
- `/rollback n` 命令可一键恢复最近 n 次操作

---

## 📦 主要依赖

| 包 | 用途 |
|----|------|
| `discord.py` | Discord Bot 框架 |
| `openai` | LLM API 客户端（OpenAI 兼容） |
| `pyautogui` | 鼠标键盘自动化 |
| `pytesseract` | OCR 文字识别 |
| `pillow` | 图像处理 |
| `requests` | HTTP 请求 |
| `yt-dlp` | 视频字幕下载 |
| `faster-whisper` | 本地语音转写（无字幕视频） |
| `playwright` | 浏览器自动化 |
| `apscheduler` | 定时任务 |
| `psutil` | 进程监控 |

---

## 🔧 OCR 配置（可选）

如需使用 `read_screen_text` 工具：

1. 下载安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
2. 安装中文语言包（`chi_sim`）
3. 将 Tesseract 路径加入系统 PATH，或在 `.env` 中设置：
   ```env
   TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

---

## 🤝 贡献指南

### 添加新工具

1. 在 `actions/executor.py` 的 `TOOLS_SCHEMA` 列表中添加工具定义：

```python
{
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "工具描述，LLM 根据此决定何时调用",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "参数说明"},
            },
            "required": ["param1"],
        },
    },
},
```

2. 在 `_do_execute()` 方法中添加对应处理分支：

```python
elif name == "my_tool":
    result = do_something(args["param1"])
    return {"ok": True, "result": result}
```

3. 如果是屏幕相关工具，将工具名加入 `_SCREEN_TOOL_NAMES` 集合。

### 添加 Skill 插件

在 `skills/` 目录下创建 `.py` 文件，实现 `register(schema_list, handler_map)` 接口，然后通过 `/skill install <路径>` 安装。

---

## ⚠️ 设计决定：危险工具无限制

以下工具**故意不加访问限制**，这是设计决定，不应修改其行为：

| 工具 | 说明 |
|------|------|
| `run_command` | `shell=True`，可执行任意 Shell 命令 |
| `file_write` | 可写入任意路径（无路径白名单） |
| `power` | 可关机/重启/睡眠/锁屏 |
| `registry_write` | 可写入 HKCU/HKLM 任意注册表键 |
| `process_kill` | 可终止任意进程 |

**设计理由：** Starbot 是运行在用户本机、由用户本人通过 Discord 操控的个人助手。
限制这些工具会严重削弱其作为桌面自动化代理的核心能力。
安全边界由 Discord Bot Token + OWNER_ID 鉴权提供——只有配置的所有者才能发送指令。

> 如需在多用户或公开环境中部署，请自行在 `actions/executor.py` 中添加相应限制。

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源，可自由使用、修改和分发。

---

## 🆕 近期更新（配置向导 / 外部 Skills 生态）

### 1) 配置向导已独立拆分（功能不变）

- 启动时若 `.env` 关键配置缺失，仍会自动进入配置向导（行为保持不变）
- 配置向导已拆分为独立模块，便于维护和后续扩展
- 现在支持“重新运行配置向导”来修改已有配置

### 2) 已配置项支持“跳过 / 修改”

在重新配置模式下，向导会按步骤提示（LLM / Discord / Proxy）：

- `Skip`：保留当前配置不变
- `Modify`：进入该步骤修改配置

已配置字段会显示当前值（敏感值会脱敏），方便微调而不是重填全部内容。

### 3) 命令行手动重跑配置向导（新增）

以下命令可在命令行中重新进入配置向导：

```bash
# 只运行配置向导，不启动 Starbot
python start.py setup
python start.py config
python start.py --setup-only

# 先运行配置向导，再继续正常启动
python start.py --setup

# 直接运行独立配置向导模块
python config_wizard.py
```

### 4) 支持外部下载的 Skills（兼容 SKILL.md 生态）

Starbot 现在支持兼容外部 `SKILL.md` 技能生态（例如部分 Codex / Claude 风格技能包），并自动将其暴露为可调用工具。

支持来源包括：

- `skillsmp.com` 页面链接（自动解析页面中的 GitHub 仓库）
- GitHub 仓库 / `tree` 子目录链接（自动查找 `SKILL.md`）
- 本地目录（包含 `SKILL.md`）
- 本地或远程 `.zip`（包含 `SKILL.md`）
- 单文件 `SKILL.md`

安装示例：

```bash
/skill install https://skillsmp.com/skills/<slug>
/skill install https://github.com/<owner>/<repo>
/skill install https://github.com/<owner>/<repo>/tree/main/path/to/skill
/skill install C:\path\to\some-skill-folder
```

### 5) AI 会自动使用这些外部 Skills

外部 `SKILL.md` 技能在加载后会自动变成可调用工具（tool schema），因此模型可以像使用内置工具一样自动选择和调用这些技能，无需手工逐条执行说明。

说明：

- 外部“发现型”技能（例如自动扫描到的 `~/.codex/skills`）默认只读加载
- `/skill remove` 不会删除用户原始目录（会提示你去原位置删除）
- 安装后如需刷新技能列表，可执行 `/skill reload`
