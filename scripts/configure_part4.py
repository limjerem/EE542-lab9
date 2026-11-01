"""Configure the final ADS app; association uses the origin, launch uses /ads/."""
import argparse,json,re,shutil,sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from configure_part2 import ANDROID,KEY,PACKAGE,FINGERPRINT

def configure(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.path not in ('','/') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an HTTPS origin without a path or credentials')
    origin='https://'+parsed.netloc
    paths=[ANDROID/'app/src/main/AndroidManifest.xml',ANDROID/'app/src/main/res/values/strings.xml',ANDROID/'app/build.gradle',ROOT/'groupchat_app_src/frontend/.well-known/assetlinks.json']
    backup=ROOT/'work/backups'/('part4-android-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    for path in paths:
        target=backup/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    tree=ET.parse(paths[0]);application=tree.getroot().find('application')
    application.set(KEY+'label','ADS Study');application.set(KEY+'icon','@drawable/ic_ads')
    activity=application.find('activity')
    for intent in activity.findall('intent-filter'):
        if any(action.get(KEY+'name')=='android.intent.action.VIEW' for action in intent.findall('action')):
            intent.set(KEY+'autoVerify','true')
            for data in intent.findall('data'):intent.remove(data)
            ET.SubElement(intent,'data',{KEY+'scheme':'https',KEY+'host':parsed.hostname})
    ET.indent(tree,space='    ');tree.write(paths[0],encoding='utf-8',xml_declaration=True)
    resources=ET.Element('resources')
    ET.SubElement(resources,'string',{'name':'defaultUrl','translatable':'false'}).text=origin+'/ads/'
    statements=[{'relation':['delegate_permission/common.handle_all_urls'],'target':{'namespace':'web','site':origin}}]
    ET.SubElement(resources,'string',{'name':'asset_statements','translatable':'false'}).text=json.dumps(statements,separators=(',',':')).replace('"','\\"')
    tree=ET.ElementTree(resources);ET.indent(tree,space='    ');tree.write(paths[1],encoding='utf-8',xml_declaration=True)
    gradle=paths[2].read_text(encoding='utf-8');gradle=re.sub(r'versionCode\s+\d+','versionCode 2',gradle);gradle=re.sub(r'versionName\s+"[^"]+"','versionName "2.0"',gradle);paths[2].write_text(gradle,encoding='utf-8')
    links=[{'relation':['delegate_permission/common.handle_all_urls'],'target':{'namespace':'android_app','package_name':PACKAGE,'sha256_cert_fingerprints':[FINGERPRINT]}}]
    paths[3].write_text(json.dumps(links,indent=2)+'\n',encoding='utf-8')
    drawable=ANDROID/'app/src/main/res/drawable';drawable.mkdir(exist_ok=True)
    (drawable/'ic_ads.xml').write_text('''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="108dp" android:height="108dp" android:viewportWidth="108" android:viewportHeight="108">
<path android:fillColor="#173c38" android:pathData="M0,0h108v108h-108z"/>
<path android:strokeColor="#b8e3c7" android:strokeWidth="5" android:strokeLineCap="round" android:fillColor="@android:color/transparent" android:pathData="M20,55 C32,25 36,25 48,55 S64,85 76,55 S88,25 94,45"/>
</vector>''',encoding='utf-8')
    output=ROOT/'outputs/part4';output.mkdir(parents=True,exist_ok=True)
    state=dict(origin=origin,launch_url=origin+'/ads/',package_name=PACKAGE,certificate_sha256=FINGERPRINT,version_name='2.0',version_code=2)
    (output/'android-origin.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    print('PART4_ANDROID_CONFIGURED',origin+'/ads/')
if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Use Lab9/.venv/Scripts/python.exe')
    parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);configure(parser.parse_args().url)
