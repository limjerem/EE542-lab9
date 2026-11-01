# Lab 9 Part 2 实验结果

Part 2 已完成。最终 APK 在 Android Studio 模拟器中通过 HTTPS 打开群聊网站；Digital Asset Links 验证通过，Chrome 未显示地址栏。注册、登录/退出、WSS 双向实时消息、真实 Llama 回复、MySQL 保存，以及刷新/重新登录后的历史恢复均已验证。

完成时间：2026-10-31 18:12 至 18:15（America/Los_Angeles）；JSON 中的时间采用 UTC。

## 最终文件与地址

- 最终 HTTPS APK：[app-https-debug.apk](app-https-debug.apk)；`app-debug.apk` 是相同内容的便捷副本。
- 当前网站：https://290b0adb97bf71.lhr.life/
- 当前关联声明：https://290b0adb97bf71.lhr.life/.well-known/assetlinks.json
- 建议用于报告的主截图：[无地址栏的 TWA、Connected、双向消息和 Llama 回复](screenshots/android-https-04-twa-final.png)。
- 母目录：`C:\Project\EE542\Lab9`；Android 工程：`C:\Project\EE542\Lab9\groupchat_app_src\twa_android_src`。
- 本次没有注册账号、购买域名或付费。隧道由 localhost.run 提供，只转发网站的 8000 端口。

临时域名会过期或改变。当前 APK 固定指向上面的域名；演示期间请保持电脑、网站、模型和隧道运行。保存下来的 APK、截图、验证记录不依赖隧道继续运行。

## 与指导书 Part 2 的对应关系

| 指导书要求 | 实际完成情况 | 证据 |
|---|---|---|
| I：安装 Android Studio | Rabbit 2 2026.2.2.8 可正常打开、同步并编译工程 | `runtime-environment.json`、`ide-https-build-success.log` |
| II：打开工程、设置包名与 HTTPS defaultUrl、Build & Run | 包名 `com.helloworld.groupchat.twa`；配置实际 HTTPS 地址；APK 已安装运行 | `source-config/`、`build-verification.json` |
| III.1-2：使用签名密钥并取得 SHA-256 指纹 | 使用现有 Android debug 签名密钥；keytool 与 APK 签名得到相同指纹 | `debug-signing-certificate.txt`、`apk-https-signature.txt` |
| III.3-4：部署匹配包名和证书的 assetlinks.json | 公开 HTTPS 返回 200、application/json、无需登录、无重定向；包名与指纹一致 | `https-verification.json`、`google-dal-statements.json` |
| III.5：安装签名 APK，TWA 无 URL 栏 | Google DAL 返回正确关联；Android 域名状态 verified；实际截图无地址栏，浏览器 standalone=true | `android-app-links.txt`、`twa-verification.json`、HTTPS 截图 |
| IV：在 Android 手机或模拟器中编译、安装、测试网站 APK | 在 Android 17 / API 37 模拟器测试通过 | `android-https-verification.json`、`mysql-evidence.json` |

没有使用跳过 Digital Asset Links 验证的 Chrome 参数。页面以 standalone 模式显示，截图保留 Android 系统状态栏与手势导航栏。

## 环境、签名和实现

| 项目 | 值 |
|---|---|
| Android Studio | Rabbit 2 2026.2.2.8 |
| Gradle / AGP | 8.13 / 8.13.0 |
| Gradle JDK | Eclipse Temurin 21.0.7 |
| compileSdk / targetSdk / minSdk | 34 / 34 / 21 |
| Build-Tools | 35.0.0 |
| 模拟器 | Medium_Phone_API_37.0，Android 17，API 37，x86_64 |
| Chrome | 145.0.7632.218 |
| Android 包名 / 版本 | com.helloworld.groupchat.twa / 1.0 |
| APK 类型 | 使用 debug 密钥签名的课程测试 APK，v1/v2 签名验证通过 |
| Python | backend\.venv，所有 Python 安装与运行均在该虚拟环境内 |
| 模型 | 本机 llama.cpp，Llama 3.1 8B Instruct，Q4_K_M |

签名证书 SHA-256：

```text
DA:2B:98:FC:35:C8:35:1A:4C:7B:C0:0F:44:88:94:4E:CA:0C:D1:76:79:E6:41:30:7C:9B:5E:78:7E:C1:CD:1D
```

最终 APK 文件 SHA-256：

```text
bb1a27a81bd493a5b96f4234666b10ee1493b251fc1320633cabfdf6c3ffc151
```

工程修复包括：补齐官方 Gradle Wrapper 并验证校验值、统一 Gradle JDK；添加 INTERNET 权限、HTTPS VIEW intent filter 和应用侧 asset_statements；将网站 assetlinks.json 更新为实际包名和签名指纹。构建由正常桌面会话中的 Android Studio **Generate APKs** 完成。

## 实验现象与数据库结果

最终 HTTPS 集成检查 16 项通过，TWA 与登录验收 9 项通过。检查包含静态截图保存；详细逐项结果见两个 verification JSON。

