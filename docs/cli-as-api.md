---
title: 白嫖 Claude API
parent: AI Capriccio
nav_order: 4
---

# 白嫖 Claude API

> 既然有了 claude.ai，为什么一定要我买 API？

## 核心思路

用 Claude Code CLI 的子进程模式充当 AI 后端，HTTP 服务器只是一层薄薄的调度壳 —— 不需要 API Key，不需要按 token 付费，直接复用 Claude Code 订阅获得完整的 Agent 能力。

```
┌──────────┐    HTTP     ┌──────────────┐   subprocess    ┌─────────────┐
│  Client  │ ──────────> │  HTTP Server │ ─────────────> │ Claude Code │
│ (browser │ <────────── │  (Python)    │ <───────────── │    CLI      │
│  / curl) │    SSE /    └──────────────┘   stdout/json   └─────────────┘
└──────────┘    JSON
```

Claude Code 本身是一个终端交互工具，但它提供了一组非交互模式的参数，使得程序化调用成为可能。HTTP 服务器通过 `subprocess` 调用 `claude` 命令，解析其输出，就得到了一个功能完整的 AI Agent 服务。

## 两种方案对比：Claude API vs Claude Code as API

### 架构差异

```
方案 A：Claude API（传统方式）
┌────────┐     HTTPS      ┌───────────────┐     HTTPS      ┌────────────┐
│ Client │ ─────────────> │  Your Server  │ ─────────────> │ Claude API │
└────────┘                │               │                │ (Anthropic) │
                          │  你需要实现：   │                └────────────┘
                          │  - Tool 定义    │
                          │  - Tool 执行    │
                          │  - 多轮循环     │
                          │  - 对话历史     │
                          │  - 错误重试     │
                          └───────────────┘

方案 B：Claude Code as API（本文方案）
┌────────┐     HTTP       ┌───────────────┐   subprocess   ┌─────────────┐
│ Client │ ─────────────> │  Your Server  │ ────────────> │ Claude Code │
└────────┘                │               │               │   CLI       │
                          │  你只需要：     │               │             │
                          │  - 路由请求     │               │ 内置：       │
                          │  - 转发输出     │               │ - 文件读写   │
                          └───────────────┘               │ - Shell 执行 │
                                                          │ - Git 操作   │
                                                          │ - 多轮 Tool  │
                                                          │ - 对话记忆   │
                                                          └─────────────┘
```

### 逐项对比

| 维度 | Claude API | Claude Code as API |
|------|------------|-------------------|
| **认证** | 需要 API Key | 不需要，用 Claude Code 登录态 |
| **计费** | 按 token 计费（input + output） | 包含在 Claude Code 订阅中（Max/Team/Enterprise） |
| **Tool Use** | 你定义 JSON Schema，你写执行逻辑 | 内置 20+ 工具（Read, Write, Edit, Bash, Grep, Glob...） |
| **Agentic Loop** | 你写 while 循环处理 tool_use → tool_result | 内置，`--max-turns` 控制轮数 |
| **对话记忆** | 你存储并回传 messages 数组 | 内置，`--session-id` + `--resume` |
| **流式输出** | SSE (原生支持) | `--output-format stream-json` (每行一个 JSON) |
| **结构化输出** | 原生 JSON mode / tool_use | 需要解析 stream-json，可靠性稍低 |
| **文件访问** | 你实现文件读取工具 | 内置，Claude 自己决定读什么文件 |
| **Shell 执行** | 你实现命令执行工具（安全风险自担） | 内置 Bash 工具，有权限模型 |
| **并发** | 高（受 API rate limit 约束，通常 1000+ RPM） | 低（每个请求一个进程，受 CLI 限流约束） |
| **首 token 延迟** | ~1-2s | ~3-5s（进程启动开销） |
| **上下文窗口** | 精确控制 token 用量 | Claude Code 自动管理，不可精确控制 |
| **部署环境** | 任何能发 HTTPS 请求的环境 | 需要安装 Claude Code CLI + Node.js |
| **成本可预测性** | 按量付费，可精确预估 | 固定订阅费，但有隐性并发/速率上限 |
| **适合规模** | 任意规模 | 内部工具 / 小团队（< 10 并发用户） |

### 各自的独特优势

