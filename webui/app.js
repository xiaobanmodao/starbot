const I18N = {
  zh: {
    "nav.chat": "主页",
    "nav.doctor": "诊断",
    "nav.config": "配置 & 设置",
    "nav.skills": "技能",
    "nav.tasks": "任务",
    "top.refreshStatus": "刷新状态",
    "top.doctor": "诊断",
    "top.screenshot": "截图",
    "chat.title": "对话",
    "chat.newSession": "新会话",
    "chat.stop": "停止",
    "chat.send": "发送",
    "chat.placeholder": "输入任务或问题。支持普通对话和复杂任务...",
    "chat.hint": "Ctrl/Cmd + Enter 发送",
    "chat.usage": "会话用量",
    "chat.hint2": "最终回答显示在左侧聊天区。",
    "chat.hint3": "工具调用和过程日志显示在诊断页面。",
    "cmd.title": "命令控制台",
    "cmd.loadHelp": "加载帮助",
    "cmd.run": "执行命令",
    "cmd.result": "命令结果",
    "cmd.copy": "复制 JSON",
    "cmd.desc": "执行与 Discord 文本命令一致的命令（如 /doctor、/skill list、/memory stats、/config LLM_MODEL xxx）。",
    "doctor.runtime": "运行时",
    "doctor.config": "配置检查",
    "doctor.features": "功能可用性",
    "doctor.refresh": "刷新",
    "doctor.components": "推荐组件",
    "doctor.runLog": "运行日志",
    "doctor.copyLog": "复制日志",
    "doctor.clearLog": "清空",
    "config.title": "配置",
    "config.reload": "重新加载",
    "config.save": "保存选定字段",
    "config.desc": "可在此修改核心配置。敏感值显示为脱敏状态；如需更新，请直接输入新值覆盖。",
    "config.note": "保存会写入 .env（LLM_MODEL 同时写入运行态 state）。Discord 功能保持不变。",
    "skills.title": "技能",
    "skills.reload": "重新加载",
    "skills.refresh": "刷新",
    "skills.actions": "技能操作",
    "skills.install": "安装来源（URL / 本地路径）",
    "memory.title": "记忆浏览器",
    "memory.stats": "统计",
    "memory.refresh": "刷新",
    "memory.search": "记忆搜索 / 删除",
    "memory.search_btn": "搜索",
    "memory.delete": "删除",
    "tasks.title": "后台任务",
    "tasks.refresh": "刷新",
    "tasks.rollback": "回滚最近的文件操作",
    "footer.discord": "Discord 模式仍然可用。",
    "footer.hint": "此 UI 是额外的本地客户端。",
    "pref.title": "界面偏好",
    "pref.language": "语言 / Language",
    "pref.theme": "配色主题",
    "pref.dark": "暗色",
    "pref.light": "亮色",
    "model.loading": "加载中...",
    "model.label": "模型",
    "model.switchOk": "已切换模型",
    "model.switchFail": "切换失败",
    "model.loadFail": "模型列表加载失败",
    // 动态渲染文字
    "status.idle": "空闲",
    "status.busy": "处理中",
    "role.you": "你",
    "role.starbot": "Starbot",
    "role.system": "系统",
    "log.connected": "本地客户端已连接。Discord 模式仍然可用。",
    "log.toolCall": "工具调用",
    "log.pollError": "轮询错误",
    "log.queued": "消息已发送。",
    "log.cancelled": "任务已取消。",
    "log.step": "步骤",
    "log.done": "完成",
    "session.reset": "会话已重置。",
    "table.noData": "暂无数据",
    "table.colComponent": "组件",
    "table.colKind": "类型",
    "table.colStatus": "状态",
    "table.colInstallHint": "安装提示",
    "table.colID": "ID",
    "table.colCategory": "分类",
    "table.colImportance": "重要性",
    "table.colContent": "内容",
    "table.colScore": "得分",
    "table.colName": "名称",
    "table.colSteps": "步骤",
    "table.colResult": "结果",
    "table.colVersion": "版本",
    "table.colManaged": "托管",
    "table.colTools": "工具",
    "table.colActions": "操作",
    "table.actionInfo": "详情",
    "table.actionUpdate": "更新",
    "table.actionRemove": "移除",
    "doctor.sessionActive": "会话激活",
    "doctor.sessionBusy": "会话处理中",
    "doctor.skillsLoaded": "已加载技能",
    "doctor.memoryDb": "记忆数据库",
    "doctor.memoryDbExists": "记忆库文件",
    "doctor.model": "模型",
    "doctor.configured": "已配置",
    "doctor.missing": "未配置",
    "doctor.available": "可用",
    "doctor.unavailable": "不可用",
    "doctor.ok": "正常",
    "doctor.notok": "缺失",
    "config.runtimeHint": "运行时模型（同步写入运行状态）",
    "config.savedToEnv": "保存到 .env",
    // toast / 动态提示
    "toast.error": "错误",
    "toast.sendFail": "发送失败",
    "toast.cmdOk": "命令已执行",
    "toast.cmdFail": "命令失败",
    "toast.doctorFail": "诊断失败",
    "toast.configLoadFail": "配置加载失败",
    "toast.saveFail": "保存失败",
    "toast.saved": "已保存",
    "toast.skillsLoadFail": "技能加载失败",
    "toast.updated": "已更新",
    "toast.updateFail": "更新失败",
    "toast.removed": "已移除",
    "toast.removeFail": "移除失败",
    "toast.deleted": "已删除",
    "toast.deleteFail": "删除失败",
    "toast.rollbackOk": "回滚已执行",
    "toast.rollbackFail": "回滚失败",
    "toast.screenshotFail": "截图失败",
    "toast.noScreenshotData": "无截图数据",
    "toast.stopRequested": "已请求停止",
    "toast.copied": "已复制",
    "toast.copyFail": "复制失败",
    "toast.reloaded": "已重新加载",
    "toast.installed": "已安装",
    "toast.installFail": "安装失败",
    // HTML 静态文字
    "brand.name": "Starbot",
    "brand.tagline": "控制中心",
    "stat.input": "输入",
    "stat.output": "输出",
    "stat.calls": "调用",
    "skills.installBtn": "安装",
    "skills.skillName": "技能名称",
    "skills.info": "详情",
    "skills.update": "更新",
    "skills.remove": "移除",
    "memory.category": "分类（留空 = 全部）",
    "memory.list": "列表",
    "memory.searchLabel": "搜索关键词",
    "memory.searchPlaceholder": "关键词",
    "memory.deleteLabel": "删除记忆 ID",
    "tasks.rollbackBtn": "回滚",
    "screenshot.title": "截图",
    "screenshot.close": "关闭",
    "misc.yes": "是",
    "misc.no": "否",
  },
  en: {
    "nav.chat": "Home",
    "nav.doctor": "Doctor",
    "nav.config": "Config & Settings",
    "nav.skills": "Skills",
    "nav.tasks": "Tasks",
    "top.refreshStatus": "Refresh Status",
    "top.doctor": "Doctor",
    "top.screenshot": "Screenshot",
    "chat.title": "Conversation",
    "chat.newSession": "New Session",
    "chat.stop": "Stop",
    "chat.send": "Send",
    "chat.placeholder": "Enter a task or question...",
    "chat.hint": "Ctrl/Cmd + Enter to send",
    "chat.usage": "Session Usage",
    "chat.hint2": "Final answers appear in the left chat area.",
    "chat.hint3": "Tool calls and process logs appear in the Doctor page.",
    "cmd.title": "Command Console",
    "cmd.loadHelp": "Load Help",
    "cmd.run": "Run Command",
    "cmd.result": "Command Result",
    "cmd.copy": "Copy JSON",
    "cmd.desc": "Execute commands like Discord text commands (e.g. /doctor, /skill list, /memory stats, /config LLM_MODEL xxx).",
    "doctor.runtime": "Runtime",
    "doctor.config": "Config Checks",
    "doctor.features": "Feature Availability",
    "doctor.refresh": "Refresh",
    "doctor.components": "Recommended Components",
    "doctor.runLog": "Run Log",
    "doctor.copyLog": "Copy Log",
    "doctor.clearLog": "Clear",
    "config.title": "Configuration",
    "config.reload": "Reload",
    "config.save": "Save Selected Fields",
    "config.desc": "Edit core configuration here. Sensitive values are masked; enter a new value to overwrite.",
    "config.note": "Saves to .env (LLM_MODEL also updates runtime state). Discord flow stays unchanged.",
    "skills.title": "Skills",
    "skills.reload": "Reload",
    "skills.refresh": "Refresh",
    "skills.actions": "Skill Actions",
    "skills.install": "Install source (URL / local path)",
    "memory.title": "Memory Browser",
    "memory.stats": "Stats",
    "memory.refresh": "Refresh",
    "memory.search": "Memory Search / Delete",
    "memory.search_btn": "Search",
    "memory.delete": "Delete",
    "tasks.title": "Background Tasks",
    "tasks.refresh": "Refresh",
    "tasks.rollback": "Rollback recent file operations",
    "footer.discord": "Discord mode remains available.",
    "footer.hint": "This UI is an additional local client.",
    "pref.title": "UI Preferences",
    "pref.language": "Language",
    "pref.theme": "Color Theme",
    "pref.dark": "Dark",
    "pref.light": "Light",
    "model.loading": "Loading...",
    "model.label": "Model",
    "model.switchOk": "Model switched",
    "model.switchFail": "Switch failed",
    "model.loadFail": "Failed to load model list",
    // dynamic text
    "status.idle": "Idle",
    "status.busy": "Busy",
    "role.you": "You",
    "role.starbot": "Starbot",
    "role.system": "System",
    "log.connected": "Local Web UI connected. Discord mode remains available.",
    "log.toolCall": "Tool call",
    "log.pollError": "Poll error",
    "log.queued": "Message sent.",
    "log.cancelled": "Task cancelled.",
    "log.step": "step",
    "log.done": "done",
    "session.reset": "Session reset.",
    "table.noData": "No data",
    "table.colComponent": "Component",
    "table.colKind": "Kind",
    "table.colStatus": "Status",
    "table.colInstallHint": "Install Hint",
    "table.colID": "ID",
    "table.colCategory": "Category",
    "table.colImportance": "Imp",
    "table.colContent": "Content",
    "table.colScore": "Score",
    "table.colName": "Name",
    "table.colSteps": "Steps",
    "table.colResult": "Result",
    "table.colVersion": "Version",
    "table.colManaged": "Managed",
    "table.colTools": "Tools",
    "table.colActions": "Actions",
    "table.actionInfo": "Info",
    "table.actionUpdate": "Update",
    "table.actionRemove": "Remove",
    "doctor.sessionActive": "Session Active",
    "doctor.sessionBusy": "Session Busy",
    "doctor.skillsLoaded": "Skills Loaded",
    "doctor.memoryDb": "Memory DB",
    "doctor.memoryDbExists": "Memory DB Exists",
    "doctor.model": "Model",
    "doctor.configured": "Configured",
    "doctor.missing": "Missing",
    "doctor.available": "Available",
    "doctor.unavailable": "Unavailable",
    "doctor.ok": "OK",
    "doctor.notok": "Missing",
    "config.runtimeHint": "Runtime model selection (also saved to state)",
    "config.savedToEnv": "Saved to .env",
    // toast / dynamic hints
    "toast.error": "Error",
    "toast.sendFail": "Send failed",
    "toast.cmdOk": "Command executed",
    "toast.cmdFail": "Command failed",
    "toast.doctorFail": "Doctor failed",
    "toast.configLoadFail": "Config load failed",
    "toast.saveFail": "Save failed",
    "toast.saved": "Saved",
    "toast.skillsLoadFail": "Skills load failed",
    "toast.updated": "Updated",
    "toast.updateFail": "Update failed",
    "toast.removed": "Removed",
    "toast.removeFail": "Remove failed",
    "toast.deleted": "Deleted",
    "toast.deleteFail": "Delete failed",
    "toast.rollbackOk": "Rollback executed",
    "toast.rollbackFail": "Rollback failed",
    "toast.screenshotFail": "Screenshot failed",
    "toast.noScreenshotData": "No screenshot image data",
    "toast.stopRequested": "Stop requested",
    "toast.copied": "Copied",
    "toast.copyFail": "Copy failed",
    "toast.reloaded": "Reloaded",
    "toast.installed": "Installed",
    "toast.installFail": "Install failed",
    // HTML static text
    "brand.name": "Starbot",
    "brand.tagline": "Control Center",
    "stat.input": "Input",
    "stat.output": "Output",
    "stat.calls": "Calls",
    "skills.installBtn": "Install",
    "skills.skillName": "Skill name",
    "skills.info": "Info",
    "skills.update": "Update",
    "skills.remove": "Remove",
    "memory.category": "Category (blank = all)",
    "memory.list": "List",
    "memory.searchLabel": "Search query",
    "memory.searchPlaceholder": "Keywords",
    "memory.deleteLabel": "Delete memory ID",
    "tasks.rollbackBtn": "Rollback",
    "screenshot.title": "Screenshot",
    "screenshot.close": "Close",
    "misc.yes": "yes",
    "misc.no": "no",
  },
};

