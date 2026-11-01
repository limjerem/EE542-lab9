const $ = (id) => document.getElementById(id);
const API = '/api';
let token = localStorage.getItem('token') || '';
let username = localStorage.getItem('username') || '';
let ws, epoch = 0, uploadsAvailable = false, uploadBusy = false;
const messages = new Map(), pending = new Set(), answered = new Set();

function feedback(id, text) { $(id).textContent = text; }
function pendingStatus() {
  feedback('botStatus', pending.size ? `Assistant is answering ${pending.size} question(s)...` : '');
}
function logout() {
  epoch += 1; token = ''; username = '';
  localStorage.removeItem('token'); localStorage.removeItem('username');
  if (ws) ws.close();
  messages.clear(); pending.clear(); answered.clear();
  $('auth').classList.remove('hidden'); $('chat').classList.add('hidden');
}
async function callAPI(path, method = 'GET', body) {
  const headers = {Authorization: `Bearer ${token}`};
  const form = body instanceof FormData;
  if (body && !form) headers['Content-Type'] = 'application/json';
  const response = await fetch(API + path, {method, headers,
    body: body ? (form ? body : JSON.stringify(body)) : undefined});
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (!response.ok) {
    if (response.status === 401) { logout(); feedback('authMsg', 'Your session expired. Please log in again.'); }
    const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join('; ') : data.detail;
    const error = new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`);
    error.status = response.status; throw error;
  }
  return data;
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function renderMessages() {
  const box = $('messages');
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 120;
  const opened = new Set([...box.querySelectorAll('details[open]')].map((node) => node.dataset.id));
  box.replaceChildren();
  for (const message of [...messages.values()].sort((a, b) => a.id - b.id)) {
    const node = element('article', `message${message.is_bot ? ' bot' : ''}${message.status === 'error' ? ' failed' : ''}`);
    node.dataset.messageId = message.id;
    node.append(element('div', 'meta', `${message.username} · ${new Date(message.created_at).toLocaleString()}`));
    node.append(element('div', 'message-body', message.content));
    if (message.sources?.length) {
      const details = element('details', 'sources'); details.dataset.id = String(message.id);
      details.open = opened.has(String(message.id));
      details.append(element('summary', '', `Retrieved passages (${message.sources.length})`));
      for (const source of message.sources) {
        const passage = element('div', 'passage');
        passage.append(element('div', 'source-title', `[${source.label}] ${source.filename} · PDF page ${source.page}`));
        passage.append(element('p', '', source.text)); details.append(passage);
      }
      node.append(details);
    }
    if (message.status === 'error' && messages.has(message.reply_to)) {
      const retry = element('button', 'small secondary', 'Retry question');
      retry.onclick = () => send(messages.get(message.reply_to).content); node.append(retry);
    }
    box.append(node);
  }
  if (atBottom) box.scrollTop = box.scrollHeight;
}
function receive(message) {
  messages.set(message.id, message);
  if (message.is_bot && message.reply_to) { answered.add(message.reply_to); pending.delete(message.reply_to); }
  renderMessages(); pendingStatus();
}
async function loadMessages() {
  const data = await callAPI('/messages');
  for (const message of data.messages) {
    messages.set(message.id, message);
    if (message.reply_to) answered.add(message.reply_to);
  }
  pending.clear();
  for (const id of data.pending_replies || []) if (!answered.has(id)) pending.add(id);
  renderMessages(); pendingStatus();
}
function connect() {
  if (!token) return Promise.reject(new Error('Please log in.'));
  const currentEpoch = epoch;
  const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws = socket;
  return new Promise((resolve, reject) => {
    let ready = false;
    const timeout = setTimeout(() => { reject(new Error('Chat connection timed out.')); socket.close(); }, 15000);
    socket.onopen = () => socket.send(JSON.stringify({type: 'authenticate', token}));
    socket.onmessage = (event) => {
      if (currentEpoch !== epoch || ws !== socket) return;
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.type === 'ready') {
        ready = true; clearTimeout(timeout);
        feedback('connectionStatus', 'Connected'); $('connectionStatus').classList.add('connected'); resolve();
      } else if (data.type === 'message') receive(data.message);
      else if (data.type === 'bot_status') {
        if (data.status === 'error') {
          pending.delete(data.request_id); feedback('chatError', 'The assistant could not save its reply. Please resend your question.');
        } else if (!answered.has(data.request_id)) pending.add(data.request_id);
        pendingStatus();
      }
    };
    socket.onclose = (event) => {
      clearTimeout(timeout);
      if (!ready) reject(new Error('Chat connection failed. Please log in again.'));
      if (currentEpoch !== epoch || ws !== socket || !token) return;
      feedback('connectionStatus', 'Reconnecting'); $('connectionStatus').classList.remove('connected');
      if ([1008, 4401].includes(event.code)) { logout(); feedback('authMsg', 'Please log in again.'); return; }
      setTimeout(() => {
        if (currentEpoch === epoch && token) connect().then(loadMessages).catch((error) => feedback('chatError', error.message));
      }, 2000);
    };
  });
}
async function loadDocuments() {
  feedback('docsError', '');
  try {
    const knowledge = await callAPI('/knowledge');
    feedback('topicName', knowledge.topic);
    feedback('knowledgeStatus', knowledge.ready ? `${knowledge.indexed_chunks} indexed passages available.` : 'The knowledge base is unavailable.');
    uploadsAvailable = knowledge.uploads_available;
    let documents = knowledge.documents || [];
    if (uploadsAvailable) documents = (await callAPI('/documents')).documents;
    $('docList').replaceChildren();
    for (const document of documents) {
      const node = element('li', '', document.filename);
      const pages = document.pages ?? document.indexed_pages;
      node.append(element('small', '', `${pages} ${document.pages === undefined ? 'indexed ' : ''}pages · ${document.chunks} chunks · ${document.status || 'ready'}`));
      if (document.error) node.append(element('small', 'error', document.error));
      if (document.id && document.status === 'failed') {
        const retry = element('button', 'small secondary', 'Retry indexing');
        retry.onclick = async () => {
          retry.disabled = true; feedback('uploadMsg', `Retrying ${document.filename}...`);
          try {
            const result = await callAPI(`/documents/${document.id}/retry`, 'POST');
            feedback('uploadMsg', `${document.filename}: ${result.error || result.status}`);
          } catch (error) { feedback('uploadMsg', `Retry failed. ${error.message}`); }
          finally { await loadDocuments(); }
        };
        node.append(retry);
      }
      $('docList').append(node);
    }
    $('fileInput').disabled = !uploadsAvailable || uploadBusy;
    $('uploadBtn').disabled = !uploadsAvailable || uploadBusy || !$('fileInput').files.length;
    feedback('uploadAvailability', uploadsAvailable ? '' : 'Document uploads are not connected yet. You can ask questions about the existing documents.');
  } catch (error) { feedback('docsError', `Could not load documents. ${error.message}`); }
}
async function enterChat() {
  await connect();
  await loadMessages();
  $('auth').classList.add('hidden'); $('chat').classList.remove('hidden');
  feedback('currentUser', username); await loadDocuments();
}
async function authenticate(path) {
  feedback('authMsg', '');
  if (!$('authForm').reportValidity()) return;
  $('loginBtn').disabled = $('signupBtn').disabled = true;
  try {
    const data = await callAPI(path, 'POST', {username: $('username').value.trim(), password: $('password').value});
    token = data.token; username = data.username;
    localStorage.setItem('token', token); localStorage.setItem('username', username);
    await enterChat();
    $('password').value = '';
  } catch (error) { feedback('authMsg', error.message); }
  finally { $('loginBtn').disabled = $('signupBtn').disabled = false; }
}
async function send(value) {
  const text = (value ?? $('chatInput').value).trim();
  if (!text) return;
  $('sendBtn').disabled = true; feedback('chatError', '');
  try {
    const data = await callAPI('/messages', 'POST', {content: text});
    receive(data.message);
    if (data.bot_pending && !answered.has(data.message.id)) pending.add(data.message.id);
    pendingStatus(); $('chatInput').value = '';
  } catch (error) { feedback('chatError', `Message not sent. ${error.message}`); }
  finally { $('sendBtn').disabled = false; }
}
$('authForm').onsubmit = (event) => { event.preventDefault(); authenticate('/login'); };
$('signupBtn').onclick = () => authenticate('/signup');
$('logoutBtn').onclick = logout;
$('composer').onsubmit = (event) => { event.preventDefault(); send(); };
$('chatInput').onkeydown = (event) => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); } };
$('refreshDocs').onclick = loadDocuments;
$('fileInput').onchange = () => { $('uploadBtn').disabled = !uploadsAvailable || uploadBusy || !$('fileInput').files.length; };
$('uploadForm').onsubmit = async (event) => {
  event.preventDefault(); if (!uploadsAvailable || uploadBusy) return;
  const files = [...$('fileInput').files]; if (!files.length) return;
  if (files.some((file) => file.size > 25 * 1024 * 1024)) { feedback('uploadMsg', 'Each file must be 25 MB or smaller.'); return; }
  const form = new FormData(); for (const file of files) form.append('files', file);
  uploadBusy = true; $('uploadBtn').disabled = true; $('fileInput').disabled = true;
  feedback('uploadMsg', 'Processing documents...');
  try {
    const data = await callAPI('/documents', 'POST', form);
    feedback('uploadMsg', data.results.map((result) => {
      const duplicate = result.duplicate || result.result === 'duplicate';
      const state = result.status === 'processing' ? 'indexing in progress' :
        (duplicate ? 'already indexed' : `${result.chunks} chunks indexed`);
      return `${result.filename}: ${result.error || state}`;
    }).join('\n'));
    if (!data.results.some((result) => result.error || result.status === 'processing')) $('fileInput').value = '';
  } catch (error) { feedback('uploadMsg', `Upload failed. ${error.message} You can retry the selected files.`); }
  finally { uploadBusy = false; await loadDocuments(); }
};
if (token) enterChat().catch((error) => { logout(); feedback('authMsg', error.message); });
