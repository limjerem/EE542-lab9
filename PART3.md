# Lab9 Part 3：本机检查与运行结果

已以队友仓库提交 `1a4703d4f76e9367626ae54ee073ee0fa6a5be3a` 为基础完成本机运行、问题复现、针对性修复与真实 OpenAI 验收。程序目前运行于 http://127.0.0.1:8501 。

工作母目录：`C:\Project\EE542\Lab9`。Part 3 使用独立虚拟环境 `C:\Project\EE542\Lab9\.venv`；原来的 `groupchat_app_src\backend\.venv` 保留给 Part 1/2。

## 现在如何使用

1. 打开 http://127.0.0.1:8501 。
2. 点击左侧 **Load saved index**，即可对现有文档提问。
3. 上传新文件后点击 **Process**。支持单个/多个 PDF、TXT、MD、HTML。
4. 展开 **Retrieved passages** 可查看本轮实际检索片段、文件名和页码。
5. **Clear conversation** 清除本次对话记忆，保留数据库和向量索引。

本机启动入口是 `embedding/upload_app.py`；`embedding/app.py` 是仓库保留的原始教学示例。Part 3 网页与 Part 1 的 8000 端口群聊独立，Android 整合属于后续 Part 4。

## 发现并修复的问题

| 问题 | 已复现的影响 | 修复 |
|---|---|---|
| 检索与索引更新并发 | 旧 FAISS 检索位置可能配上新一代文档，返回错误片段 | 索引加载加锁；一次查询持有匹配的索引与文档快照 |
| 索引 JSON 未指定读取编码 | Windows 非 UTF-8 默认编码下，中文和特殊字符乱码 | 索引元数据和 CURRENT 指针显式使用 UTF-8 |
| 历史回答的来源丢失 | 第二次提问后，上一轮 Retrieved passages 消失 | 将来源与回答一起存入会话，统一渲染新旧消息 |
| 配置文件中的 RAG_REUSE_ONLY 未生效 | 本地配置要求仅复用缓存时，仍可能请求新嵌入 | 将合并后的配置明确传入向量存储，并保留环境变量兼容性 |

修复前的四项失败复现保存为 `review-reproductions.txt`。原有七项测试和新增五项回归测试，修复后全部通过。新增第五项验证额度错误提示可操作且不会回显密钥。

同时补充了课程 PDF 字体解析所需的 `fonttools`；为网页/CLI 增加明确的 OpenAI 额度错误提示；上传界面验证脚本可通过 `PLAYWRIGHT_BROWSER_CHANNEL=chrome` 复用本机 Chrome。

原源码备份位于 `work/backups/part3-review-20261031-200626`。本次修改保留在本地，尚未提交或推送到 GitHub。

## 验收结果

| 检查 | 结果 | 文件 |
|---|---|---|
| 自动回归测试 | 12 passed | `local-tests.txt` |
| 依赖一致性 | pip check 通过 | `pip-check.txt` |
| 完整课程 PDF 真实向量化 | 124 页、771 个向量、1536 维 | `native-index.json`、`native-index-build.txt` |
| MySQL 文本、页、文本块与向量持久化 | 5 份文档、128 页、784 个文本块/向量 | `library-verification.json` |
| 去重与缓存复用 | 重复处理、索引重载通过；该复核阶段 0 次外部 API 请求 | `library-verification.txt` |
| 真实网页文件上传 | 单 PDF、多 PDF、TXT/HTML、重复处理、重载、清空共 6 个场景通过 | `upload-ui.json` |
| 真实 OpenAI 检索对话与命令行 | 9 项检查通过，包含连续追问、引用、清空、范围外拒答和 exit | `live-conversation.json`、`cli-live.txt` |
| 真实 OpenAI 网页问答 | 5 项检查通过，包含两轮回答、历史引用保留与重载 | `live-browser.json` |
| 中文实际问答与控制台编码 | 中文输入、中文带引用回答、exit 均通过 | `chinese-acceptance.json`、`cli-chinese.txt` |
| Part 1/2 保留 | 22 个受保护文件哈希均未改变 | `summary.json` |

回归测试中的离线替身仅用于故障复现。在线验收使用真实 OpenAI Embeddings 和 GPT 回答，未用本地 Llama 或固定答案替代。