const state = {
  activeView: "chat",
  seenEventKeys: new Set(),
  chatBusy: false,
  configDraft: {},
  skillItems: [],
  currentLang: "zh",
  currentModel: "",
};

const els = {};

function $(id) {
  return document.getElementById(id);
}

function t(key) {
  const dict = I18N[state.currentLang] || I18N.zh;
  return dict[key] || key;
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
    btnAttach: $("btnAttach"),
    fileInput: $("fileInput"),
    composerAttachments: $("composerAttachments"),
    btnClearEventLog: $("btnClearEventLog"),
    btnCopyEventLog: $("btnCopyEventLog"),
    usageInput: $("usageInput"),
    usageOutput: $("usageOutput"),
    usageCalls: $("usageCalls"),
    sessionBusyDot: $("sessionBusyDot"),
    sessionBusyText: $("sessionBusyText"),
    modelLabel: $("modelLabel"),
    modelPicker: $("modelPicker"),
    btnModelPicker: $("btnModelPicker"),
    modelDropdown: $("modelDropdown"),
    modelDropdownLoading: $("modelDropdownLoading"),
    modelDropdownList: $("modelDropdownList"),
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
    div.classList.add("exiting");
    div.addEventListener("animationend", () => div.remove(), { once: true });
    setTimeout(() => div.remove(), 300);
  }, 2400);
}

