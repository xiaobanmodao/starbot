# StarBot

StarBot 是一个可在本地运行的 AI 智能代理，支持命令行、网页和守护进程三种使用方式。
它可以通过工具调用完成系统命令执行、文件读写、网页检索、HTTP 接口请求、SQLite 查询，并支持动态创建自定义工具。

## 项目特点

- 支持三种运行模式：命令行模式、网页模式、守护进程模式
- 支持流式输出回答
- 内置完整工具体系（系统命令、PowerShell、Python、文件、网络、数据库）
- 支持会话历史本地保存与恢复
- 支持运行时创建并持久化自定义工具
- 同时保留 Node.js 与 Python 两套实现（当前主实现为 Node.js）

## 目录结构

```text
starbot/
├─ src/                    # Node.js 主实现
│  ├─ index.js             # 程序入口（选择命令行/网页）
│  ├─ automation/          # 自动化核心（OpenClaw 风格分层）
│  │  ├─ runner/           # 后台常驻执行层（沉默）
│  │  ├─ watchers/         # 条件监控（只判断）
│  │  ├─ actions/          # 动作执行（真干活）
│  │  ├─ store/            # 任务/结果/状态存储
│  │  ├─ notifier/         # 系统通知（非对话）
│  │  └─ chat/             # 对话汇总层（唯一可说话）
│  ├─ agent.js             # 代理主循环与工具调度
│  ├─ client.js            # OpenAI 兼容客户端
│  ├─ cli.js               # 命令行交互
│  ├─ web/                 # 网页服务与前端页面
│  ├─ tools/               # 内置工具与动态工具系统
│  └─ history/             # 会话历史存储
├─ starbot/                # Python 版本实现（保留）
├─ start_starbot.bat       # Windows 一键启动（Node）
├─ run.py                  # Python 启动入口
├─ package.json
├─ requirements.txt
└─ config.yaml             # 本地配置（已在 .gitignore 中忽略）
```

## 环境要求

- Node.js 18 及以上（推荐）
- Python 3.10 及以上（仅在使用 Python 版本时需要）

## 安装步骤

### 安装 Node.js 依赖（主实现）

```bash
npm install
```

### 安装 Python 依赖（可选）

```bash
pip install -r requirements.txt
```

## 配置说明

Node 版本配置默认保存在：

- Windows：`%USERPROFILE%\.starbot\config.json`
- Linux/macOS：`~/.starbot/config.json`

支持以下环境变量覆盖：

- `STARBOT_API_KEY`
- `STARBOT_BASE_URL`
- `STARBOT_MODEL`
- `STARBOT_MAX_ITERATIONS`

Python 版本默认读取项目根目录 `config.yaml`。

## 启动方式

### 启动 Node 命令行模式

```bash
npm start
```

### 启动 Node 网页模式

```bash
node src/index.js --web
```

### 启动 Node 守护进程模式（常驻自动执行任务）

```bash
npm run daemon
```

### 启动 Python 命令行模式

```bash
python run.py
```

### 启动 Python 网页模式

```bash
python run.py --web
```

## 命令行常用指令（Node）

- `/help`：查看可用指令
- `/new`：新建会话
- `/history`：切换历史会话
- `/model`：切换模型
- `/tools`：查看工具
- `/config key value`：修改配置
- `/clear`：清空当前会话
- `/exit`：退出程序

## 持续工作模式

StarBot 默认开启持续工作能力（`max_iterations = -1`），并支持真正的后台自动化 runner。

使用建议：

1. 在对话中直接下达无人值守任务（AI 会调用无人值守工具创建任务）。
2. 守护进程常驻执行监控与动作，不直接对话。
3. 你下次激活原对话时，会收到一次性汇总。
4. 需要停止守护进程可使用 `Ctrl + C`（前台）或结束 daemon 进程。

你可以直接在对话里下达任务，例如：

- “从现在开始每 30 秒看盘并分析，除非我说停止，否则一直做。”

在该模式下，AI 会自动调用无人值守工具创建后台任务并拉起守护进程，无需你手动输入管理命令。
后台 Runner 不会直接回复用户；只写结构化结果，等待你下次在原对话输入时统一汇报。

## 守护进程任务管理（无人值守）

你可以把任务保存到本地任务库，随后用守护进程常驻执行，不需要持续保持聊天窗口输入。

### 添加任务

```bash
node src/index.js --job-add --task-id "auto_delete_desktop_file" --path "C:\\Users\\胡书源\\Desktop\\133456.txt" --interval 1 --origin <conversation_id> --end-at 2026-02-18T23:59:59+08:00
```

### 查看任务

```bash
npm run job:list
```

### 启用/禁用任务

```bash
node src/index.js --job-enable <任务ID>
node src/index.js --job-disable <任务ID>
```

### 删除任务

```bash
node src/index.js --job-remove <任务ID>
```

任务文件路径：`~/.starbot/automation_tasks.json`
结果文件路径：`~/.starbot/automation_results.json`

### OpenClaw 风格约束（当前实现）

- 后台 Runner 不持有对话上下文，不调用任何对话/LLM 接口
- 后台只写结构化结果（`reported=false`），并更新任务状态
- 任务完成后状态为 `completed`（失败为 `error`）
- 用户可见汇报仅在原始对话激活时统一输出，随后标记为 `reported=true`
- 后台线程不会直接向用户发对话消息，也不会创建临时对话

## 指定测试任务（133456.txt）

1. 在任意对话中告诉 AI：  
   “监控 `C:\\Users\\胡书源\\Desktop\\133456.txt`，出现即删除，循环到指定时间并系统通知。”
2. AI 会通过工具创建无人值守任务并拉起 daemon。
3. 后台会在 1 秒轮询中执行：
   - watcher 检测文件是否存在
   - action 执行真实删除
   - 写入结构化 result（`reported=false`）
   - 触发系统通知
4. 你下次在原对话输入消息时，会一次性收到汇总，并自动标记已汇报。

## 安全说明

- 本项目包含高权限工具（如 `shell_exec`、`powershell_exec`、`python_exec`、`file_write`、`sqlite_query`）。
- 请仅在可信环境中运行，避免执行来源不明的提示词或命令。
- 不要将 API Key 提交到仓库。
- 本仓库已通过 `.gitignore` 忽略 `config.yaml` 与本地数据目录，降低密钥泄露风险。

## 许可证

本项目采用 MIT 许可证，详见 `LICENSE` 文件。
