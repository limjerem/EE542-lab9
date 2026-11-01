'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = {token: localStorage.getItem('token'), username: localStorage.getItem('ads.username') || '', conversation: null, busy: false, retry: null, navVersion: 0};
  const node = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
  const remember = () => `ads.conversation.${state.username}`;
  function notice(text) { $('notice').textContent = text || ''; $('notice').classList.toggle('success', !!text && /^(Saved|New conversation|Signed out)/.test(text)); }
  function closeRail() { $('rail').classList.remove('open'); $('railScrim').classList.remove('open'); }
  function view(name) {
    for (const key of ['chat','library','about']) $(key + 'View').classList.toggle('hidden', name !== key);
    document.querySelectorAll('[data-view]').forEach(el => el.classList.toggle('active', el.dataset.view === name));
    $('viewLabel').textContent = {chat:'Study workspace',library:'Source library',about:'How it works'}[name];
    closeRail();
  }
  async function api(path, options = {}) {
    const headers = {'Content-Type':'application/json', ...(options.headers || {})};
    if (state.token) headers.Authorization = 'Bearer ' + state.token;
    let response;
    try { response = await fetch('/api' + path, {...options, headers}); }
    catch (_) { throw new Error('Connection interrupted. Please check the connection and retry.'); }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401 && state.token) { logout(); notice('Please sign in again.'); }
      const message = typeof data.detail === 'string' ? data.detail : 'Please check your input and try again.';
      const error = new Error(message); error.status = response.status; throw error;
    }
    return data;
  }
  function identity() {
    $('identity').textContent = state.token ? state.username || 'Study account' : 'Your study workspace';
    $('signIn').classList.toggle('hidden', !!state.token);
    $('logout').classList.toggle('hidden', !state.token);
    $('composeHint').textContent = state.token ? 'Enter to send · Shift + Enter for a new line' : 'Sign in to ask and save your study history';
  }
  function resetConversation() {
    state.navVersion++; state.conversation = null; state.retry = null; $('thread').replaceChildren();
    $('thread').classList.add('hidden'); $('welcome').classList.remove('hidden');
  }
  function logout() {
    state.token = null; state.username = ''; localStorage.removeItem('token'); localStorage.removeItem('ads.username');
    resetConversation(); $('history').replaceChildren(); identity();
  }
  function showSource(source, index) {
    $('sourceTitle').textContent = `[${index + 1}] ${source.title}`;
    $('sourceMeta').textContent = `${source.edition} · PDF page ${source.page} · ${source.publisher}`;
    $('sourceQuote').textContent = source.text;
    const link = new URL(source.url);
    // Only official source URLs from our curated manifest are exposed.
    $('sourceLink').href = link.href.split('#')[0] + '#page=' + source.page;
    $('sourceDialog').showModal();
  }
  function inline(parent, text, sources) {
    const re = /(\[\d+\]|\*\*[^*\n]+\*\*|`[^`\n]+`)/g;
    let start = 0;
    for (const match of text.matchAll(re)) {
      parent.append(document.createTextNode(text.slice(start, match.index)));
      const token = match[0];
      if (/^\[\d+\]$/.test(token)) {
        const i = Number(token.slice(1,-1)) - 1;
        if (sources[i]) { const b = node('button','citation',token); b.type='button'; b.title=`View source ${i+1}`; b.onclick=()=>showSource(sources[i],i); parent.append(b); }
        else parent.append(document.createTextNode(token));
      } else parent.append(node(token.startsWith('**') ? 'strong' : 'code','',token.slice(token.startsWith('**') ? 2 : 1,token.startsWith('**') ? -2 : -1)));
      start = match.index + token.length;
    }
    parent.append(document.createTextNode(text.slice(start)));
  }
  function renderAnswer(parent, text, sources) {
    for (const block of text.split(/\n\s*\n/)) {
      const p=node('p');
      for (const [index,line] of block.split('\n').entries()) {
        if (index) p.append(document.createElement('br'));
        inline(p,line.replace(/^#{1,4}\s*/,''),sources);
      }
      parent.append(p);
    }
  }
  function appendTurn(turn) {
    const wrap=node('article','turn');
    wrap.append(node('div','question-bubble',turn.question));
    const card=node('div','answer-card'); card.append(node('div','answer-label','∿  ADS STUDY COMPANION'));
    const body=node('div','answer-body'); renderAnswer(body,turn.answer,turn.sources); card.append(body);
    const details=node('details','sources'); details.append(node('summary','',`${turn.sources.length} retrieved passages · view original sources`));
    const list=node('div','source-list');
    turn.sources.forEach((source,index)=>{
      const b=node('button','source-item'); b.type='button';
      b.append(node('strong','',`[${index+1}] ${source.title}`),node('span','',`${source.edition} · PDF page ${source.page}`));
      b.onclick=()=>showSource(source,index); list.append(b);
    });
    details.append(list);card.append(details);wrap.append(card);$('thread').append(wrap);
    $('welcome').classList.add('hidden');$('thread').classList.remove('hidden');
  }
  function scrollBottom() { requestAnimationFrame(()=>{ const el=$('thread'); el.scrollTop=el.scrollHeight; }); }
  async function history() {
    if (!state.token) return;
    const token=state.token;const data=await api('/ads/conversations');if(token!==state.token)return;$('history').replaceChildren();
    if (!data.conversations.length) $('history').append(node('p','history-empty','Your saved conversations appear here.'));
    for (const item of data.conversations) {
      const b=node('button',item.id===state.conversation ? 'current' : '',item.title);
      b.type='button';b.title=item.title;b.onclick=()=>loadConversation(item.id).catch(e=>notice(e.message));$('history').append(b);
    }
  }
  async function loadConversation(id) {
    if (state.busy) return;
    const version=++state.navVersion,token=state.token;const data=await api('/ads/conversations/'+id);if(version!==state.navVersion||token!==state.token||state.busy)return;resetConversation();state.conversation=id;localStorage.setItem(remember(),id);
    data.turns.forEach(appendTurn);view('chat');notice('');scrollBottom();await history();
  }
  async function restore() {
    const version=state.navVersion;identity();await history();if(version!==state.navVersion||!state.token)return;const id=localStorage.getItem(remember());
    if (id) { try {await loadConversation(id);} catch(e) {if(e.status===404)localStorage.removeItem(remember());else throw e;} }
  }
  async function authenticate(signup) {
    $('authError').textContent='';if (!$('authForm').reportValidity()) return;
    const username=$('username').value.trim();const password=$('password').value;
    $('loginButton').disabled=true;$('signupButton').disabled=true;
    try {
      const data=await api(signup ? '/signup' : '/login',{method:'POST',body:JSON.stringify({username,password})});
      state.token=data.token;state.username=data.username || username;
      localStorage.setItem('token',state.token);localStorage.setItem('ads.username',state.username);
      $('password').value='';notice('');await restore();$('authDialog').close();$('question').focus();
    } catch(e) {$('authError').textContent=e.message;}
    finally {$('loginButton').disabled=false;$('signupButton').disabled=false;}
  }
  function showAuth() { $('authError').textContent='';$('authDialog').showModal();$('username').focus(); }
  async function submit(event) {
    if(event)event.preventDefault();if(state.busy)return;
    const question=$('question').value.trim();if(!question)return;
    if(!state.token){showAuth();return;}
    state.navVersion++;state.busy=true;$('send').disabled=true;$('question').disabled=true;notice('Searching the manuals and preparing an answer…');
    const thinking=node('div','thinking','Searching the ADS collection…');
    try {
      if(!state.conversation){const data=await api('/ads/conversations',{method:'POST'});state.conversation=data.id;localStorage.setItem(remember(),data.id);}
      if(!state.retry || state.retry.question!==question || state.retry.conversation_id!==state.conversation)
        state.retry={conversation_id:state.conversation,request_id:crypto.randomUUID ? crypto.randomUUID() : '10000000-1000-4000-8000-100000000000'.replace(/[018]/g,c=>(c^crypto.getRandomValues(new Uint8Array(1))[0]&15>>c/4).toString(16)),question};
      $('thread').append(thinking);$('thread').classList.remove('hidden');scrollBottom();
      const result=await api('/ads/ask',{method:'POST',body:JSON.stringify(state.retry)});
      thinking.remove();appendTurn(result);state.retry=null;$('question').value='';$('question').style.height='';notice('Saved to your study history.');await history();scrollBottom();
    } catch(e) {thinking.remove();notice(e.message);if(e.status===404){localStorage.removeItem(remember());resetConversation();}}
    finally {state.busy=false;$('send').disabled=false;$('question').disabled=false;$('question').focus();}
  }
  async function library() {
    const data=await api('/ads/library');$('sourceCount').textContent=data.source_count;$('pageCount').textContent=data.pages;
    $('readyText').textContent='Source-backed answers';$('libraryCards').replaceChildren();
    data.sources.forEach((source,index)=>{
      const card=node('article','library-card');card.append(node('span','source-index',String(index+1).padStart(2,'0')),node('h2','',source.title),node('p','',source.topic));
      card.append(node('div','source-meta',`${source.edition} · ${source.pages} PDF pages`));
      const a=node('a','', 'Open official PDF ↗');a.href=source.url;a.target='_blank';a.rel='noopener';card.append(a);$('libraryCards').append(card);
    });
  }
  document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>view(b.dataset.view));
  document.querySelectorAll('[data-question]').forEach(b=>b.onclick=()=>{view('chat');$('question').value=b.dataset.question;$('question').focus();});
  $('menu').onclick=()=>{$('rail').classList.add('open');$('railScrim').classList.add('open');};$('railScrim').onclick=closeRail;
  $('newChat').onclick=()=>{if(state.busy)return;localStorage.removeItem(remember());resetConversation();view('chat');notice('New conversation. Your previous conversations are saved.');history().catch(e=>notice(e.message));$('question').focus();};
  $('signIn').onclick=showAuth;$('closeAuth').onclick=()=>$('authDialog').close();$('closeSource').onclick=()=>$('sourceDialog').close();
  $('logout').onclick=()=>{if(!state.busy){logout();closeRail();notice('Signed out.');}};
  $('authForm').onsubmit=e=>{e.preventDefault();authenticate(false);};$('signupButton').onclick=()=>authenticate(true);
  $('questionForm').onsubmit=submit;$('question').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit();}};
  $('question').oninput=()=>{$('question').style.height='auto';$('question').style.height=Math.min($('question').scrollHeight,150)+'px';};
  identity();library().catch(e=>{$('readyText').textContent='Connection unavailable';notice(e.message);});
  if(state.token)restore().catch(e=>notice(e.message));
})();