function applyLang(lang) {
  state.currentLang = lang;
  const dict = I18N[lang] || I18N.zh;
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    const text = dict[key];
    if (!text) return;
    if (el.tagName === "TEXTAREA" || (el.tagName === "INPUT" && el.placeholder !== undefined)) {
      el.placeholder = text;
    } else {
      el.textContent = text;
    }
  });
  document.querySelectorAll("#langPicker .seg-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.lang === lang));
  localStorage.setItem("sb_lang", lang);
  // Refresh dynamic text already rendered
  if (els.sessionBusyText) {
    els.sessionBusyText.textContent = state.chatBusy ? t("status.busy") : t("status.idle");
  }
  if (els.modelLabel && state.currentModel) {
    els.modelLabel.textContent = `${t("model.label")}: ${state.currentModel}`;
  }
  // Re-render all dynamic panels so table headers / labels update
  if (typeof loadDoctor === "function") loadDoctor();
  if (typeof loadSkills === "function") loadSkills();
  if (typeof loadMemoryList === "function") loadMemoryList();
  if (typeof loadTasks === "function") loadTasks();
  if (typeof loadConfig === "function") loadConfig();
  document.title = `${t("brand.name")} ${t("brand.tagline")}`;
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelectorAll("#themePicker .seg-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.themeVal === theme));
  localStorage.setItem("sb_theme", theme);
}

function appendEventLog(text) {
  const now = new Date();
  const ts = now.toLocaleTimeString();
  els.eventLog.textContent += `[${ts}] ${text}\n`;
  els.eventLog.scrollTop = els.eventLog.scrollHeight;
}

function appendChat(role, text) {
  if (!text) return;
  // Remove thinking bubble before appending real content
  const tb = document.getElementById("thinkingBubble");
  if (tb) tb.remove();
  const box = document.createElement("div");
  box.className = `chat-msg ${role}`;
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = role === "user" ? t("role.you") : role === "assistant" ? t("role.starbot") : t("role.system");
  const content = document.createElement("div");
  content.className = "content";
  content.textContent = text;
  box.append(roleEl, content);
  els.chatFeed.appendChild(box);
  els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
}

function showThinkingBubble(toolNames) {
  let existing = document.getElementById("thinkingBubble");
  if (existing) {
    // Update tool label on existing bubble
    if (toolNames) {
      const content = existing.querySelector(".thinking-content");
      let label = existing.querySelector(".thinking-label");
      if (!label && content) {
        label = document.createElement("span");
        label.className = "thinking-label";
        content.appendChild(label);
      }
      if (label) label.textContent = toolNames;
    }
    els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
    return;
  }
  const box = document.createElement("div");
  box.id = "thinkingBubble";
  box.className = "chat-msg assistant thinking";
  const roleEl = document.createElement("div");
  roleEl.className = "role";
  roleEl.textContent = t("role.starbot");
  const content = document.createElement("div");
  content.className = "content thinking-content";
  const spinnerEl = document.createElement("span");
  spinnerEl.className = "spinner";
  content.appendChild(spinnerEl);
  if (toolNames) {
    const label = document.createElement("span");
    label.className = "thinking-label";
    label.textContent = toolNames;
    content.appendChild(label);
  }
  box.append(roleEl, content);
  els.chatFeed.appendChild(box);
  els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
}

function removeThinkingBubble() {
  const existing = document.getElementById("thinkingBubble");
  if (existing) existing.remove();
}

function getOrCreateStreamBubble() {
  let el = document.getElementById("streamBubble");
  if (!el) {
    removeThinkingBubble();
    el = document.createElement("div");
    el.id = "streamBubble";
    el.className = "chat-msg assistant";
    const roleEl = document.createElement("div");
    roleEl.className = "role";
    roleEl.textContent = t("role.starbot");
    const content = document.createElement("div");
    content.className = "content";
    el.append(roleEl, content);
    els.chatFeed.appendChild(el);
  }
  return el;
}

function setBusy(busy) {
  state.chatBusy = !!busy;
  els.sessionBusyDot.classList.toggle("busy", !!busy);
  els.sessionBusyDot.classList.toggle("idle", !busy);
  els.sessionBusyText.textContent = busy ? t("status.busy") : t("status.idle");
  els.btnChatSend.disabled = !!busy;
  if (!busy) {
    removeThinkingBubble();
  }
}

function updateUsage(usage) {
  const u = usage || {};
  if (els.usageInput) els.usageInput.textContent = String(u.input ?? 0);
  if (els.usageOutput) els.usageOutput.textContent = String(u.output ?? 0);
  if (els.usageCalls) els.usageCalls.textContent = String(u.calls ?? 0);
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
  if (els.memoryActionResult) els.memoryActionResult.textContent = prettyJSON(obj);
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
    td.textContent = t("table.noData");
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
    const isTarget = v.id === `view-${name}`;
    if (isTarget && !v.classList.contains("active")) {
      v.classList.add("active");
      // Re-trigger entrance animation
      v.style.animation = "none";
      v.offsetHeight; // force reflow
      v.style.animation = "";
    } else if (!isTarget) {
      v.classList.remove("active");
    }
  });
}