**Claude API 独有：**
- 精确的 token 计数和成本控制
- 自定义工具（可以调用任何外部 API、数据库、第三方服务）
- 高并发、低延迟，适合生产环境
- 不依赖本地环境，可部署在任何服务器
- Batch API 支持（批量处理，50% 折扣）

**Claude Code as API 独有：**
- 零成本开发 —— 不需要实现任何工具、循环、或状态管理
- 完整的代码仓库感知 —— Claude 可以自己 grep、读文件、看 git history
- 可以直接在仓库里执行命令（build、test、lint）
- Session 持久化在磁盘上，进程重启后对话不丢失
- 从 CLI 原型到 HTTP 服务只需加一层薄壳

### 选择建议

```
你的场景是...                              → 选择
───────────────────────────────────────────────────
面向用户的产品，需要高可用               → Claude API
需要调用外部 API（支付、数据库、邮件）   → Claude API
团队 > 10 人并发使用                     → Claude API
需要精确的成本核算                       → Claude API
内部开发工具 / DevOps 自动化             → Claude Code as API
AI 驱动的代码审查 / 生成 / 重构         → Claude Code as API
快速原型验证                             → Claude Code as API
已有 Claude Code 订阅，不想额外付费      → Claude Code as API
```

## 为什么可行：Claude Code CLI 的关键参数

| 参数 | 用途 |
|------|------|
| `-p <prompt>` | 非交互模式，传入一次性 prompt |
| `--system-prompt <text>` | 注入自定义系统提示词 |
| `--model <model-id>` | 选择模型（Opus / Sonnet / Haiku） |
| `--output-format stream-json` | 机器可读的流式 JSON 输出 |
| `--session-id <uuid>` | 创建命名会话（多轮对话） |
| `--resume <session-id>` | 恢复已有会话 |
| `--allowedTools <list>` | 限制可用工具（如只读：`Read,Glob,Grep`） |
| `--max-turns <n>` | 限制 Agent 循环轮数 |
| `--dangerously-skip-permissions` | 无头模式（跳过用户确认提示） |

## 核心组件实现

### 1. CLI 封装器（一次性任务）

用于代码生成、审查、分析等不需要流式输出的场景：

```python
import io, os, subprocess
from pathlib import Path

def call_claude(
    system_prompt: str,
    task_prompt: str,
    model: str,
    cwd: str | Path,
    skip_permissions: bool = False,
    timeout: int | None = None,
) -> tuple[str, int]:
    """调用 Claude CLI，返回 (输出文本, 退出码)。"""
    args = ["claude", "--model", model, "-p", task_prompt,
            "--system-prompt", system_prompt]
    if skip_permissions:
        args.insert(1, "--dangerously-skip-permissions")

    # 移除 CLAUDECODE 环境变量，避免嵌套会话冲突
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    buf = io.StringIO()
    with subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=str(cwd), env=env,
    ) as proc:
        try:
            for line in proc.stdout:
                buf.write(line)
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return buf.getvalue().strip(), -1

    return buf.getvalue().strip(), proc.returncode
```

HTTP handler 中使用：

```python
@app.post("/api/tasks")
def handle_task(request):
    output, code = call_claude(
        system_prompt="你是一个代码审查专家...",
        task_prompt=request.json["prompt"],
        model="claude-sonnet-4-6",
        cwd="/path/to/repo",
        skip_permissions=True,
    )
    return {"result": output, "exit_code": code}
```

### 2. SSE 流式输出（实时聊天）

用于需要实时展示 Claude 回复的交互式聊天场景：

```python
import json, subprocess, uuid

def call_claude_stream(message, session_id, is_resume, system_prompt, cwd):
    """从 Claude 的 stream-json 输出中逐步产出 (事件类型, 数据)。

    事件类型: "text"（增量文本块）, "result"（最终完整结果）, "error"（错误）
    """
    args = [
        "claude", "--model", "claude-sonnet-4-6",
        "-p", message,
        "--output-format", "stream-json",
        "--allowedTools", "Read,Glob,Grep",  # 按需限制
        "--max-turns", "3",
    ]
    if is_resume:
        args += ["--resume", session_id]
    else:
        args += ["--session-id", session_id, "--system-prompt", system_prompt]

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    proc = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, env=env, cwd=cwd,
    )

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
            if evt.get("type") == "assistant":
                for block in evt.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        yield ("text", block["text"])
            elif evt.get("type") == "result":
                yield ("result", evt.get("result", ""))
        except json.JSONDecodeError:
            continue

    proc.wait(timeout=10)
    if proc.returncode != 0:
        yield ("error", f"Exit code {proc.returncode}")
```

