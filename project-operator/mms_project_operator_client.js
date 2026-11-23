(() => {
  "use strict";

  const pairingToken = window.__MMS_PROJECT_OPERATOR_PAIRING_TOKEN;
  try { delete window.__MMS_PROJECT_OPERATOR_PAIRING_TOKEN; } catch (_) {}
  if (typeof pairingToken !== "string" || pairingToken.length < 40) return;

  let sessionToken = null;
  let pairingConsumed = false;
  let polling = false;
  let stopped = false;
  let panel;
  let statusNode;
  let connectButton;

  const allowedOperations = new Set([
    "snapshot",
    "search",
    "inspectResource",
    "inspectProjectObject",
    "analyzeCompatibility",
    "planMigration"
  ]);

  function setStatus(message, connected = false) {
    if (statusNode) statusNode.textContent = message;
    if (connectButton) {
      connectButton.textContent = connected ? "断开 AI 连接" : "连接 AI 操作员";
      connectButton.setAttribute("aria-pressed", String(connected));
    }
    if (panel) panel.dataset.connected = String(connected);
  }

  function createPanel() {
    if (document.getElementById("mms-project-operator-panel")) return;
    panel = document.createElement("section");
    panel.id = "mms-project-operator-panel";
    panel.style.cssText = [
      "position:fixed", "right:16px", "bottom:16px", "z-index:2147483000",
      "display:flex", "align-items:center", "gap:10px", "max-width:min(440px,calc(100vw - 32px))",
      "padding:10px 12px", "border:1px solid #8a806c", "border-radius:8px",
      "background:#211f25", "color:#f1eadc", "box-shadow:0 8px 28px #0008",
      "font:12px/1.4 system-ui,sans-serif"
    ].join(";");
    const text = document.createElement("span");
    text.textContent = "AI 项目操作员：尚未连接";
    text.style.cssText = "min-width:0;overflow-wrap:anywhere";
    statusNode = text;
    connectButton = document.createElement("button");
    connectButton.type = "button";
    connectButton.textContent = "连接 AI 操作员";
    connectButton.style.cssText = [
      "flex:none", "border:1px solid #c7b58b", "border-radius:5px",
      "padding:7px 10px", "background:#4b4936", "color:#fff4d9",
      "font:inherit", "cursor:pointer"
    ].join(";");
    connectButton.addEventListener("click", () => {
      if (sessionToken) disconnect();
      else if (pairingConsumed) window.location.reload();
      else connect();
    });
    panel.append(text, connectButton);
    document.body.append(panel);
  }

  async function post(path, body, authenticated = false) {
    const headers = { "Content-Type": "application/json" };
    if (authenticated) {
      if (!sessionToken) throw new Error("PROJECT_BRIDGE_NOT_CONNECTED");
      headers["X-MMS-Session"] = sessionToken;
    }
    const response = await fetch(path, {
      method: "POST",
      headers,
      body: JSON.stringify(body || {}),
      cache: "no-store",
      credentials: "same-origin",
      redirect: "error"
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok !== true) {
      throw new Error(typeof payload.error === "string" ? payload.error : "PROJECT_BRIDGE_HTTP_ERROR");
    }
    return payload;
  }

  async function waitForApi() {
    const deadline = Date.now() + 15000;
    while (!window.MMSProjectOperator && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    if (!window.MMSProjectOperator) throw new Error("PROJECT_OPERATOR_API_NOT_READY");
  }

  async function connect() {
    if (sessionToken || polling) return;
    setStatus("正在建立本地只读连接…");
    try {
      await waitForApi();
      const paired = await post("/bridge/pair", { token: pairingToken });
      sessionToken = paired.session_token;
      pairingConsumed = true;
      if (typeof sessionToken !== "string" || sessionToken.length < 40) {
        sessionToken = null;
        throw new Error("PROJECT_BRIDGE_SESSION_INVALID");
      }
      setStatus("已连接本地编辑器；当前仅开放只读操作", true);
      void pollLoop();
    } catch (error) {
      setStatus("连接失败：" + String(error.message || error));
    }
  }

  async function disconnect() {
    stopped = true;
    const token = sessionToken;
    sessionToken = null;
    polling = false;
    if (token) {
      try {
        await fetch("/bridge/disconnect", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-MMS-Session": token },
          body: "{}",
          cache: "no-store",
          credentials: "same-origin",
          keepalive: true,
          redirect: "error"
        });
      } catch (_) {}
    }
    stopped = false;
    setStatus("AI 操作员已断开；重新连接请刷新页面");
    if (connectButton) connectButton.textContent = "刷新页面重新连接";
  }

  async function execute(request) {
    if (!request || typeof request !== "object" || typeof request.id !== "string" ||
        !allowedOperations.has(request.operation) || !request.arguments ||
        typeof request.arguments !== "object" || Array.isArray(request.arguments)) {
      throw new Error("PROJECT_BRIDGE_REQUEST_INVALID");
    }
    const api = window.MMSProjectOperator;
    const operation = request.operation;
    const args = request.arguments;
    if (operation === "snapshot") return await api.snapshot();
    if (operation === "search") return await api.search(args);
    if (operation === "inspectResource") return await api.inspectResource(args);
    if (operation === "inspectProjectObject") return await api.inspectProjectObject(args);
    if (operation === "analyzeCompatibility") return await api.analyzeCompatibility();
    if (operation === "planMigration") return await api.planMigration(args);
    throw new Error("PROJECT_BRIDGE_OPERATION_NOT_ALLOWED");
  }

  async function pollLoop() {
    if (polling || !sessionToken) return;
    polling = true;
    stopped = false;
    while (sessionToken && !stopped) {
      try {
        const response = await post("/bridge/poll", { wait_ms: 10000 }, true);
        if (!response.request) continue;
        let result = null;
        let error = null;
        try {
          result = await execute(response.request);
        } catch (caught) {
          error = String(caught && caught.message ? caught.message : caught).slice(0, 500);
        }
        await post("/bridge/result", {
          request_id: response.request.id,
          result,
          error
        }, true);
      } catch (caught) {
        setStatus("连接中断：" + String(caught.message || caught));
        sessionToken = null;
        break;
      }
    }
    polling = false;
    if (!sessionToken) setStatus("AI 操作员已断开");
  }

  function boot() {
    createPanel();
    setStatus("AI 项目操作员：尚未连接");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  window.addEventListener("pagehide", () => {
    stopped = true;
    const token = sessionToken;
    sessionToken = null;
    if (token) {
      try {
        fetch("/bridge/disconnect", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-MMS-Session": token },
          body: "{}",
          cache: "no-store",
          credentials: "same-origin",
          keepalive: true
        });
      } catch (_) {}
    }
  }, { once: true });
})();