async function loadStatus() {
  const res = await apiGet("/api/status");
  if (!res.ok) return;
  const d = res.data || {};
  setBusy(!!d.session_busy);
  updateUsage(d.usage || {});
  if (d.model) {
    state.currentModel = d.model;
    els.modelLabel.textContent = `${t("model.label")}: ${d.model}`;
  }
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
          showThinkingBubble();
          break;
        case "assistant":
          appendChat("assistant", ev.text || "");
          break;
        case "stream_start": {
          removeThinkingBubble();
          getOrCreateStreamBubble();
          break;
        }
        case "stream_delta": {
          const bubble = getOrCreateStreamBubble();
          const contentEl = bubble.querySelector(".content");
          if (contentEl) contentEl.textContent += (ev.text || "");
          els.chatFeed.scrollTop = els.chatFeed.scrollHeight;
          break;
        }
        case "stream_end": {
          const sb = document.getElementById("streamBubble");
          if (sb) {
            const ct = (sb.querySelector(".content")?.textContent || "").trim();
            if (!ct) { sb.remove(); } else { sb.removeAttribute("id"); }
          }
          break;
        }
        case "stream_clear": {
          // LLM switched from text to tool calls — keep reasoning text if non-empty
          const sc = document.getElementById("streamBubble");
          if (sc) {
            const ct = (sc.querySelector(".content")?.textContent || "").trim();
            if (!ct) { sc.remove(); } else { sc.removeAttribute("id"); }
          }
          showThinkingBubble();
          break;
        }
        case "status":
          appendEventLog(ev.text || "");
          break;
        case "tool_call": {
          const names = (ev.names || []).join(", ");
          showThinkingBubble(`${t("log.toolCall")}: ${names}`);
          appendEventLog(`${t("log.toolCall")}: ${names}`);
          break;
        }
        case "tool_result":
          appendEventLog(`${ev.done ? t("log.done") : t("log.step")}: ${ev.summary || ""}`);
          if (!ev.done) {
            showThinkingBubble();
          }
          break;
        case "done":
          removeThinkingBubble();
          setBusy(false);
          break;
        case "error":
          appendEventLog(`${t("toast.error")}: ${ev.message || ""}`);
          showToast(ev.message || t("toast.error"), "error");
          break;
        case "cancelled":
          appendEventLog(t("log.cancelled"));
          break;
        default:
          break;
      }
    }
  } catch (e) {
    appendEventLog(`${t("log.pollError")}: ${e}`);
  }
}

