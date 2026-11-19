"use strict";

const $ = id => document.getElementById(id);
const isTouch = matchMedia("(pointer: coarse)").matches;
const narrow = () => matchMedia("(max-width: 860px)").matches;

const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} },
};

const state = {
  chatId: store.get("jarvisChat"),
  chats: [],
  pendingImage: null,     // {b64, url, name}
  busy: false,
  think: false,
};

// ================= helpers =================

function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "#i-" + name);
  svg.appendChild(use);
  return svg;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

let toastTimer;
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 2200);
}

function confirmBox(title, text) {
  const d = $("confirm");
  $("confirmTitle").textContent = title;
  $("confirmText").textContent = text;
  d.returnValue = "";
  d.showModal();
  return new Promise(res => d.addEventListener("close", () => res(d.returnValue === "ok"), {once: true}));
}

class SignedOut extends Error {}

async function api(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {}),
  });
  if (r.status === 401) { showLogin("Your session ended. Please sign in again."); throw new SignedOut(); }
  return r.json();
}

// ================= theme =================

function applyTheme(choice) {
  if (choice === "light" || choice === "dark") document.documentElement.dataset.theme = choice;
  else delete document.documentElement.dataset.theme;
  store.set("jarvisTheme", choice === "system" ? null : choice);
  for (const b of document.querySelectorAll("[data-theme-set]")) {
    b.setAttribute("aria-checked", String(b.dataset.themeSet === choice));
  }
}
for (const b of document.querySelectorAll("[data-theme-set]")) b.onclick = () => applyTheme(b.dataset.themeSet);
applyTheme(store.get("jarvisTheme") || "system");

// ================= sign-in =================

function showLogin(message) {
  $("app").hidden = true;
  $("login").hidden = false;
  $("loginError").textContent = message || "";
  $("pw").value = "";
  setTimeout(() => $("pw").focus(), 50);
}

function showApp() {
  $("login").hidden = true;
  $("app").hidden = false;
  if (!narrow() && store.get("jarvisSide") === "collapsed") $("app").classList.add("side-collapsed");
  greet();
  refreshSidebar();
  if (state.chatId) openChat(state.chatId); else resetChatView();
  if (!isTouch) $("box").focus();
}