OpenAI 嵌入模型：`text-embedding-3-small`；问答模型：`gpt-6-luna`。API 最初返回额度耗尽，用户处理额度后已成功完成全部真实调用；当前无需再处理该错误。初次错误记录单独保留为 `openai-connection-initial-quota.json`。

## 实际问答与向量样例

问题：According to the ADS cookbook, how does tuning differ from optimization?

实际回答：Tuning is a manual process: you change component values and observe how circuit performance changes. Optimization is automated: ADS modifies component values to meet specified performance goals. [1]

追问：Which of those two is automated, and which is done manually?

实际回答：Optimization is automated; tuning is done manually. [1]

问题超出文档范围时，例如询问洛杉矶明天天气，实际回答明确说明检索文档不包含天气信息。

- `embedding-example.json` 保存实际来源片段、对应问题与回答、相似度和向量前 16 个分量。
- `embedding-example.npy` 保存该片段完整的 1536 维实际向量，已按代码进行 L2 归一化。
- 来源页码是上传 PDF 的物理页位置；例如单页摘录中的 PDF page 1 对应原课程 PDF 的第 5 页。

## 截图

只保存静态 PNG，没有录屏，也未修改截图内容。

- [上传库与已有文档](screenshots/01-upload-library.png)
- [真实检索问答](screenshots/02-live-answer.png)
- [连续追问](screenshots/03-live-answer.png)
- [连续追问与实际来源片段](screenshots/04-followup-with-sources.png)
- [清空对话后的状态](screenshots/05-conversation-cleared.png)
- `upload-interface.png` 为队友上传验证脚本在本机运行后的截图。

## 本机启动与停止

以下命令在母目录 `C:\Project\EE542\Lab9` 下执行。

```powershell
.\scripts\start_part3.ps1
```

停止：

```powershell
.\scripts\start_part3.ps1 -Stop
```

脚本只管理 Part 3 的 8501 端口服务。更改 API key、问答模型或本地配置后，停止再启动以刷新缓存资源。

直接运行命令等价于：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m streamlit run embedding/upload_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

命令行问答：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 .\embedding\documents_cli.py --show-context
```

输入 `exit` 退出，`/clear` 清空记忆。

批量读取文件夹并入库：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 .\embedding\documents_cli.py --folder "C:\你的文档目录" --show-context
```

同一向量索引支持一个写入进程。通过 CLI 批量导入时，先停止网页服务；普通 CLI 提问可与网页同时使用。

## 本地数据与配置

- 配置：`embedding/.env.upload`，已被 Git 忽略。不要把它复制到报告或提交到仓库。
- 原课程 PDF 索引：`embedding/index_data/`。
- 上传库索引与持久化向量缓存：`embedding/upload_index/`。
- 课程 PDF 和本机生成的测试摘录保留在原位置与 `local_artifacts/part3-upload-fixtures/`。
- MySQL 使用现有 `groupchat` 数据库中的 `rag_documents`、`rag_pages`、`rag_chunks`，未改动原群聊表。
- 每轮对话记忆保留最近六轮，浏览器刷新后需重新加载索引；向量和原文继续保留。
- 新文档首次处理、问题嵌入和回答会调用 OpenAI；已缓存的相同文本无需重复做文档嵌入。

## 再次验证

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m pytest tests -q
.\.venv\Scripts\python.exe -m pip check
$env:RAG_REUSE_ONLY='1'
.\.venv\Scripts\python.exe -B -X utf8 scripts/verify_library.py
$env:PLAYWRIGHT_BROWSER_CHANNEL='chrome'
.\.venv\Scripts\python.exe -B -X utf8 scripts/verify_upload_ui.py
.\.venv\Scripts\python.exe -B -X utf8 scripts/verify_part3_live.py
.\.venv\Scripts\python.exe -B -X utf8 scripts/verify_part3_browser.py
```

最后两项会再次调用真实 OpenAI 并覆盖对应结果。完整依赖版本见 `requirements.lock.txt`；本次使用 Python 3.13.6，所有安装与执行均在 Part 3 虚拟环境中。

## 参考

- [OpenAI GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [OpenAI Embeddings](https://developers.openai.com/api/docs/guides/embeddings)
- [OpenAI 错误码](https://developers.openai.com/api/docs/guides/error-codes)
- [Playwright 浏览器支持](https://playwright.dev/python/docs/browsers)