Android 注册实验账号后显示 Connected。Android 发出的消息立即到达独立客户端；独立客户端发送的消息通过 WSS 到达 Android，无需刷新。问题由实际本地 Llama 模型回答，双方均收到广播。刷新及退出后重新登录，均能恢复连接和已保存的回复。

最终 HTTPS 测试的数据库记录为 messages.id 13-16，包含 Android 普通消息、另一客户端消息、问题、机器人回复；SQL 查询保存于 `mysql-evidence.json`。实验账号与记录保留，方便之后核对。

问题：What is a Trusted Web Activity? Answer in one short sentence.

实际模型回复：A Trusted Web Activity (TWA) is a Google Chrome feature that allows web applications to run on Android devices with the same level of security as native apps.

以上是模型实验输出，技术定义应以官方文档为准。

## 截图索引

全部为直接保存的静态 PNG，没有录屏，也未修改截图内容。

| 文件 | 用途 |
|---|---|
| `android-https-01-login.png` | HTTPS APK 的注册/登录页面，无地址栏 |
| `android-https-02-realtime-llm.png` | 实时消息与机器人回复 |
| `android-https-03-history-restored.png` | 刷新后的历史恢复 |
| `android-https-04-twa-final.png` | 最终登录恢复后的完整 TWA，建议作为报告主图 |
| `android-local-01` 至 `04` | 较早的 HTTP 本地测试，可用于对比有地址栏的 Custom Tab |

图片均在 `screenshots/`。较早的本地截图可能包含 Chrome 自然消失的密码提示；未操作保存密码。

## 启动、停止与复现

以下 PowerShell 命令均在母目录 `C:\Project\EE542\Lab9` 下执行。

启动或复用网站、Llama 与临时 HTTPS 隧道：

```powershell
.\scripts\start_part2_tunnel.ps1
```

当前连接仍运行时，脚本会复用它。若连接已停止，脚本会建立新临时地址、同步修改 Android URL 与关联配置，并提示重新构建。请在 Android Studio 中执行 **Generate APKs**，随后安装新 APK：

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -e install -r .\groupchat_app_src\twa_android_src\app\build\outputs\apk\debug\app-debug.apk
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -e shell am start -n com.helloworld.groupchat.twa/com.google.androidbrowserhelper.trusted.LauncherActivity
```

可使用已有课程测试账号 `lab9_demo`，实验口令为 `Lab9Demo!2026`，也可在网站自行注册实验账号。

仅关闭公网隧道：

```powershell
.\scripts\start_part2_tunnel.ps1 -Stop
```

关闭脚本管理的网站与模型进程：

```powershell
.\scripts\start_part1.ps1 -Stop
```

MySQL 是独立服务，上述停止命令不会关闭它。

### 再次验证

Python 必须使用本项目虚拟环境。Android 调试接口转发后，使用当前真实 HTTPS origin：

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -e forward tcp:9224 localabstract:chrome_devtools_remote
.\groupchat_app_src\backend\.venv\Scripts\python.exe -B -u .\scripts\verify_part2_android.py --origin https://当前域名 --label android-https
.\groupchat_app_src\backend\.venv\Scripts\python.exe -B -u .\scripts\verify_part2_https.py
.\groupchat_app_src\backend\.venv\Scripts\python.exe -B -u .\scripts\verify_part2_twa.py
```

验证工具会创建新的实验账号、消息，并保存结果和截图。verify_part2_https.py 会使用当前配置自动刷新 Google DAL 查询、HTTPS 和 TLS 验证记录。

## 排障记录与限制

- Cloudflare 临时入口持续在 TLS 握手阶段连接重置，因此经用户明确授权后改用 localhost.run；Cloudflare 失败日志保留为 `cloudflare-attempt.log`。
- 模拟器首次启动挂起，保留数据冷启动后恢复；重启 ADB 服务后连接正常，没有清空 AVD 数据。
- 自动化命令进程直接运行 Gradle 曾遇到 Java NIO 回环连接错误；实际成功构建来自 Android Studio。IDE 与系统安全配置未为此修改。
- HTTPS 验证工具首次复用了被隧道关闭的 HTTP 连接；工具改为不保留空闲连接后，完整验证通过。首次失败记录保留为 `android-https-initial-attempt.json`。
- 临时隧道用于课程实验，不提供永久域名。地址变化时必须更新配置、重新编译安装；已有截图和日志仍可作为本次实验的证据。

## 参考

- 指导书 lab9-f26.pdf 第 3 页，Part 2。
- [Chrome TWA Quick Start](https://developer.chrome.com/docs/android/trusted-web-activity/quick-start)
- [Chrome TWA Integration Guide](https://developer.chrome.com/docs/android/trusted-web-activity/integration-guide)
- [Google Digital Asset Links statements.list](https://developers.google.com/digital-asset-links/reference/rest/v1/statements/list)
- [localhost.run HTTP Tunnels](https://localhost.run/docs/http-tunnels)
- [localhost.run Free Tunnels](https://localhost.run/docs/forever-free)