// ── File attachments ──
const pendingFiles = [];

function renderAttachmentChips() {
  els.composerAttachments.innerHTML = "";
  pendingFiles.forEach((f, i) => {
    const chip = document.createElement("span");
    chip.className = "attach-chip";
    chip.innerHTML = `<span class="chip-name">${f.name}</span><button class="chip-remove" data-idx="${i}">&times;</button>`;
    els.composerAttachments.appendChild(chip);
  });
  els.composerAttachments.querySelectorAll(".chip-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      pendingFiles.splice(Number(btn.dataset.idx), 1);
      renderAttachmentChips();
    });
  });
}

function handleFileSelect(fileList) {
  for (const file of fileList) {
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = reader.result.split(",")[1] || "";
      pendingFiles.push({ name: file.name, type: file.type || "application/octet-stream", data_b64: b64 });
      renderAttachmentChips();
    };
    reader.readAsDataURL(file);
  }
}

async function sendChat() {
  const text = els.chatInput.value.trim();
  if (!text && pendingFiles.length === 0) return;
  const body = { text };
  if (pendingFiles.length > 0) {
    body.attachments = pendingFiles.slice();
  }
  const res = await apiPost("/api/chat/send", body);
  if (!res.ok) {
    showToast(res.message || t("toast.sendFail"), "error");
    return;
  }
  els.chatInput.value = "";
  els.chatInput.style.height = "auto";
  pendingFiles.length = 0;
  renderAttachmentChips();
  appendEventLog(t("log.queued"));
}

