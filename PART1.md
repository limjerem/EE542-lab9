# Lab9 Part 1

工作母目录：`C:\Project\EE542\Lab9`

## 已配置的系统

- 网站：<http://localhost:8000/>，FastAPI + HTML/CSS/JavaScript。
- MySQL：`127.0.0.1:3306/groupchat`，应用账号 `chatuser`。连接密码仅保存在应用 `.env` 中。
- 本地模型：Meta Llama 3.1 8B Instruct，Q4_K_M，4096 上下文，RTX 4060 CUDA 加速。
- 模型服务：`http://127.0.0.1:8001/v1`，模型别名 `llama-3.1-8b-instruct`。
- Python：仅使用 `groupchat_app_src\backend\.venv`，Python 3.13.6。

## 启动与停止

先确认 MySQL 服务正在运行。在 PowerShell 中执行：

```powershell
Set-Location 'C:\Project\EE542\Lab9'
.\scripts\start_part1.ps1
```

模型和网站会在后台启动，重复运行会复用已就绪的服务。

```powershell
.\scripts\start_part1.ps1 -Stop
```

停止操作仅针对脚本记录且启动时间匹配的模型、网站进程，不会停止 MySQL。
日志位于 `work\logs`。

## 网页演示

1. 打开 <http://localhost:8000/>。
2. 注册自己的账号（用户名至少 3 个字符，密码至少 8 个字符且不超过 72 个 UTF-8 字节）。
3. 或使用本地演示账号 `lab9_demo`，密码 `Lab9Demo!2026`。
4. 发送普通消息，验证聊天；发送含英文 `?` 或中文 `？` 的问题，验证机器人回答。
5. 用两个浏览器会话登录不同账号，验证消息实时同步。
6. 刷新网页，验证历史记录保留；点击 Log Out 退出。

当前 `.env` 位于 `groupchat_app_src\.env`。JWT 密钥已配置；数据库、JWT 和可选模型 API 密钥均不应提交到版本库。

## Python 安装与复验

所有命令明确调用虚拟环境，不依赖终端是否已经激活环境。

```powershell
& '.\groupchat_app_src\backend\.venv\Scripts\python.exe' -m pip install -r '.\groupchat_app_src\backend\requirements.lock.txt'
& '.\groupchat_app_src\backend\.venv\Scripts\python.exe' -B -u '.\scripts\verify_part1.py'
```

复验调用真实 MySQL 和本地模型，检查注册、登录、拒绝未授权访问、双用户 WebSocket 广播、英文及中文问题触发、真实模型回复、密码哈希和消息落库。脚本仅清理该次创建的测试数据。结果保存于 `work\part1-verification.json`。

## 本次补齐的内容

- 显式声明 `sqlalchemy[asyncio]`，包含异步数据库所需的 greenlet。
- 直接使用 bcrypt，兼容已有 bcrypt 密码哈希，并校验密码字节长度。
- WebSocket 登录认证；JWT 通过首条消息发送，不放在 URL 中。
- 登出关闭连接；断线重连并补取历史；合并消息避免重复。
- 支持中英文问号和 Enter 发送，提供等待回复与错误反馈。

## 模型文件来源

- llama.cpp 官方构建：b12023 / CUDA 12.4。
- 模型：https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF
- 模型版本：bf5b95e96dac0462e2a09145ec66cae9a3f12067。
- 模型及两个运行时压缩包均已核验 SHA-256；具体 URL、大小和校验值见 `tools\llama.cpp\provenance.json`。

Part 1 实现通用群聊和 Llama 回答。文档知识库检索与自定义直方图 Embedding 属于后续实验部分。
