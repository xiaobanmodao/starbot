const state = {
  activeView: "chat",
  seenEventKeys: new Set(),
  chatBusy: false,
  configDraft: {},
  skillItems: [],
};

const els = {};

function $(id) {
  return document.getElementById(id);
}

function bindElements() {
  Object.assign(els, {
    navTabs: $("navTabs"),
    chatFeed: $("chatFeed"),
    eventLog: $("eventLog"),
    chatInput: $("chatInput"),
    btnChatSend: $("btnChatSend"),
    btnChatStop: $("btnChatStop"),
    btnChatReset: $("btnChatReset"),
    btnClearEventLog: $("btnClearEventLog"),
    usageInput: $("usageInput"),
    usageOutput: $("usageOutput"),
    usageCalls: $("usageCalls"),
    sessionBusyDot: $("sessionBusyDot"),
    sessionBusyText: $("sessionBusyText"),
    modelLabel: $("modelLabel"),
    btnQuickStatus: $("btnQuickStatus"),
    btnQuickDoctor: $("btnQuickDoctor"),
    btnOpenScreenshot: $("btnOpenScreenshot"),
    btnCloseImageModal: $("btnCloseImageModal"),
    imageModal: $("imageModal"),
    screenshotImg: $("screenshotImg"),
    commandInput: $("commandInput"),
    commandResult: $("commandResult"),
    btnRunCommand: $("btnRunCommand"),
    btnLoadHelp: $("btnLoadHelp"),
    btnCopyCommandResult: $("btnCopyCommandResult"),
    doctorRuntime: $("doctorRuntime"),
    doctorConfigChecks: $("doctorConfigChecks"),
    doctorFeatures: $("doctorFeatures"),
    doctorChecksTable: $("doctorChecksTable"),
    btnRefreshDoctor: $("btnRefreshDoctor"),
    configForm: $("configForm"),
    btnReloadConfig: $("btnReloadConfig"),
    btnSaveConfig: $("btnSaveConfig"),
    skillsTable: $("skillsTable"),
    btnReloadSkills: $("btnReloadSkills"),
    btnRefreshSkills: $("btnRefreshSkills"),
    skillInstallSource: $("skillInstallSource"),
    btnSkillInstall: $("btnSkillInstall"),
    skillNameAction: $("skillNameAction"),
    btnSkillInfo: $("btnSkillInfo"),
    btnSkillUpdate: $("btnSkillUpdate"),
    btnSkillRemove: $("btnSkillRemove"),
    skillActionResult: $("skillActionResult"),
    memoryCategory: $("memoryCategory"),
    btnMemoryList: $("btnMemoryList"),
    btnMemoryStats: $("btnMemoryStats"),
    btnMemoryRefresh: $("btnMemoryRefresh"),
    memoryListTable: $("memoryListTable"),
    memorySearchQuery: $("memorySearchQuery"),
    btnMemorySearch: $("btnMemorySearch"),
    memorySearchTable: $("memorySearchTable"),
    memoryDeleteId: $("memoryDeleteId"),
    btnMemoryDelete: $("btnMemoryDelete"),
    memoryActionResult: $("memoryActionResult"),
    btnRefreshTasks: $("btnRefreshTasks"),
    tasksTable: $("tasksTable"),
    rollbackCount: $("rollbackCount"),
    btnRollback: $("btnRollback"),
    taskActionResult: $("taskActionResult"),
    toastHost: $("toastHost"),
  });
}

async function apiGet(path) {
  const r = await fetch(path, { cache: "no-store" });
  return r.json();
}

async function apiPost(path, body = {}) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}

function showToast(text, level = "ok") {
  const div = document.createElement("div");
  div.className = `toast ${level}`;
  div.textContent = text;
  els.toastHost.appendChild(div);
  setTimeout(() => {
    div.remove();
  }, 2600);
}

function appendEventLog(text) {
  const now = new Date();
  const ts = now.toLocaleTimeString();
  els.eventLog.textContent += `[${ts}] ${text}\n`;
  els.eventLog.scrollTop = els.eventLog.scrollHeight;
}

function appendChat(role, text) {
  if (!text) return;
  const box = document.createElement("div");
  box.className = `chat-msg ${role}`;
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = role === "user" ? "You" : role === "assistant" ? "Starbot" : "System";
  const content = document.createElement("div");
  content.className = "content";
  content.textContent = text;
  box.append(roleEl, content);
  els.chatFeed.appendChild(box);
  els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
}