HTTP handler 桥接到 SSE：

```python
def handle_chat_sse(self, message):
    global session  # {"id": str} or None

    is_resume = session is not None
    if not is_resume:
        session = {"id": str(uuid.uuid4())}

    # SSE 响应头
    self.send_response(200)
    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
    self.send_header("Cache-Control", "no-cache")
    self.end_headers()

    for evt_type, evt_data in call_claude_stream(
        message, session["id"], is_resume, SYSTEM_PROMPT, cwd="/repo"
    ):
        payload = f"event: {evt_type}\ndata: {json.dumps(evt_data)}\n\n"
        self.wfile.write(payload.encode())
        self.wfile.flush()

    self.wfile.write(b"event: done\ndata: \"\"\n\n")
    self.wfile.flush()
```

前端 JavaScript：

```javascript
function chat(message) {
  const es = new EventSource(`/api/chat?message=${encodeURIComponent(message)}`);

  es.addEventListener('text', (e) => {
    // 增量文本 —— 追加到 UI
    document.getElementById('response').textContent += JSON.parse(e.data);
  });

  es.addEventListener('result', (e) => {
    // 最终完整回复 —— 用 markdown 渲染
    const full = JSON.parse(e.data);
    document.getElementById('response').innerHTML = renderMarkdown(full);
    es.close();
  });

  es.addEventListener('done', () => es.close());
  es.addEventListener('error', () => es.close());
}
```

### 3. 会话管理（多轮对话）

Claude Code 原生支持会话。HTTP 服务器只需维护一个 session ID：

```python
# 新建对话
session_id = str(uuid.uuid4())
# 第一条消息: --session-id <id> --system-prompt <prompt>
# 后续消息:   --resume <id>    （系统提示词会被记住）
# 重置对话:   丢弃 session_id，下一条消息自动开启新会话
```

**关键行为：**
- `--session-id` 创建新会话
- `--resume` 恢复已有会话（完整上下文保留）
- 会话持久化在磁盘（`~/.claude/projects/`），进程重启后不丢失
- 无需重传对话历史 —— Claude Code 内部管理

### 4. 后台 Worker（长时间任务）

对于耗时较长的任务（代码实现、重构），用后台线程执行：

```python
import threading, time

active_workers = {}

def handle_long_task(task_id, prompt):
    def _worker():
        active_workers[task_id] = {"started": time.time(), "status": "running"}
        try:
            output, code = call_claude(
                system_prompt="你是一个开发者...",
                task_prompt=prompt,
                model="claude-sonnet-4-6",
                cwd="/path/to/repo",
                skip_permissions=True,
            )
            active_workers[task_id]["status"] = "done"
            active_workers[task_id]["result"] = output
        except Exception as e:
            active_workers[task_id]["status"] = "error"
            active_workers[task_id]["error"] = str(e)

    threading.Thread(target=_worker, daemon=True).start()
    return {"task_id": task_id, "status": "started"}

# 轮询获取结果
def get_task_status(task_id):
    return active_workers.get(task_id, {"status": "not_found"})
```

## 架构模式

### 模式 A：聊天助手（有状态，流式）

```
浏览器 ──SSE──> HTTP Server ──subprocess──> claude --session-id X --output-format stream-json
                    │                              │
                    │<──────── 流式事件 ────────────┘
                    │
                session_id 存在内存中（或数据库）
```

- 每个用户/对话维持一个持久会话
- `--resume` 实现多轮
- `--allowedTools` 限制能力范围（如只读）
- `--max-turns` 控制成本

### 模式 B：任务 Worker（无状态，即发即忘）

```
API 请求 ──> HTTP Server ──> 线程 ──> claude -p "任务" --skip-permissions
                 │                        │
                 │<── 202 Accepted        │
                 │                        └──> 写文件、跑命令、退出
                 │
              轮询 /status 获取结果
```

- 每个任务独立会话（无状态泄漏）
- `--dangerously-skip-permissions` 用于无头执行
- 工作目录（`cwd`）提供文件/仓库上下文
- 系统提示词定义 Agent 的角色和边界

