# Lab 9 Part 2: contributor-reported Android TWA results

The Windows contributor reports completing Android TWA verification on
2026-10-31, 18:12-18:15 America/Los_Angeles. This English version preserves the
scope of that report. The APK, screenshots and detailed JSON/log files referenced
below are not included in the merged Git tree. They must be supplied for an
independent review; no Android build or device run was performed on WSL.

## Reported outcome

A signed APK opened the HTTPS group-chat website in an Android Studio emulator.
Digital Asset Links validation passed and Chrome displayed no address bar.
Registration, login/logout, bidirectional WSS, local Llama replies, MySQL storage,
and history restoration after refresh/relogin were reported as verified.

The recorded website was `https://290b0adb97bf71.lhr.life/`; its association endpoint
was `/.well-known/assetlinks.json`. This was a temporary localhost.run tunnel,
not a permanent deployment. Its availability is not established by this report.
A new hostname requires updating configuration and rebuilding/reinstalling the APK.

## Environment and identity

| Item | Contributor's recorded value |
|---|---|
| Windows root | `C:\Project\EE542\Lab9` |
| Android project | `groupchat_app_src\twa_android_src` |
| Android Studio | Rabbit 2 2026.2.2.8 |
| Gradle / Android Gradle Plugin | 8.13 / 8.13.0 |
| JDK | Eclipse Temurin 21.0.7 |
| compileSdk / targetSdk / minSdk | 34 / 34 / 21 |
| Build Tools | 35.0.0 |
| Emulator | Medium_Phone_API_37.0, Android 17, API 37, x86_64 |
| Chrome | 145.0.7632.218 |
| Package / version | `com.helloworld.groupchat.twa` / 1.0 |
| Signing | Existing debug key; reported v1/v2 APK signature checks |
| Model | Local llama.cpp, Llama 3.1 8B Instruct, Q4_K_M |

Recorded certificate SHA-256:

```text
DA:2B:98:FC:35:C8:35:1A:4C:7B:C0:0F:44:88:94:4E:CA:0C:D1:76:79:E6:41:30:7C:9B:5E:78:7E:C1:CD:1D
```

Recorded `app-https-debug.apk` SHA-256:

```text
bb1a27a81bd493a5b96f4234666b10ee1493b251fc1320633cabfdf6c3ffc151
```

The report describes a normal Android Studio Generate APKs build, an official
Gradle Wrapper, INTERNET permission, HTTPS VIEW intent filter, app asset_statements,
and matching website package/certificate entries. It states that no Chrome flag
was used to bypass Digital Asset Links. The reported browser state was
`standalone=true` with the Android system status/navigation bars still visible.

## Evidence referenced by the contributor

| Requirement | Referenced local artifacts |
|---|---|
| IDE setup and successful build | `runtime-environment.json`, `ide-https-build-success.log` |
| Configuration and APK | `source-config/`, `build-verification.json`, `app-https-debug.apk` |
| Certificate / APK signatures | `debug-signing-certificate.txt`, `apk-https-signature.txt` |
| HTTPS and Digital Asset Links | `https-verification.json`, `google-dal-statements.json` |
| Verified TWA without address bar | `android-app-links.txt`, `twa-verification.json` |
| Real chat / database | `android-https-verification.json`, `mysql-evidence.json` |

The report records 16 HTTPS integration checks and 9 TWA/login checks, with database
message IDs 13-16 on that machine. Static screenshots are referenced as
`screenshots/android-https-01-login.png`, `02-realtime-llm.png`,
`03-history-restored.png`, and `04-twa-final.png` (each with the android-https prefix).
The final screenshot is the suggested video/report image. These files are absent
from this checkout; source/configuration alone does not reproduce those outcomes.

The recorded question was: "What is a Trusted Web Activity? Answer in one short
sentence." The recorded model answer described TWA as a Chrome feature allowing
web applications on Android with native-app-like security. This is a model output,
not an authoritative definition.

## Windows reproduction

Run from `C:\Project\EE542\Lab9` in PowerShell:

```powershell
.\scripts\start_part2_tunnel.ps1
```

The script reuses an active connection or creates a new temporary hostname and
updates Android/association settings. Rebuild using Android Studio Generate APKs,
then install and launch:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -e install -r .\groupchat_app_src\twa_android_src\app\build\outputs\apk\debug\app-debug.apk
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -e shell am start -n com.helloworld.groupchat.twa/com.google.androidbrowserhelper.trusted.LauncherActivity
```

Stop the public tunnel with `scripts/start_part2_tunnel.ps1 -Stop`. Stop the
script-managed website/model with `scripts/start_part1.ps1 -Stop`; MySQL is separate.
Use an existing private test account or create one in the website.

For device checks, forward Chrome DevTools and use the current HTTPS origin:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -e forward tcp:9224 localabstract:chrome_devtools_remote
.\groupchat_app_src\backend\.venv\Scripts\python.exe -B -u .\scripts\verify_part2_android.py --origin https://CURRENT_HOST --label android-https
.\groupchat_app_src\backend\.venv\Scripts\python.exe -B -u .\scripts\verify_part2_https.py
.\groupchat_app_src\backend\.venv\Scripts\python.exe -B -u .\scripts\verify_part2_twa.py
```

Use the combined backend dependencies when testing the new Part 4 website.
The earlier Part 2 run validates the earlier general-chat website, not the merged
Part 4 upload/retrieval/citation flow. That Android integration remains to be tested.

## Recorded limitations and troubleshooting

Cloudflare TLS attempts failed; the contributor switched to localhost.run with
user authorization. Emulator startup required a cold boot without clearing data,
and ADB needed restarting. Command-line Gradle encountered a Java NIO loopback
error; the reported successful build came from Android Studio. An initial HTTPS
verification reused a closed tunnel connection; disabling idle connection reuse
was reported to resolve it. Initial failure logs were retained on that machine.

No Android installation, emulator reset, APK rebuild or public tunnel was started
on WSL during the merge review.