let lockTimer;
function lockLogin(seconds) {
  const btn = $("loginBtn");
  btn.disabled = true;
  $("pw").disabled = true;
  clearInterval(lockTimer);
  const end = Date.now() + seconds * 1000;
  const tick = () => {
    const left = Math.ceil((end - Date.now()) / 1000);
    if (left <= 0) {
      clearInterval(lockTimer);
      btn.disabled = false;
      $("pw").disabled = false;
      $("loginError").textContent = "You can try again now.";
      $("pw").focus();
      return;
    }
    $("loginError").textContent = `Too many wrong attempts. Try again in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  };
  tick();
  lockTimer = setInterval(tick, 1000);
}

$("loginForm").addEventListener("submit", async e => {
  e.preventDefault();
  const pw = $("pw").value;
  const field = $("pw").closest(".pw-field");
  const card = $("loginForm");
  if (!pw) { $("loginError").textContent = "Enter your password."; field.classList.add("error"); $("pw").focus(); return; }

  const btn = $("loginBtn");
  btn.disabled = true;
  btn.classList.add("loading");
  $("loginError").textContent = "";
  try {
    const r = await fetch("/login", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({password: pw, remember: $("remember").checked}),
    });
    const data = await r.json();
    btn.classList.remove("loading");
    if (r.ok) { field.classList.remove("error"); btn.disabled = false; showApp(); return; }

    $("loginError").textContent = data.error || "Could not sign in.";
    field.classList.add("error");
    card.classList.remove("shake"); void card.offsetWidth; card.classList.add("shake");
    if (r.status === 429 && data.retry) lockLogin(data.retry);
    else { btn.disabled = false; $("pw").select(); }
  } catch (err) {
    btn.classList.remove("loading");
    btn.disabled = false;
    $("loginError").textContent = "Could not reach Jarvis. Is the server running?";
  }
});

$("pw").addEventListener("input", () => $("pw").closest(".pw-field").classList.remove("error"));
for (const ev of ["keydown", "keyup"]) {
  $("pw").addEventListener(ev, e => {
    if (e.getModifierState) $("capsHint").hidden = !e.getModifierState("CapsLock");
  });
}
$("pwToggle").addEventListener("click", () => {
  const input = $("pw");
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  const t = $("pwToggle");
  t.replaceChildren(icon(show ? "eye-off" : "eye"));
  t.setAttribute("aria-label", show ? "Hide password" : "Show password");
  t.title = t.getAttribute("aria-label");
  input.focus();
});

$("logout").addEventListener("click", async () => {
  await fetch("/logout", {method: "POST"});
  closeSidebar();
  showLogin("You have signed out.");
});

// ================= sidebar =================

function openSidebar() {
  if (narrow()) $("app").classList.add("side-open");
  else { $("app").classList.remove("side-collapsed"); store.set("jarvisSide", null); }
}
function closeSidebar() {
  if (narrow()) $("app").classList.remove("side-open");
}
$("openSide").onclick = openSidebar;
$("closeSide").onclick = () => {
  if (narrow()) closeSidebar();
  else { $("app").classList.add("side-collapsed"); store.set("jarvisSide", "collapsed"); }
};
$("scrim").onclick = closeSidebar;

function sideItem(iconName, label, meta, active, onOpen, onDelete, deleteLabel) {
  const li = el("li", "side-item" + (active ? " active" : "") + (onOpen ? "" : " static"));
  li.title = label;
  li.append(icon(iconName), el("span", "label", label));
  if (meta) li.append(el("span", "meta", meta));
  if (onOpen) {
    li.tabIndex = 0;
    li.onclick = onOpen;
    li.onkeydown = e => { if (e.key === "Enter") onOpen(); };
  }
  const del = el("button", "icon-btn");
  del.append(icon("trash"));
  del.setAttribute("aria-label", deleteLabel);
  del.title = deleteLabel;
  del.onclick = e => { e.stopPropagation(); onDelete(); };
  li.append(del);
  return li;
}

function dateGroup(iso) {
  if (!iso) return "Older";
  const d = new Date(iso);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const days = Math.floor((today - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 864e5);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Previous 7 days";
  if (days < 30) return "Previous 30 days";
  return "Older";
}

function renderChats() {
  const q = $("search").value.trim().toLowerCase();
  const box = $("chatGroups");
  box.replaceChildren();
  const groups = new Map();
  for (const ch of state.chats) {
    if (q && !ch.title.toLowerCase().includes(q)) continue;
    const g = dateGroup(ch.updated);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(ch);
  }
  for (const [name, chats] of groups) {
    box.append(el("h2", "side-title", name));
    const ul = el("ul", "side-list");
    for (const ch of chats) {
      const item = sideItem("chat", ch.title, null, ch.id === state.chatId,
        () => { openChat(ch.id); closeSidebar(); },
        async () => {
          if (!await confirmBox("Delete chat?", `"${ch.title}" will be deleted for good.`)) return;
          await api("/chats/delete", {id: ch.id});
          if (ch.id === state.chatId) resetChatView();
          refreshSidebar();
          toast("Chat deleted");
        }, "Delete chat");
      item.firstChild.remove();            // chat rows look cleaner without an icon
      item.dataset.id = ch.id;
      ul.append(item);
    }
    box.append(ul);
  }
  if (!groups.size) {
    box.append(el("h2", "side-title", "Chats"));
    box.append(el("p", "side-empty", q ? "No chats match your search" : "Your chats will appear here"));
  }
}
$("search").addEventListener("input", renderChats);

async function refreshSidebar() {
  let c, d;
  try { [c, d] = await Promise.all([api("/chats"), api("/documents")]); }
  catch (e) { return; }
  state.chats = c.chats || [];
  renderChats();

  const dl = $("docList");
  dl.replaceChildren();
  for (const doc of d.documents || []) {
    dl.append(sideItem("doc", doc.name, doc.pages + " p", false, null,
      async () => {
        if (!await confirmBox("Delete document?", `Jarvis will forget "${doc.name}".`)) return;
        await api("/documents/delete", {id: doc.id});
        refreshSidebar();
        toast("Document deleted");
      }, "Delete document"));
  }
  if (!dl.children.length) dl.append(el("li", "side-empty", "Attach a PDF to add one"));
  updateTitle();
}

function updateTitle() {
  const ch = state.chats.find(c => c.id === state.chatId);
  $("chatTitle").textContent = ch ? ch.title : "";
  document.title = ch ? ch.title + " · Jarvis" : "Jarvis";
  for (const li of document.querySelectorAll("#chatGroups .side-item")) {
    li.classList.toggle("active", li.dataset.id === state.chatId);
  }
}

// ================= chat view =================

function greet() {
  const h = new Date().getHours();
  $("greeting").textContent = h < 5 ? "Good evening" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function setChat(id) {
  state.chatId = id;
  store.set("jarvisChat", id);
}

function showWelcome(show) { $("welcome").hidden = !show; }

function resetChatView() {
  setChat(null);
  $("log").replaceChildren();
  showWelcome(true);
  updateTitle();
}

const scroller = $("scroller");
const nearBottom = () => scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 120;
function scrollDown(smooth) { scroller.scrollTo({top: scroller.scrollHeight, behavior: smooth ? "smooth" : "auto"}); }
scroller.addEventListener("scroll", () => {
  $("toBottom").hidden = nearBottom();
  document.querySelector(".topbar").classList.toggle("scrolled", scroller.scrollTop > 4);
});
$("toBottom").onclick = () => scrollDown(true);

function jarvisRow() {
  const row = el("div", "msg jarvis");
  const av = el("div", "avatar");
  av.append(icon("logo"));
  const body = el("div", "body");
  row.append(av, body);
  return [row, body];
}

function addMessage(who, text, opts = {}) {
  showWelcome(false);
  const bubble = el("div", "bubble");
  if (opts.imageUrl) { const img = el("img"); img.src = opts.imageUrl; img.alt = "Attached image"; bubble.append(img); }
  let row;
  if (who === "you") {
    row = el("div", "msg you");
    if (text) bubble.append(document.createTextNode(text));
    row.append(bubble);
  } else {
    let body;
    [row, body] = jarvisRow();
    if (opts.kind) row.classList.add(opts.kind);
    body.append(bubble);
    if (opts.reveal && text) reveal(bubble, text); else if (text) bubble.textContent = text;
    if (text && !opts.kind) addActions(body, text);
  }
  if (opts.replace) opts.replace.replaceWith(row); else $("log").append(row);
  if (opts.replace || nearBottom() || who === "you") scrollDown(false);
  return row;
}

// show a new reply a few words at a time; finishes within about a second
function reveal(node, text) {
  const parts = text.split(/(\s+)/);
  const step = Math.max(1, Math.ceil(parts.length / 60));
  let i = 0;
  const follow = nearBottom();
  const tick = () => {
    i = Math.min(parts.length, i + step);
    node.textContent = parts.slice(0, i).join("");
    if (follow) scrollDown(false);
    if (i < parts.length) setTimeout(tick, 16);
  };
  tick();
}

function addActions(body, text) {
  const bar = el("div", "msg-actions");
  const copy = el("button", "icon-btn");
  copy.append(icon("copy"));
  copy.setAttribute("aria-label", "Copy reply");
  copy.title = "Copy";
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {              // the clipboard API needs https; fall back for http on the home network
      const ta = el("textarea"); ta.value = text; document.body.append(ta); ta.select();
      document.execCommand("copy"); ta.remove();
    }
    copy.replaceChildren(icon("check"));
    toast("Copied");
    setTimeout(() => copy.replaceChildren(icon("copy")), 1500);
  };
  bar.append(copy);
  body.append(bar);
}

function addThinking(label) {
  showWelcome(false);
  const [row, body] = jarvisRow();
  const t = el("div", "thinking");
  const dots = el("span", "dots");
  dots.append(el("span"), el("span"), el("span"));
  t.append(dots, el("span", "shimmer", label || "Thinking"));
  body.append(t);
  $("log").append(row);
  scrollDown(true);
  return row;
}

async function openChat(id) {
  let data;
  try { data = await api("/chats/get", {id}); } catch (e) { return; }
  if (!data.messages || !data.messages.length) { resetChatView(); return; }
  setChat(id);
  $("log").replaceChildren();
  showWelcome(false);
  for (const m of data.messages) addMessage(m.who, m.text);
  updateTitle();
  requestAnimationFrame(() => scrollDown(false));
}

function newChat() {
  resetChatView();
  closeSidebar();
  if (!isTouch) $("box").focus();
}
$("newChat").onclick = newChat;
$("newChatTop").onclick = newChat;
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" && !$("app").hidden) { e.preventDefault(); newChat(); }
});

// ================= composer =================

const box = $("box");

function autosize() {
  box.style.height = "auto";
  box.style.height = Math.min(box.scrollHeight, 240) + "px";
  $("send").disabled = state.busy || !box.value.trim();
}
box.addEventListener("input", autosize);
box.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing && !isTouch) {
    e.preventDefault();
    $("composer").requestSubmit();
  }
});

$("thinkBtn").onclick = () => {
  state.think = !state.think;
  $("thinkBtn").setAttribute("aria-pressed", String(state.think));
  toast(state.think ? "Think mode on: slower, more careful answers" : "Think mode off");
  box.focus();
};

for (const b of document.querySelectorAll(".suggest")) {
  b.onclick = () => {
    if (b.dataset.fill) {
      box.value = b.dataset.fill;
      autosize();
      box.focus();
      box.setSelectionRange(box.value.length, box.value.length);
    } else {
      box.value = b.dataset.text;
      autosize();
      $("composer").requestSubmit();
    }
  };
}

$("composer").addEventListener("submit", async e => {
  e.preventDefault();
  const text = box.value.trim();
  if (!text || state.busy) return;

  const image = state.pendingImage;
  clearAttachment();
  box.value = "";
  state.busy = true;
  autosize();

  addMessage("you", text, {imageUrl: image && image.url});
  const careful = state.think || /think (about|hard|carefully|deeply)/i.test(text);
  const wait = addThinking(careful ? "Thinking carefully" : image ? "Looking at the image" : "Thinking");
  try {
    const data = await api("/chat", {message: text, chat_id: state.chatId, think: state.think, images: image ? [image.b64] : []});
    const isNew = data.chat_id && data.chat_id !== state.chatId;
    if (data.chat_id) setChat(data.chat_id);
    if (data.reply) addMessage("jarvis", data.reply, {replace: wait, reveal: true});
    else addMessage("jarvis", data.error || "Something went wrong.", {replace: wait, kind: "error"});
    if (isNew) refreshSidebar(); else updateTitle();
  } catch (err) {
    if (err instanceof SignedOut) { wait.remove(); return; }
    addMessage("jarvis", "Could not reach Jarvis. Check that the server is running.", {replace: wait, kind: "error"});
  } finally {
    state.busy = false;
    autosize();
    if (!isTouch) box.focus();
  }
});

// ================= attachments =================

function imageToBase64(file) {      // shrink big photos so the model reads them faster
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, 1280 / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * scale);
      c.height = Math.round(img.height * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      resolve(c.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
}

function clearAttachment() {
  state.pendingImage = null;
  $("attachment").hidden = true;
}

async function uploadPdf(file) {
  const wait = addThinking(`Reading ${file.name}`);
  const form = new FormData();
  form.append("file", file);
  try {
    const r = await fetch("/upload", {method: "POST", body: form});
    if (r.status === 401) { wait.remove(); showLogin("Your session ended. Please sign in again."); return; }
    const data = await r.json();
    addMessage("jarvis", data.reply || data.error || "Upload failed.", {replace: wait, kind: data.reply ? "note" : "error"});
    refreshSidebar();
  } catch (e) {
    addMessage("jarvis", "Could not upload the file.", {replace: wait, kind: "error"});
  }
}

async function handleFile(file) {
  if (!file) return;
  if (file.type.startsWith("image/")) {
    try {
      const url = await imageToBase64(file);
      state.pendingImage = {url, b64: url.split(",")[1], name: file.name || "Pasted image"};
    } catch (e) { toast("Could not read that image"); return; }
    $("attachThumb").src = state.pendingImage.url;
    $("attachName").textContent = state.pendingImage.name;
    $("attachment").hidden = false;
    box.placeholder = "Ask about this image…";
    box.focus();
  } else if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
    uploadPdf(file);
  } else {
    toast("Only PDFs and images are supported");
  }
}

$("attach").onclick = () => $("file").click();
$("file").onchange = () => { handleFile($("file").files[0]); $("file").value = ""; };
$("attachRemove").onclick = () => { clearAttachment(); box.placeholder = "Ask Jarvis anything…"; };
box.addEventListener("paste", e => {
  for (const item of e.clipboardData.items) {
    if (item.type.startsWith("image/")) { e.preventDefault(); handleFile(item.getAsFile()); }
  }
});

let dragDepth = 0;
const main = document.querySelector(".main");
main.addEventListener("dragenter", e => { if ([...e.dataTransfer.types].includes("Files")) { dragDepth++; $("dropZone").hidden = false; } });
main.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("dropZone").hidden = true; } });
main.addEventListener("dragover", e => e.preventDefault());
main.addEventListener("drop", e => {
  e.preventDefault();
  dragDepth = 0;
  $("dropZone").hidden = true;
  handleFile(e.dataTransfer.files[0]);
});

// ================= start =================

fetch("/me").then(r => r.json()).then(d => d.signed_in ? showApp() : showLogin())
  .catch(() => showLogin("Could not reach Jarvis. Is the server running?"));