### 模式 C：混合模式（聊天 + 任务调度）

```
                    ┌───────────────────────┐
                    │     HTTP Server       │
                    │                       │
  聊天 SSE ─────>  │  Chat Session (resume) │  ← 有状态，流式，限制工具
                    │                       │
  任务 POST ────>  │  Worker Pool          │  ← 无状态，后台，完整权限
                    │  ├── 开发者 Agent     │
                    │  ├── 审查者 Agent     │
                    │  └── 分析者 Agent     │
                    └───────────────────────┘
```

每个"角色"拥有独立的系统提示词和工具权限。HTTP 服务器只负责路由。

## 踩坑指南

### 1. 环境变量隔离

启动子进程时必须移除 `CLAUDECODE` 环境变量，否则会导致嵌套会话冲突：

```python
env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
```

### 2. 进程清理

始终处理 `TimeoutExpired`，杀掉僵尸进程。`proc.kill()` 后必须调用 `proc.wait()`：

```python
try:
    proc.wait(timeout=timeout)
except subprocess.TimeoutExpired:
    proc.kill()
    proc.wait()  # 必须！否则留下僵尸进程
```

### 3. stream-json 解析

`--output-format stream-json` 每行输出一个 JSON 对象，但不是每行都有意义。需要按 `type` 字段过滤：

- `type: "assistant"` → 包含文本块（增量输出）
- `type: "result"` → 最终完整结果
- 其他类型（`system`, `tool_use` 等）→ 通常可忽略

### 4. 并发限制

Claude Code 有内置速率限制。同时运行太多会话会触发限流。根据你的订阅等级设计 Worker 池大小。

### 5. CLI 发现

`claude` 二进制的位置因安装方式不同而异（npm global、homebrew 等）。建议使用 `shutil.which("claude")` 加 fallback：

```python
import shutil

def find_claude_cmd():
    if shutil.which("claude"):
        return ["claude"]
    # fallback: 检查 npm global 安装路径
    for npm_root in [
        Path("/opt/homebrew/lib/node_modules"),
        Path("/usr/local/lib/node_modules"),
        Path.home() / ".npm-global" / "lib" / "node_modules",
    ]:
        cli_js = npm_root / "@anthropic-ai" / "claude-code" / "cli.js"
        if cli_js.is_file():
            return [shutil.which("node") or "node", str(cli_js)]
    raise FileNotFoundError("claude CLI not found")
```

### 6. 权限模型

`--dangerously-skip-permissions` 是无头运行的必要条件，但会授予完整的文件系统和 Shell 访问权限。通过以下手段限制爆炸半径：

- `cwd` 限定工作目录
- `--allowedTools` 限制可用工具
- 系统提示词中声明禁止事项

### 如果可以用 claude.ai token 的地方

```bash
claude setup-token
```

## 最小可运行示例

一个完整的流式聊天服务器，约 50 行：

```python
import json, os, subprocess, uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

session = None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global session
        qs = parse_qs(urlparse(self.path).query)
        msg = qs.get("m", [""])[0]
        if not msg:
            self.send_error(400); return

        is_resume = session is not None
        if not is_resume:
            session = str(uuid.uuid4())

        args = ["claude", "-p", msg, "--output-format", "stream-json"]
        args += (["--resume", session] if is_resume
                 else ["--session-id", session,
                       "--system-prompt", "你是一个有帮助的助手。"])

        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, text=True, env=env)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()

        for line in proc.stdout:
            if not line.strip(): continue
            try:
                evt = json.loads(line)
                if evt.get("type") == "assistant":
                    for b in evt.get("message",{}).get("content",[]):
                        if b.get("type") == "text":
                            self.wfile.write(
                                f"data: {json.dumps(b['text'])}\n\n".encode())
                            self.wfile.flush()
                elif evt.get("type") == "result":
                    self.wfile.write(
                        f"event: result\ndata: {json.dumps(evt['result'])}\n\n".encode())
                    self.wfile.flush()
            except: pass
        proc.wait()

HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
```

## 一句话总结

**Claude Code CLI + subprocess = 免费的 Agent-as-a-Service**。HTTP 服务器只是管道 —— 把请求路由到 Claude 会话，把响应流式转发回去。你获得了完整的 Agent 技术栈（工具调用、文件访问、多轮记忆），而不需要自己实现其中任何一部分。