async function runCommand() {
  const text = els.commandInput.value.trim();
  if (!text) return;
  const res = await apiPost("/api/command", { text });
  setCommandResult(res);
  showToast(res.ok ? t("toast.cmdOk") : (res.message || t("toast.cmdFail")), res.ok ? "ok" : "error");

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
    showToast(res.message || t("toast.doctorFail"), "error");
    return;
  }
  const d = res.data || {};
  const runtime = d.runtime || {};
  renderListBlock(els.doctorRuntime, [
    { key: t("doctor.model"), value: runtime.model || "-" },
    { key: t("doctor.sessionActive"), value: String(!!runtime.session_active), badge: runtime.session_active ? "ok" : "warn" },
    { key: t("doctor.sessionBusy"), value: String(!!runtime.session_busy), badge: runtime.session_busy ? "warn" : "ok" },
    { key: t("doctor.skillsLoaded"), value: String(runtime.skills_count ?? 0) },
    { key: t("doctor.memoryDb"), value: runtime.memory_db || "-" },
    { key: t("doctor.memoryDbExists"), value: String(!!runtime.memory_db_exists), badge: runtime.memory_db_exists ? "ok" : "bad" },
  ]);

  const cfgOk = d.config_ok || {};
  renderListBlock(els.doctorConfigChecks, Object.keys(cfgOk).map((k) => ({
    key: k,
    value: cfgOk[k] ? t("doctor.configured") : t("doctor.missing"),
    badge: cfgOk[k] ? "ok" : "bad",
  })));

  const features = d.features || {};
  renderListBlock(els.doctorFeatures, Object.keys(features).map((k) => ({
    key: k,
    value: features[k] ? t("doctor.available") : t("doctor.unavailable"),
    badge: features[k] ? "ok" : "warn",
  })));

  renderTable(els.doctorChecksTable, [
    { key: "label", label: t("table.colComponent") },
    { key: "kind", label: t("table.colKind") },
    { key: "ok", label: t("table.colStatus"), render: (r) => r.ok ? t("doctor.ok") : t("doctor.notok") },
    { key: "hint", label: t("table.colInstallHint") },
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
    ? t("config.runtimeHint")
    : t("config.savedToEnv");
  field.append(name, input, help);
  return field;
}

async function loadConfig() {
  const res = await apiGet("/api/config");
  if (!res.ok) {
    showToast(res.message || t("toast.configLoadFail"), "error");
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
    showToast(res.message || t("toast.saveFail"), "error");
    return;
  }
  showToast(res.message || t("toast.saved"), "ok");
  loadConfig();
  loadStatus();
}

async function loadSkills() {
  const res = await apiGet("/api/skills");
  if (!res.ok) {
    showToast(res.message || t("toast.skillsLoadFail"), "error");
    return;
  }
  const items = (res.data || {}).items || [];
  state.skillItems = items;
  renderTable(els.skillsTable, [
    { key: "name", label: t("table.colName") },
    { key: "version", label: t("table.colVersion") },
    { key: "kind", label: t("table.colKind") },
    { key: "managed", label: t("table.colManaged"), render: (r) => (r.managed ? t("misc.yes") : t("misc.no")) },
    { key: "tools", label: t("table.colTools"), render: (r) => (r.tools || []).join(", ") },
    {
      key: "actions",
      label: t("table.colActions"),
      render: (r) => createActionCell([
        { label: t("table.actionInfo"), onClick: () => skillInfoByName(r.name) },
        { label: t("table.actionUpdate"), onClick: () => skillUpdateByName(r.name) },
        { label: t("table.actionRemove"), onClick: () => skillRemoveByName(r.name) },
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
  showToast(res.message || (res.ok ? t("toast.updated") : t("toast.updateFail")), res.ok ? "ok" : "error");
  loadSkills();
}

async function skillRemoveByName(name) {
  els.skillNameAction.value = name;
  const res = await apiPost("/api/skill/remove", { name });
  setSkillActionResult(res);
  showToast(res.message || (res.ok ? t("toast.removed") : t("toast.removeFail")), res.ok ? "ok" : "error");
  loadSkills();
}

async function loadMemoryList() {
  if (!els.memoryCategory || !els.memoryListTable) return;
  const category = els.memoryCategory.value.trim();
  const res = await apiGet(`/api/memory/list?category=${encodeURIComponent(category)}&limit=30`);
  if (!res.ok) return;
  const items = (res.data || {}).items || [];
  renderTable(els.memoryListTable, [
    { key: "id", label: t("table.colID") },
    { key: "category", label: t("table.colCategory") },
    { key: "importance", label: t("table.colImportance") },
    { key: "content", label: t("table.colContent"), render: (r) => (r.content || "").slice(0, 160) },
  ], items);
}

async function loadMemoryStatsIntoResult() {
  const res = await apiGet("/api/memory/stats");
  setMemoryActionResult(res);
}

async function memorySearch() {
  if (!els.memorySearchQuery || !els.memorySearchTable) return;
  const query = els.memorySearchQuery.value.trim();
  const res = await apiPost("/api/memory/search", { query, limit: 12 });
  setMemoryActionResult(res);
  const items = (res.data || {}).items || [];
  renderTable(els.memorySearchTable, [
    { key: "id", label: t("table.colID") },
    { key: "category", label: t("table.colCategory") },
    { key: "score", label: t("table.colScore"), render: (r) => r.score ?? "" },
    { key: "content", label: t("table.colContent"), render: (r) => (r.content || "").slice(0, 180) },
  ], items);
}

async function memoryDelete() {
  if (!els.memoryDeleteId) return;
  const id = Number(els.memoryDeleteId.value || 0);
  const res = await apiPost("/api/memory/delete", { id });
  setMemoryActionResult(res);
  showToast(res.message || (res.ok ? t("toast.deleted") : t("toast.deleteFail")), res.ok ? "ok" : "error");
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
    { key: "id", label: t("table.colID") },
    { key: "name", label: t("table.colName") },
    { key: "status", label: t("table.colStatus") },
    { key: "steps", label: t("table.colSteps") },
    { key: "result", label: t("table.colResult"), render: (r) => (r.result || "").slice(0, 120) },
  ], items);
  setTaskActionResult(res);
}

async function doRollback() {
  const count = Number(els.rollbackCount.value || 1);
  const res = await apiPost("/api/rollback", { count });
  setTaskActionResult(res);
  showToast(res.ok ? t("toast.rollbackOk") : (res.message || t("toast.rollbackFail")), res.ok ? "ok" : "error");
}

async function openScreenshotModal() {
  const res = await apiPost("/api/screenshot", {});
  if (!res.ok) {
    showToast(res.message || t("toast.screenshotFail"), "error");
    return;
  }
  const b64 = res.data?.jpeg_base64;
  if (!b64) {
    showToast(t("toast.noScreenshotData"), "error");
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
    showToast(res.message || t("toast.stopRequested"), res.ok ? "warn" : "error");
  });
  els.btnChatReset.addEventListener("click", async () => {
    const res = await apiPost("/api/chat/reset", {});
    showToast(res.message || t("session.reset"), res.ok ? "ok" : "error");
    if (res.ok) appendChat("system", t("session.reset"));
  });
  els.btnClearEventLog.addEventListener("click", () => {
    els.eventLog.textContent = "";
  });
  els.btnCopyEventLog.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(els.eventLog.textContent || "");
      showToast(t("toast.copied"), "ok");
    } catch {
      showToast(t("toast.copyFail"), "warn");
    }
  });
  els.chatInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      sendChat();
    }
  });

  // Textarea auto-resize
  els.chatInput.addEventListener("input", () => {
    els.chatInput.style.height = "auto";
    els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 160) + "px";
  });

  // File attach
  els.btnAttach.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", () => {
    if (els.fileInput.files.length) handleFileSelect(els.fileInput.files);
    els.fileInput.value = "";
  });

  els.btnRunCommand.addEventListener("click", runCommand);
  els.btnLoadHelp.addEventListener("click", async () => {
    els.commandInput.value = "/help";
    await runCommand();
  });
  els.btnCopyCommandResult.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(els.commandResult.textContent || "");
      showToast(t("toast.copied"), "ok");
    } catch {
      showToast(t("toast.copyFail"), "warn");
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
    showToast(res.message || t("toast.reloaded"), res.ok ? "ok" : "error");
    loadSkills();
  });
  els.btnSkillInstall.addEventListener("click", async () => {
    const source = els.skillInstallSource.value.trim();
    const res = await apiPost("/api/skill/install", { source });
    setSkillActionResult(res);
    showToast(res.message || (res.ok ? t("toast.installed") : t("toast.installFail")), res.ok ? "ok" : "error");
    loadSkills();
  });
  els.btnSkillInfo.addEventListener("click", () => skillInfoByName(els.skillNameAction.value.trim()));
  els.btnSkillUpdate.addEventListener("click", () => skillUpdateByName(els.skillNameAction.value.trim()));
  els.btnSkillRemove.addEventListener("click", () => skillRemoveByName(els.skillNameAction.value.trim()));

  els.btnMemoryList?.addEventListener("click", loadMemoryList);
  els.btnMemoryRefresh?.addEventListener("click", loadMemoryList);
  els.btnMemoryStats?.addEventListener("click", loadMemoryStatsIntoResult);
  els.btnMemorySearch?.addEventListener("click", memorySearch);
  els.btnMemoryDelete?.addEventListener("click", memoryDelete);

  els.btnRefreshTasks.addEventListener("click", loadTasks);
  els.btnRollback.addEventListener("click", doRollback);

  document.querySelectorAll("#langPicker .seg-btn").forEach(b =>
    b.addEventListener("click", () => applyLang(b.dataset.lang)));
  document.querySelectorAll("#themePicker .seg-btn").forEach(b =>
    b.addEventListener("click", () => applyTheme(b.dataset.themeVal)));

  // 模型选择器
  els.btnModelPicker.addEventListener("click", async (e) => {
    e.stopPropagation();
    const isOpen = els.modelPicker.classList.contains("open");
    if (isOpen) {
      closeModelDropdown();
    } else {
      els.modelPicker.classList.add("open");
      els.modelDropdown.classList.remove("hidden");
      els.modelDropdownLoading.style.display = "block";
      els.modelDropdownList.innerHTML = "";
      const res = await apiGet("/api/model/list");
      els.modelDropdownLoading.style.display = "none";
      if (!res.ok) {
        els.modelDropdownLoading.style.display = "block";
        els.modelDropdownLoading.textContent = t("model.loadFail");
        return;
      }
      const models = (res.data || {}).models || [];
      const current = (res.data || {}).current || state.currentModel;
      models.forEach(m => {
        const btn = document.createElement("button");
        btn.className = "model-item" + (m === current ? " active" : "");
        btn.textContent = m;
        btn.addEventListener("click", async () => {
          closeModelDropdown();
          const r = await apiPost("/api/model/set", { name: m });
          showToast(r.ok ? `${t("model.switchOk")}: ${m}` : (r.message || t("model.switchFail")), r.ok ? "ok" : "error");
          if (r.ok) {
            state.currentModel = m;
            els.modelLabel.textContent = `${t("model.label")}: ${m}`;
          }
        });
        els.modelDropdownList.appendChild(btn);
      });
    }
  });

  document.addEventListener("click", (e) => {
    if (!els.modelPicker.contains(e.target)) closeModelDropdown();
  });
}

