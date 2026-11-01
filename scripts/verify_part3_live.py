"""Live OpenAI conversation and real command-line acceptance, with credentials kept local."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,time,subprocess,re
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from lab9_core.library import open_library,settings
from lab9_core.conversation import open_chat
OUT=ROOT/'outputs/part3'
checks=[]
def check(name,ok):
    checks.append({'name':name,'passed':bool(ok)});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    if not ok:raise AssertionError(name)
values=settings();collection=open_library();chat=open_chat(collection.vectors);calls=[];real=chat.model
class RecordRealModel:
    def invoke(self,messages):
        response=real.invoke(messages)
        calls.append({'model':response.response_metadata.get('model_name') or response.response_metadata.get('model'),'usage':response.usage_metadata})
        return response
chat.model=RecordRealModel()
report={'tested_at':datetime.now(timezone.utc).isoformat(),'real_openai':True,'chat_model':values.get('OPENAI_CHAT_MODEL'),'embedding_model':values.get('EMBEDDING_MODEL'),'checks':checks,'turns':[],'model_calls':calls}
try:
    for question in ['According to the ADS cookbook, how does tuning differ from optimization?','Which of those two is automated, and which is done manually?']:
        start=time.monotonic();result=chat.ask(question);result['question']=question;result['seconds']=round(time.monotonic()-start,2);report['turns'].append(result)
        check('answer cites retrieved passages',bool(re.search(r'\[\d+\]',result['answer'])))
        check('retrieved sources have real file and PDF page',all(s['filename'] and s['page']>=1 and len(s['text'])<=500 for s in result['sources']))
        print('REAL_ANSWER',result['answer'],flush=True)
    check('follow-up rewrites references into a standalone query','tuning' in report['turns'][1]['query'].lower() and 'optim' in report['turns'][1]['query'].lower())
    check('memory contains both completed turns',len(chat.history)==4)
    chat.clear();check('clear removes conversation memory',chat.history==[])
    question='What will the weather be in Los Angeles tomorrow?'
    result=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-B','-u','-X','utf8',str(ROOT/'embedding/documents_cli.py'),'--show-context'],input=question+'\n/clear\nexit\n',capture_output=True,text=True,encoding='utf-8',cwd=str(ROOT),timeout=180)
    (OUT/'cli-live.txt').write_text('INPUT: '+question+'\nINPUT: /clear\nINPUT: exit\n\n'+result.stdout+'\nSTDERR:\n'+result.stderr,encoding='utf-8')
    check('real CLI accepts questions, clear and exit',result.returncode==0 and 'Goodbye.' in result.stdout and 'Conversation memory cleared.' in result.stdout and 'Question failed' not in result.stdout)
    check('unsupported question is refused using document scope',bool(re.search(r'not (?:provide|contain|include|have)|do not|does not|no information|insufficient|not enough|cannot|can.t',result.stdout,re.I)))
    report['cli_question']=question;report['status']='passed'
finally:
    (OUT/'live-conversation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
