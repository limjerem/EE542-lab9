"""Configure the TWA origin and website association for the existing debug signing key."""
import argparse,json,shutil,sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent.parent
ANDROID=ROOT/'groupchat_app_src/twa_android_src'
ANDROID_NS='http://schemas.android.com/apk/res/android'
ET.register_namespace('android',ANDROID_NS)
KEY='{'+ANDROID_NS+'}'
PACKAGE='com.helloworld.groupchat.twa'
FINGERPRINT='DA:2B:98:FC:35:C8:35:1A:4C:7B:C0:0F:44:88:94:4E:CA:0C:D1:76:79:E6:41:30:7C:9B:5E:78:7E:C1:CD:1D'

def configure(url):
    origin=urlsplit(url)
    if origin.scheme not in ('http','https') or not origin.hostname or origin.username or origin.password:
        raise ValueError('Provide an HTTP(S) origin without embedded credentials')
    if origin.path not in ('','/') or origin.query or origin.fragment:
        raise ValueError('Provide the site origin, without a subpath/query')
    site=f'{origin.scheme}://{origin.netloc}'
    manifest=ANDROID/'app/src/main/AndroidManifest.xml'
    strings=ANDROID/'app/src/main/res/values/strings.xml'
    assetlinks=ROOT/'groupchat_app_src/frontend/.well-known/assetlinks.json'
    backup=ROOT/'work/backups'/('twa-origin-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    for path in (manifest,strings,assetlinks):
        target=backup/path.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    tree=ET.parse(manifest);root=tree.getroot();application=root.find('application')
    if not any(e.get(KEY+'name')=='android.permission.INTERNET' for e in root.findall('uses-permission')):
        root.insert(0,ET.Element('uses-permission',{KEY+'name':'android.permission.INTERNET'}))
    if not any(e.get(KEY+'name')=='asset_statements' for e in application.findall('meta-data')):
        ET.SubElement(application,'meta-data',{KEY+'name':'asset_statements',KEY+'resource':'@string/asset_statements'})
    activity=application.find('activity')
    for intent in list(activity.findall('intent-filter')):
        if any(action.get(KEY+'name')=='android.intent.action.VIEW' for action in intent.findall('action')):
            activity.remove(intent)
    intent=ET.SubElement(activity,'intent-filter',{KEY+'autoVerify':'true' if origin.scheme=='https' else 'false'})
    ET.SubElement(intent,'action',{KEY+'name':'android.intent.action.VIEW'})
    for category in ('android.intent.category.DEFAULT','android.intent.category.BROWSABLE'):
        ET.SubElement(intent,'category',{KEY+'name':category})
    data={KEY+'scheme':origin.scheme,KEY+'host':origin.hostname}
    if origin.port:data[KEY+'port']=str(origin.port)
    ET.SubElement(intent,'data',data)
    ET.indent(tree,space='    ');tree.write(manifest,encoding='utf-8',xml_declaration=True)
    resources=ET.Element('resources')
    ET.SubElement(resources,'string',{'name':'defaultUrl','translatable':'false'}).text=site+'/'
    statements=[{'relation':['delegate_permission/common.handle_all_urls'],'target':{'namespace':'web','site':site}}]
    ET.SubElement(resources,'string',{'name':'asset_statements','translatable':'false'}).text=json.dumps(statements,separators=(',',':')).replace('"','\\"')
    tree=ET.ElementTree(resources);ET.indent(tree,space='    ');tree.write(strings,encoding='utf-8',xml_declaration=True)
    links=[{'relation':['delegate_permission/common.handle_all_urls'],'target':{'namespace':'android_app','package_name':PACKAGE,'sha256_cert_fingerprints':[FINGERPRINT]}}]
    assetlinks.write_text(json.dumps(links,indent=2)+'\n',encoding='utf-8')
    state={'origin':site,'package_name':PACKAGE,'certificate_sha256':FINGERPRINT,'https':origin.scheme=='https','status':'configured; build and device verification pending'}
    (ROOT/'outputs/part2/origin-config.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    print('TWA_ORIGIN_CONFIGURED',site,flush=True)
    print('WEBSITE_ASSET_LINKS_UPDATED',flush=True)

if __name__=='__main__':
    if sys.prefix==sys.base_prefix:raise SystemExit('Run with backend/.venv/Scripts/python.exe')
    parser=argparse.ArgumentParser();parser.add_argument('--url',required=True)
    configure(parser.parse_args().url)