function setBusy(busy) {
  state.chatBusy = !!busy;
  els.sessionBusyDot.classList.toggle("busy", !!busy);
  els.sessionBusyDot.classList.toggle("idle", !busy);
  els.sessionBusyText.textContent = busy ? "Busy" : "Idle";
  els.btnChatSend.disabled = !!busy;
}

function updateUsage(usage) {
  const u = usage || {};
  els.usageInput.textContent = String(u.input ?? 0);
  els.usageOutput.textContent = String(u.output ?? 0);
  els.usageCalls.textContent = String(u.calls ?? 0);
}

function prettyJSON(obj) {
  return JSON.stringify(obj, null, 2);
}

function setCommandResult(obj) {
  els.commandResult.textContent = prettyJSON(obj);
}

function setSkillActionResult(obj) {
  els.skillActionResult.textContent = prettyJSON(obj);
}

function setMemoryActionResult(obj) {
  els.memoryActionResult.textContent = prettyJSON(obj);
}

function setTaskActionResult(obj) {
  els.taskActionResult.textContent = prettyJSON(obj);
}

function renderListBlock(container, rows) {
  container.innerHTML = "";
  (rows || []).forEach((row) => {
    const el = document.createElement("div");
    el.className = "kv-row";
    const k = document.createElement("div");
    k.className = "k";
    k.textContent = row.key;
    const v = document.createElement("div");
    v.className = "v";
    if (row.badge) {
      const pill = document.createElement("span");
      pill.className = `pill ${row.badge}`;
      pill.textContent = row.value;
      v.appendChild(pill);
    } else {
      v.textContent = row.value;
    }
    el.append(k, v);
    container.appendChild(el);
  });
}