function closeModelDropdown() {
  els.modelPicker.classList.remove("open");
  els.modelDropdown.classList.add("hidden");
}

async function bootstrapPanels() {
  appendChat("system", t("log.connected"));
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
  applyTheme(localStorage.getItem("sb_theme") || "dark");
  applyLang(localStorage.getItem("sb_lang") || "en");
  bindElements();
  wireNav();
  wireActions();
  wireTitlebar();
  switchView("chat");
  bootstrapPanels();
  startPolling();
}

function wireTitlebar() {
  const btnMin = $("btnWinMinimize");
  const btnMax = $("btnWinMaximize");
  const btnClose = $("btnWinClose");

  // --- Electron mode ---
  if (window.electronAPI) {
    if (btnMin) btnMin.addEventListener("click", () => window.electronAPI.minimize());
    if (btnMax) btnMax.addEventListener("click", () => window.electronAPI.toggleMaximize());
    if (btnClose) btnClose.addEventListener("click", () => window.electronAPI.close());
    // Electron natively supports frameless window resize; hide JS resize handles
    document.querySelectorAll(".resize-handle").forEach(el => el.style.display = "none");
    return;
  }

  // --- pywebview mode (legacy) ---
  function onPywebviewReady() {
    const api = window.pywebview && window.pywebview.api;
    if (!api) {
      document.body.classList.add("browser-mode");
      return;
    }
    if (btnMin) btnMin.addEventListener("click", () => api.win_minimize());
    if (btnMax) btnMax.addEventListener("click", () => api.win_toggle_maximize());
    if (btnClose) btnClose.addEventListener("click", () => api.win_close());

    document.querySelectorAll(".resize-handle").forEach(el => {
      el.addEventListener("mousedown", e => {
        e.preventDefault();
        e.stopPropagation();
        const edge = parseInt(el.dataset.edge, 10);
        if (edge && api.win_start_resize) {
          api.win_start_resize(edge);
        }
      });
    });
  }

  if (window.pywebview) {
    onPywebviewReady();
  } else {
    window.addEventListener("pywebviewready", onPywebviewReady);
    setTimeout(() => {
      if (!window.pywebview) {
        document.body.classList.add("browser-mode");
      }
    }, 1500);
  }
}

document.addEventListener("DOMContentLoaded", init);

