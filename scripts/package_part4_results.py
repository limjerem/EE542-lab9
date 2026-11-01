"""Package verified Part 4 evidence without secrets, indexes or publisher PDFs."""
import argparse,hashlib,html,importlib.metadata,json,platform,shutil,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/part4'
def write(name,data):(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main(destination):
    config=json.loads((OUT/'android-origin.json').read_text());origin=config['origin']
    reports={name:json.loads((OUT/(name+'.json')).read_text(encoding='utf-8')) for name in ['desktop-verification','android-verification','ui-race-verification']}
    assert all(r['status']=='passed' for r in reports.values())
    assert all(c['passed'] for r in reports.values() for c in r.get('checks',[]) if isinstance(c,dict))
    with httpx.Client(timeout=30) as client:
        local=client.get('http://127.0.0.1:8000/api/ads/health');public=client.get(origin+'/api/ads/health')
        assert local.status_code==200 and public.status_code==200 and public.json()['ready']
        groupchat=client.get('http://127.0.0.1:8000/');assert groupchat.status_code==200 and 'Group Chat' in groupchat.text
    apk=OUT/'ADS-Study-Companion-v2-debug.apk';native=ROOT/'groupchat_app_src/twa_android_src/app/build/outputs/apk/debug/app-debug.apk'
    digest=hashlib.sha256(apk.read_bytes()).hexdigest();assert digest==hashlib.sha256(native.read_bytes()).hexdigest()
    signature=(OUT/'apk-signature.txt').read_text(encoding='utf-8-sig')
    assert 'Verified using v2 scheme (APK Signature Scheme v2): true' in signature
    assert config['certificate_sha256'].replace(':','').lower() in signature
    metadata=json.loads((native.parent/'output-metadata.json').read_text())
    assert metadata['elements'][0]['versionCode']==2 and metadata['elements'][0]['versionName']=='2.0'
    build=dict(packaged_at=datetime.now(timezone.utc).isoformat(),built_at_local=datetime.fromtimestamp(native.stat().st_mtime,ZoneInfo('America/Los_Angeles')).isoformat(),
        package_name=config['package_name'],version_name='2.0',version_code=2,apk_file=apk.name,bytes=apk.stat().st_size,sha256=digest,
        certificate_sha256=config['certificate_sha256'],signature_verified=True,build_method='Android Studio Generate APKs, Gradle assembleDebug',
        launch_url=config['launch_url'],python_version=platform.python_version(),virtual_environment=str(Path(sys.prefix)),
        dependencies={p:importlib.metadata.version(p) for p in ['fastapi','uvicorn','langchain-openai','faiss-cpu','SQLAlchemy','openai']},
        unit_tests={'command':'.venv/Scripts/python.exe -B -m pytest -q tests','passed':17,'observed_result':'17 passed in 2.87s'},
        desktop_checks=len(reports['desktop-verification']['checks']),android_checks=len(reports['android-verification']['checks']),ui_race_check='passed')
    write('build-verification.json',build)
    write('deployment-status.json',dict(checked_at=datetime.now(timezone.utc).isoformat(),local_url='http://localhost:8000/ads/',launch_url=config['launch_url'],local_ready=True,public_https_ready=True,original_groupchat_ready=True))
    screenshot_manifest=[]
    for path in sorted((OUT/'screenshots').glob('*.png')):
        data=path.read_bytes();assert data.startswith(b'\x89PNG\r\n\x1a\n')
        screenshot_manifest.append(dict(file=path.relative_to(OUT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),method='adb exec-out screencap -p, unedited' if path.name.startswith('android-') else 'Playwright Chrome screenshot'))
    write('screenshot-manifest.json',screenshot_manifest)
    shutil.copy2(ROOT/'PART4.md',OUT/'PART4.md');shutil.copy2(ROOT/'part4/corpus.json',OUT/'corpus-manifest.json')
    corpus=json.loads((OUT/'corpus-verification.json').read_text())
    esc=lambda x:html.escape(str(x))
    checks=''.join('<tr><td>'+esc(name)+'</td><td>PASS</td><td><a href="'+name+'.json">核验记录</a></td></tr>' for name in reports)
    source_manifest=json.loads((ROOT/'part4/corpus.json').read_text())
    sources=''.join(f'<tr><td><a href="{esc(s["url"])}">{esc(s["title"])}</a></td><td>{esc(s["edition"])}</td><td>{s["pages"]}</td><td>{corpus["per_source"][s["id"]]}</td></tr>' for s in source_manifest['sources'])
    images=[('desktop-01-home.png','桌面首页'),('desktop-02-library.png','正式资料库'),('desktop-04-answer.png','真实问答'),('android-12-clean-home.png','Android 首页'),('android-13-final.png','Android 中英文追问'),('android-09-clean-source.png','Android 原文与页码')]
    gallery=''.join(f'<figure><a href="screenshots/{name}"><img loading="lazy" src="screenshots/{name}" alt="{label}"></a><figcaption>{label}</figcaption></figure>' for name,label in images)
    body=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lab9 Part4 实验结果</title>
<style>body{{margin:0;background:#f3f6f2;color:#203d35;font:16px/1.8 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1100px;margin:auto;padding:44px 28px}}h1{{font-size:36px;line-height:1.3}}h2{{margin-top:42px}}a{{color:#246b55}}.lead{{font-size:19px;max-width:900px}}.stats{{display:flex;flex-wrap:wrap;gap:18px;margin:30px 0}}.stat{{background:white;border:1px solid #d7e3d8;border-radius:14px;padding:18px 24px;flex:1;min-width:150px}}.stat b{{display:block;font-size:28px}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:12px;border:1px solid #d9e4d8;text-align:left}}.gallery{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;align-items:start}}figure{{margin:0;background:white;padding:10px;border-radius:12px;border:1px solid #dbe5d9}}img{{display:block;max-width:100%;height:auto}}figcaption{{padding:8px 3px;font-size:14px}}code{{background:#e5eee4;padding:3px 6px;border-radius:5px}}.note{{font-size:14px;color:#6a7f70}}@media(max-width:760px){{.gallery{{grid-template-columns:1fr 1fr}}main{{padding:25px 16px}}table{{font-size:12px}}td,th{{padding:8px}}}}</style>
<main><p>EE542 · LAB 9 · PART 4</p><h1>ADS Study Companion 实验结果</h1><p class="lead">面向学习 ADS 的 EE/RF 学生，完成正式资料库、带来源的中英文问答网站和 Android TWA。回答可展开查看原文、版本与 PDF 页码；聊天历史按账号保存。</p>
<div class="stats"><div class="stat"><b>4 / 462</b>份官方资料 / PDF 页</div><div class="stat"><b>2,552</b>正式向量片段</div><div class="stat"><b>17</b>后端测试通过</div><div class="stat"><b>HTTPS + TWA</b>真实关联验证通过</div></div>
<p><a href="ADS-Study-Companion-v2-debug.apk">下载 Android APK v2.0</a> · <a href="PART4.md">完整运行说明</a> · <a href="build-verification.json">APK 哈希与环境</a></p>
<p>本机：<a href="http://localhost:8000/ads/">http://localhost:8000/ads/</a><br>当前 HTTPS：<a href="{esc(config['launch_url'])}">{esc(config['launch_url'])}</a></p><p class="note">临时隧道需要保持电脑、网站和 SSH 进程运行。免费域名更换后，需更新 Android 配置并重新生成 APK。资料范围为 ADS 2011 系列。</p>
<h2>资料整理</h2><table><tr><th>官方资料</th><th>版本</th><th>PDF 页</th><th>去重片段</th></tr>{sources}</table><p class="note">排除封面、版权等前置页、测试摘录和重复片段；校验来源 SHA-256。FAISS 向量维度 1,536。复用 763 条已有向量，新增 1,789 条。原 Part 3 的 784 条上传片段保持完整。</p>
<h2>验收记录</h2><table><tr><th>范围</th><th>结果</th><th>证据</th></tr>{checks}</table><p>桌面 {build['desktop_checks']} 项检查、Android {build['android_checks']} 项检查通过。包括实际模型调用、中文追问、引用、MySQL 保存、刷新恢复、账号隔离与请求去重。专门的延迟响应测试验证了新建会话不会被旧历史覆盖。</p><p>Google Digital Asset Links 和 Android 域名验证均通过；页面报告 secure standalone，UI 层级没有 Chrome 地址栏或工具栏。<a href="google-dal.json">Google DAL</a> · <a href="android-app-links.txt">Android App Links</a> · <a href="android-window.xml">实际 UI 层级</a></p>
<h2>可用于报告的截图</h2><p class="note">点击查看原图。Android 图片为直接截图，未编辑；没有录屏。完整图片目录及哈希见 <a href="screenshot-manifest.json">截图清单</a>。补拍时模拟器曾出现一次 0xC0000005 进程退出，冷启动恢复；问答与关联验收已在退出前通过。</p><div class="gallery">{gallery}</div><p class="note">测试日期：2026-10-31（America/Los_Angeles）。此页是 Part 4 实验结果索引，完整跨 Part 实验报告另行整理。</p></main></html>'''
    (OUT/'实验结果.html').write_text(body,encoding='utf-8')
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    copied=destination/'Lab9-Part4';copied.mkdir(exist_ok=True)
    selected=[]
    for path in OUT.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.json','.txt','.xml','.md','.html','.png','.apk'}:
            target=copied/path.relative_to(OUT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);selected.append(path)
    archive=destination/'Lab9-Part4-results.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in selected:bundle.write(path,path.relative_to(OUT).as_posix())
    print(json.dumps(dict(status='packaged',files=len(selected),archive=str(archive),apk_sha256=digest,desktop_checks=build['desktop_checks'],android_checks=build['android_checks']),ensure_ascii=True),flush=True)
if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use the project virtual environment')
    parser=argparse.ArgumentParser();parser.add_argument('--destination',required=True);main(parser.parse_args().destination)