function renderTable(container, columns, rows) {
  const table = document.createElement("table");
  table.className = "data-table";
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c.label;
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");

  if (!rows || rows.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns.length;
    td.textContent = "No data";
    tr.appendChild(td);
    tbody.appendChild(tr);
  } else {
    rows.forEach((row) => {
      const tr = document.createElement("tr");
      columns.forEach((c) => {
        const td = document.createElement("td");
        const val = typeof c.render === "function" ? c.render(row) : row[c.key];
        if (val instanceof Node) td.appendChild(val);
        else td.textContent = val == null ? "" : String(val);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }
  table.appendChild(tbody);
  container.innerHTML = "";
  container.appendChild(table);
}

function switchView(name) {
  state.activeView = name;
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((v) => {
    v.classList.toggle("active", v.id === `view-${name}`);
  });
}

async function loadStatus() {
  const res = await apiGet("/api/status");
  if (!res.ok) return;
  const d = res.data || {};
  setBusy(!!d.session_busy);
  updateUsage(d.usage || {});
  if (d.model) els.modelLabel.textContent = `Model: ${d.model}`;
}

async function pollEvents() {
  try {
    const res = await apiGet("/api/chat/events?limit=200");
    if (!res.ok) return;
    const data = res.data || {};
    if (typeof data.busy === "boolean") setBusy(data.busy);
    if (data.usage) updateUsage(data.usage);

    for (const ev of data.events || []) {
      const key = `${ev.type}:${ev.time}:${ev.text || ev.message || ev.reason || ""}`;
      if (state.seenEventKeys.has(key)) continue;
      state.seenEventKeys.add(key);
      if (state.seenEventKeys.size > 5000) {
        state.seenEventKeys = new Set([...state.seenEventKeys].slice(-3000));
      }

      switch (ev.type) {
        case "user":
          appendChat("user", ev.text || "");
          break;
        case "assistant":
          appendChat("assistant", ev.text || "");
          break;
        case "status":
          appendEventLog(ev.text || "");
          break;
        case "tool_call":
          appendEventLog(`Tool call: ${(ev.names || []).join(", ")}`);
          break;
        case "tool_result":
          appendEventLog(`${ev.done ? "done" : "step"}: ${ev.summary || ""}`);
          break;
        case "error":
          appendEventLog(`Error: ${ev.message || ""}`);
          showToast(ev.message || "Error", "error");
          break;
        case "cancelled":
          appendEventLog("Task cancelled.");
          break;
        default:
          break;
      }
    }
  } catch (e) {
    appendEventLog(`Poll error: ${e}`);
  }
}

async function sendChat() {
  const text = els.chatInput.value.trim();
  if (!text) return;
  const res = await apiPost("/api/chat/send", { text });
  if (!res.ok) {
    showToast(res.message || "Send failed", "error");
    return;
  }
  els.chatInput.value = "";
  appendEventLog("Message queued.");
}

async function runCommand() {
  const text = els.commandInput.value.trim();
  if (!text) return;
  const res = await apiPost("/api/command", { text });
  setCommandResult(res);
  showToast(res.ok ? "Command executed" : (res.message || "Command failed"), res.ok ? "ok" : "error");

  // Refresh relevant panels after command execution.
  if (text.startsWith("/skill")) loadSkills();
  if (text.startsWith("/memory")) {
    loadMemoryList();
    loadMemoryStatsIntoResult();
  }
  if (text.startsWith("/config")) loadConfig();
  if (text.startsWith("/doctor")) loadDoctor();
  if (text.startsWith("/tasks") || text.startsWith("/rollback")) loadTasks();
  if (text.startsWith("/model")) loadStatus();
}

function createActionCell(actions) {
  const wrap = document.createElement("div");
  wrap.className = "table-actions";
  actions.forEach((a) => {
    const b = document.createElement("button");
    b.className = "tiny-btn";
    b.textContent = a.label;
    b.addEventListener("click", a.onClick);
    wrap.appendChild(b);
  });
  return wrap;
}

async function loadDoctor() {
  const res = await apiGet("/api/doctor");
  if (!res.ok) {
    showToast(res.message || "Doctor failed", "error");
    return;
  }
  const d = res.data || {};
  const runtime = d.runtime || {};
  renderListBlock(els.doctorRuntime, [
    { key: "Model", value: runtime.model || "-" },
    { key: "Session Active", value: String(!!runtime.session_active), badge: runtime.session_active ? "ok" : "warn" },
    { key: "Session Busy", value: String(!!runtime.session_busy), badge: runtime.session_busy ? "warn" : "ok" },
    { key: "Skills Loaded", value: String(runtime.skills_count ?? 0) },
    { key: "Memory DB", value: runtime.memory_db || "-" },
    { key: "Memory DB Exists", value: String(!!runtime.memory_db_exists), badge: runtime.memory_db_exists ? "ok" : "bad" },
  ]);

  const cfgOk = d.config_ok || {};
  renderListBlock(els.doctorConfigChecks, Object.keys(cfgOk).map((k) => ({
    key: k,
    value: cfgOk[k] ? "Configured" : "Missing",
    badge: cfgOk[k] ? "ok" : "bad",
  })));

  const features = d.features || {};
  renderListBlock(els.doctorFeatures, Object.keys(features).map((k) => ({
    key: k,
    value: features[k] ? "Available" : "Unavailable",
    badge: features[k] ? "ok" : "warn",
  })));

  renderTable(els.doctorChecksTable, [
    { key: "label", label: "Component" },
    { key: "kind", label: "Kind" },
    { key: "ok", label: "Status", render: (r) => r.ok ? "OK" : "Missing" },
    { key: "hint", label: "Install Hint" },
  ], d.checks || []);
}

function buildConfigField(key, value) {
  const field = document.createElement("div");
  field.className = "field";
  const name = document.createElement("div");
  name.className = "field-name";
  name.textContent = key;
  const input = document.createElement("input");
  input.type = key.includes("KEY") || key.includes("TOKEN") ? "password" : "text";
  input.dataset.key = key;
  input.value = value ?? "";
  input.placeholder = key;
  input.addEventListener("input", () => {
    state.configDraft[key] = input.value;
  });
  const help = document.createElement("div");
  help.className = "field-help";
  help.textContent = (key === "LLM_MODEL")
    ? "Runtime model selection (also saved to state)"
    : "Saved to .env";
  field.append(name, input, help);
  return field;
}

async function loadConfig() {
  const res = await apiGet("/api/config");
  if (!res.ok) {
    showToast(res.message || "Config load failed", "error");
    return;
  }
  const cfg = (res.data || {}).config || {};
  state.configDraft = { ...cfg };
  els.configForm.innerHTML = "";
  Object.keys(cfg).forEach((k) => {
    els.configForm.appendChild(buildConfigField(k, cfg[k]));
  });
}

async function saveConfig() {
  const values = {};
  els.configForm.querySelectorAll("input[data-key]").forEach((input) => {
    values[input.dataset.key] = input.value;
  });
  const res = await apiPost("/api/config/bulk", { values });
  if (!res.ok) {
    showToast(res.message || "Save failed", "error");
    return;
  }
  showToast(res.message || "Saved", "ok");
  loadConfig();
  loadStatus();
}

async function loadSkills() {
  const res = await apiGet("/api/skills");
  if (!res.ok) {
    showToast(res.message || "Skills load failed", "error");
    return;
  }
  const items = (res.data || {}).items || [];
  state.skillItems = items;
  renderTable(els.skillsTable, [
    { key: "name", label: "Name" },
    { key: "version", label: "Version" },
    { key: "kind", label: "Kind" },
    { key: "managed", label: "Managed", render: (r) => (r.managed ? "yes" : "no") },
    { key: "tools", label: "Tools", render: (r) => (r.tools || []).join(", ") },
    {
      key: "actions",
      label: "Actions",
      render: (r) => createActionCell([
        { label: "Info", onClick: () => skillInfoByName(r.name) },
        { label: "Update", onClick: () => skillUpdateByName(r.name) },
        { label: "Remove", onClick: () => skillRemoveByName(r.name) },
      ]),
    },
  ], items);
}

async function skillInfoByName(name) {
  els.skillNameAction.value = name;
  const res = await apiPost("/api/skill/info", { name });
  setSkillActionResult(res);
}

async function skillUpdateByName(name) {
  els.skillNameAction.value = name;
  const res = await apiPost("/api/skill/update", { name });
  setSkillActionResult(res);
  showToast(res.message || (res.ok ? "Updated" : "Update failed"), res.ok ? "ok" : "error");
  loadSkills();
}

async function skillRemoveByName(name) {
  els.skillNameAction.value = name;
  const res = await apiPost("/api/skill/remove", { name });
  setSkillActionResult(res);
  showToast(res.message || (res.ok ? "Removed" : "Remove failed"), res.ok ? "ok" : "error");
  loadSkills();
}

async function loadMemoryList() {
  const category = els.memoryCategory.value.trim();
  const res = await apiGet(`/api/memory/list?category=${encodeURIComponent(category)}&limit=30`);
  if (!res.ok) return;
  const items = (res.data || {}).items || [];
  renderTable(els.memoryListTable, [
    { key: "id", label: "ID" },
    { key: "category", label: "Category" },
    { key: "importance", label: "Imp" },
    { key: "content", label: "Content", render: (r) => (r.content || "").slice(0, 160) },
  ], items);
}

async function loadMemoryStatsIntoResult() {
  const res = await apiGet("/api/memory/stats");
  setMemoryActionResult(res);
}

async function memorySearch() {
  const query = els.memorySearchQuery.value.trim();
  const res = await apiPost("/api/memory/search", { query, limit: 12 });
  setMemoryActionResult(res);
  const items = (res.data || {}).items || [];
  renderTable(els.memorySearchTable, [
    { key: "id", label: "ID" },
    { key: "category", label: "Category" },
    { key: "score", label: "Score", render: (r) => r.score ?? "" },
    { key: "content", label: "Content", render: (r) => (r.content || "").slice(0, 180) },
  ], items);
}

async function memoryDelete() {
  const id = Number(els.memoryDeleteId.value || 0);
  const res = await apiPost("/api/memory/delete", { id });
  setMemoryActionResult(res);
  showToast(res.message || (res.ok ? "Deleted" : "Delete failed"), res.ok ? "ok" : "error");
  loadMemoryList();
}

async function loadTasks() {
  const res = await apiGet("/api/tasks");
  if (!res.ok) {
    setTaskActionResult(res);
    return;
  }
  const items = (res.data || {}).items || [];
  renderTable(els.tasksTable, [
    { key: "id", label: "ID" },
    { key: "name", label: "Name" },
    { key: "status", label: "Status" },
    { key: "steps", label: "Steps" },
    { key: "result", label: "Result", render: (r) => (r.result || "").slice(0, 120) },
  ], items);
  setTaskActionResult(res);
}

async function doRollback() {
  const count = Number(els.rollbackCount.value || 1);
  const res = await apiPost("/api/rollback", { count });
  setTaskActionResult(res);
  showToast(res.ok ? "Rollback executed" : (res.message || "Rollback failed"), res.ok ? "ok" : "error");
}

async function openScreenshotModal() {
  const res = await apiPost("/api/screenshot", {});
  if (!res.ok) {
    showToast(res.message || "Screenshot failed", "error");
    return;
  }
  const b64 = res.data?.jpeg_base64;
  if (!b64) {
    showToast("No screenshot image data", "error");
    return;
  }
  els.screenshotImg.src = `data:image/jpeg;base64,${b64}`;
  els.imageModal.classList.remove("hidden");
}

function closeScreenshotModal() {
  els.imageModal.classList.add("hidden");
  els.screenshotImg.removeAttribute("src");
}

function wireNav() {
  els.navTabs.addEventListener("click", (e) => {
    const btn = e.target.closest(".nav-tab");
    if (!btn) return;
    switchView(btn.dataset.view);
  });
}

function wireActions() {
  els.btnChatSend.addEventListener("click", sendChat);
  els.btnChatStop.addEventListener("click", async () => {
    const res = await apiPost("/api/chat/stop", {});
    showToast(res.message || "Stop requested", res.ok ? "warn" : "error");
  });
  els.btnChatReset.addEventListener("click", async () => {
    const res = await apiPost("/api/chat/reset", {});
    showToast(res.message || "Session reset", res.ok ? "ok" : "error");
    if (res.ok) appendChat("system", "Session reset.");
  });
  els.btnClearEventLog.addEventListener("click", () => {
    els.eventLog.textContent = "";
  });
  els.chatInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      sendChat();
    }
  });

  els.btnRunCommand.addEventListener("click", runCommand);
  els.btnLoadHelp.addEventListener("click", async () => {
    els.commandInput.value = "/help";
    await runCommand();
  });
  els.btnCopyCommandResult.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(els.commandResult.textContent || "");
      showToast("Copied", "ok");
    } catch {
      showToast("Copy failed", "warn");
    }
  });

  els.btnQuickStatus.addEventListener("click", loadStatus);
  els.btnQuickDoctor.addEventListener("click", loadDoctor);
  els.btnOpenScreenshot.addEventListener("click", openScreenshotModal);
  els.btnCloseImageModal.addEventListener("click", closeScreenshotModal);
  els.imageModal.addEventListener("click", (e) => {
    if (e.target === els.imageModal) closeScreenshotModal();
  });

  els.btnRefreshDoctor.addEventListener("click", loadDoctor);
  els.btnReloadConfig.addEventListener("click", loadConfig);
  els.btnSaveConfig.addEventListener("click", saveConfig);

  els.btnRefreshSkills.addEventListener("click", loadSkills);
  els.btnReloadSkills.addEventListener("click", async () => {
    const res = await apiPost("/api/skill/reload", {});
    setSkillActionResult(res);
    showToast(res.message || "Reloaded", res.ok ? "ok" : "error");
    loadSkills();
  });
  els.btnSkillInstall.addEventListener("click", async () => {
    const source = els.skillInstallSource.value.trim();
    const res = await apiPost("/api/skill/install", { source });
    setSkillActionResult(res);
    showToast(res.message || (res.ok ? "Installed" : "Install failed"), res.ok ? "ok" : "error");
    loadSkills();
  });
  els.btnSkillInfo.addEventListener("click", () => skillInfoByName(els.skillNameAction.value.trim()));
  els.btnSkillUpdate.addEventListener("click", () => skillUpdateByName(els.skillNameAction.value.trim()));
  els.btnSkillRemove.addEventListener("click", () => skillRemoveByName(els.skillNameAction.value.trim()));

  els.btnMemoryList.addEventListener("click", loadMemoryList);
  els.btnMemoryRefresh.addEventListener("click", loadMemoryList);
  els.btnMemoryStats.addEventListener("click", loadMemoryStatsIntoResult);
  els.btnMemorySearch.addEventListener("click", memorySearch);
  els.btnMemoryDelete.addEventListener("click", memoryDelete);

  els.btnRefreshTasks.addEventListener("click", loadTasks);
  els.btnRollback.addEventListener("click", doRollback);
}

async function bootstrapPanels() {
  appendChat("system", "Local Web UI connected. Discord control flow is still available in parallel.");
  await Promise.allSettled([
    loadStatus(),
    loadDoctor(),
    loadConfig(),
    loadSkills(),
    loadMemoryList(),
    loadTasks(),
  ]);
}

function startPolling() {
  setInterval(pollEvents, 700);
  setInterval(loadStatus, 5000);
}

function init() {
  bindElements();
  wireNav();
  wireActions();
  switchView("chat");
  bootstrapPanels();
  startPolling();
}

document.addEventListener("DOMContentLoaded", init);

