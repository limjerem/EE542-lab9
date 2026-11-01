const $ = (id) => document.getElementById(id);
const authPanel = $("auth"), chatPanel = $("chat"), messagesDiv = $("messages");
const usernameInput = $("username"), passwordInput = $("password");
const authMsg = $("authMsg"), chatMsg = $("chatMsg"), connectionStatus = $("connectionStatus");
const signupBtn = $("signupBtn"), loginBtn = $("loginBtn"), logoutBtn = $("logoutBtn");
const chatInput = $("chatInput"), sendBtn = $("sendBtn");
const API = location.origin + "/api";
const messagesById = new Map();
let token = localStorage.getItem("token") || "";
let ws = null, reconnectTimer = null;

function showAuth() {
  authPanel.classList.remove("hidden");
  chatPanel.classList.add("hidden");
}

function showChat() {
  authPanel.classList.add("hidden");
  chatPanel.classList.remove("hidden");
}

function closeWS() {
  clearTimeout(reconnectTimer);
  const previous = ws;
  ws = null;
  if (previous) previous.close();
}

function logout() {
  token = "";
  localStorage.removeItem("token");
  closeWS();
  messagesDiv.replaceChildren();
  messagesById.clear();
  chatMsg.textContent = "";
  showAuth();
}

async function callAPI(path, method = "GET", body) {
  const headers = {"Content-Type": "application/json"};
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch(API + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item) => item.msg).join("; ") : data.detail;
    throw new Error(detail || "HTTP " + response.status);
  }
  return data;
}

function addMessage(message) {
  if (messagesById.has(message.id)) return;
  messagesById.set(message.id, message);
  const element = document.createElement("div");
  element.className = "message" + (message.is_bot ? " bot" : "");
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${message.username || "unknown"} • ${new Date(message.created_at).toLocaleString()}`;
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = message.content;
  element.append(meta, body);
  messagesDiv.appendChild(element);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function loadMessages() {
  const data = await callAPI("/messages");
  // Merge broadcasts received while history was loading, without duplicates.
  const merged = new Map(data.messages.map((message) => [message.id, message]));
  for (const message of messagesById.values()) merged.set(message.id, message);
  messagesDiv.replaceChildren();
  messagesById.clear();
  [...merged.values()].sort((a, b) => a.id - b.id).slice(-100).forEach(addMessage);
}

function connectWS() {
  closeWS();
  if (!token) return Promise.reject(new Error("Please log in"));
  connectionStatus.textContent = "Connecting…";
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);
  ws = socket;
  return new Promise((resolve, reject) => {
    let ready = false;
    const timeout = setTimeout(() => {
      reject(new Error("Chat connection timed out"));
      socket.close();
    }, 15000);
    socket.onopen = () => socket.send(JSON.stringify({type: "authenticate", token}));
    socket.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.type === "ready") {
        ready = true;
        clearTimeout(timeout);
        connectionStatus.textContent = "Connected";
        resolve();
      } else if (data.type === "message") {
        addMessage(data.message);
      }
    };
    socket.onclose = (event) => {
      clearTimeout(timeout);
      if (!ready) reject(new Error(event.code === 4401 ? "Please log in again" : "Chat connection failed"));
      if (ws !== socket) return;
      ws = null;
      connectionStatus.textContent = "Disconnected";
      if (event.code === 4401) {
        logout();
        authMsg.textContent = "Your login expired. Please log in again.";
      } else if (token) {
        reconnectTimer = setTimeout(() => {
          connectWS().then(loadMessages).catch(() => { if (token) connectionStatus.textContent = "Reconnecting…"; });
        }, 2000);
      }
    };
  });
}

async function authenticate(path) {
  authMsg.textContent = "";
  signupBtn.disabled = loginBtn.disabled = true;
  try {
    const result = await callAPI(path, "POST", {
      username: usernameInput.value.trim(), password: passwordInput.value
    });
    token = result.token;
    localStorage.setItem("token", token);
    await connectWS();
    await loadMessages();
    passwordInput.value = "";
    showChat();
  } catch (error) {
    logout();
    authMsg.textContent = error.message;
  } finally {
    signupBtn.disabled = loginBtn.disabled = false;
  }
}

signupBtn.onclick = () => authenticate("/signup");
loginBtn.onclick = () => authenticate("/login");
logoutBtn.onclick = logout;

sendBtn.onclick = async () => {
  const content = chatInput.value.trim();
  if (!content || sendBtn.disabled) return;
  sendBtn.disabled = true;
  chatInput.value = "";
  chatMsg.textContent = /[?？]/.test(content) ? "Waiting for the bot…" : "Sending…";
  try {
    await callAPI("/messages", "POST", {content});
    chatMsg.textContent = "";
  } catch (error) {
    if (!chatInput.value) chatInput.value = content;
    chatMsg.textContent = error.message;
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
};

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.isComposing) {
    event.preventDefault();
    sendBtn.click();
  }
});

if (token) {
  connectWS().then(loadMessages).then(showChat).catch(logout);
} else {
  showAuth();
}
