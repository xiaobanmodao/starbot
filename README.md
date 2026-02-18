# StarBot

本项目是一个可在本地运行的 AI 代理，支持 CLI 和 Web 两种交互方式。  
它可以通过工具调用执行系统命令、读写文件、搜索网页、请求 HTTP 接口、查询 SQLite，并支持动态创建自定义工具。

## 特性

- 双运行模式：CLI / Web
- 流式对话输出（SSE）
- 内置工具系统（Shell、PowerShell、Python、文件、网络、数据库等）
- 会话历史持久化（本地保存）
- 支持在运行时创建并持久化自定义工具
- 同时保留 Node.js 与 Python 两套实现（当前主实现为 Node.js）

## 项目结构

```text
starbot/
├─ src/                    # Node.js 主实现
│  ├─ index.js             # 程序入口（CLI/Web 选择）
│  ├─ agent.js             # Agent 主循环与工具调用
│  ├─ client.js            # OpenAI 兼容客户端
│  ├─ cli.js               # 终端交互
│  ├─ web/                 # Web 服务与前端
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

- Node.js 18+（推荐）
- Python 3.10+（如需运行 Python 版本）

## 安装

### Node.js（主实现）

```bash
npm install
```

### Python（可选）

```bash
pip install -r requirements.txt
```

## 配置

Node 版本配置默认保存在：

- Windows: `%USERPROFILE%\.starbot\config.json`
- Linux/macOS: `~/.starbot/config.json`

也支持环境变量覆盖：

- `STARBOT_API_KEY`
- `STARBOT_BASE_URL`
- `STARBOT_MODEL`

Python 版本默认读取项目根目录 `config.yaml`。

## 运行

### Node CLI

```bash
npm start
```

### Node Web

```bash
node src/index.js --web
```

### Python CLI

```bash
python run.py
```

### Python Web

```bash
python run.py --web
```

## 常用 CLI 命令（Node）

- `/help` 查看命令
- `/new` 新建会话
- `/history` 切换历史会话
- `/model` 切换模型
- `/tools` 查看工具
- `/config key value` 修改配置
- `/clear` 清空当前会话
- `/exit` 退出

## 安全说明（重要）

- 本项目包含高权限工具（如 `shell_exec`、`powershell_exec`、`python_exec`、`file_write`、`sqlite_query`）。
- 请仅在可信环境中运行，避免执行来源不明的提示词或命令。
- **不要将 API Key 写入仓库。**
- 本仓库已通过 `.gitignore` 忽略 `config.yaml` 与本地数据目录，防止密钥误提交。

## 许可证

当前仓库未显式声明许可证。若需开源发布，建议补充 `LICENSE` 文件。
