# StarBot

StarBot 是一个可在本地运行的 AI 智能代理，支持命令行和网页两种使用方式。
它可以通过工具调用完成系统命令执行、文件读写、网页检索、HTTP 接口请求、SQLite 查询，并支持动态创建自定义工具。

## 项目特点

- 支持双模式运行：命令行模式、网页模式
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
- `/auto start 秒数 任务`：启动后台自动任务循环
- `/auto stop`：停止后台自动任务循环
- `/auto status`：查看后台任务状态
- `/config key value`：修改配置
- `/clear`：清空当前会话
- `/exit`：退出程序

## 持续工作模式

StarBot 默认开启持续工作能力（`max_iterations = -1`），并支持后台自动执行模式。

使用建议：

1. 推荐使用后台自动模式（一次下达，自动循环）：
   - `/auto start 30 每隔30秒抓取最新行情并分析趋势变化`
2. 查看状态：`/auto status`
3. 停止任务：`/auto stop`
4. 如果需要限制单轮内部推理轮次，可设置：`/config max_iterations N`
5. 在命令行中也可通过 `Ctrl + C` 终止程序

## 安全说明

- 本项目包含高权限工具（如 `shell_exec`、`powershell_exec`、`python_exec`、`file_write`、`sqlite_query`）。
- 请仅在可信环境中运行，避免执行来源不明的提示词或命令。
- 不要将 API Key 提交到仓库。
- 本仓库已通过 `.gitignore` 忽略 `config.yaml` 与本地数据目录，降低密钥泄露风险。

## 许可证

本项目采用 MIT 许可证，详见 `LICENSE` 文件。
