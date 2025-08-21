
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const badge = $("#auth-badge");
  const storageKey = "tokens";
  const API = {
    base: "", // same-origin
    get tokens() { try { return JSON.parse(localStorage.getItem(storageKey) || "null"); } catch { return null; } },
    set tokens(v) {
      if (v) localStorage.setItem(storageKey, JSON.stringify(v));
      else localStorage.removeItem(storageKey);
      badge.textContent = v ? "Signed in" : "Not signed in";
    },
    async refresh() {
      const t = API.tokens;
      if (!t?.refresh) throw new Error("No refresh token");
      const r = await fetch("/api/auth/token/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: t.refresh }),
      });
      if (!r.ok) throw new Error("Refresh failed");
      const data = await r.json();
      API.tokens = { access: data.access, refresh: t.refresh };
      return data.access;
    },
    async request(path, opts = {}, retry = true) {
      const t = API.tokens;
      opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
      if (t?.access) opts.headers["Authorization"] = "Bearer " + t.access;
      const res = await fetch(path, opts);
      if (res.status === 401 && retry) {
        try {
          const tok = await API.refresh();
          opts.headers["Authorization"] = "Bearer " + tok;
          return await API.request(path, opts, false);
        } catch {
          API.tokens = null;
        }
      }
      return res;
    },
    async getJson(path) {
      const r = await API.request(path);
      if (!r.ok) throw await r.json().catch(() => new Error(r.statusText));
      return r.json();
    },
    async sendJson(path, method, body) {
      const r = await API.request(path, { method, body: JSON.stringify(body) });
      const text = await r.text();
      try { return { ok: r.ok, data: JSON.parse(text) }; } catch { return { ok: r.ok, data: text }; }
    },
  };
  // Tabs
  const tabs = $("#tabs");
  const sections = {
    auth: $("#tab-auth"),
    menu: $("#tab-menu"),
    orders: $("#tab-orders"),
    explorer: $("#tab-explorer"),
  };
  tabs?.addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") return;
    const tab = e.target.getAttribute("data-tab");
    $$("#tabs button").forEach(b => b.classList.toggle("active", b === e.target));
    Object.entries(sections).forEach(([k, el]) => el.style.display = (k === tab) ? "" : "none");
  });
  // Auth
  const loginForm = $("#login-form");
  const logoutBtn = $("#logout-btn");
  const authErr = $("#auth-error");
  loginForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    authErr.style.display = "none";
    const username = $("#username").value;
    const password = $("#password").value;
    try {
      const r = await fetch("/api/auth/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || "Login failed");
      }
      const data = await r.json();
      API.tokens = data;
    } catch (err) {
      authErr.textContent = err.message;
      authErr.style.display = "";
    }
  });
  logoutBtn?.addEventListener("click", () => (API.tokens = null));
  // Menu
  const menuErr = $("#menu-error");
  const catUl = $("#categories");
  const itemsUl = $("#items");
  async function loadMenu() {
    menuErr.style.display = "none";
    try {
      const cats = await API.getJson("/api/menu/categories/");
      const items = await API.getJson("/api/menu/items/");
      const catList = (cats.results ?? cats);
      const itemList = (items.results ?? items);
      catUl.innerHTML = catList.map(c => `<li><code>#${c.id}</code> ${c.name}</li>`).join("");
      itemsUl.innerHTML = itemList.map(i => `<li><code>#${i.id}</code> ${i.name} ${i.price ? `<span class="muted">— ${i.price}</span>` : ""}</li>`).join("");
    } catch (e) {
      menuErr.textContent = (e.detail || e.message || "Failed to load menu");
      menuErr.style.display = "";
    }
  }
  $("#reload-menu")?.addEventListener("click", loadMenu);
  // Orders
  const ordersErr = $("#orders-error");
  const ordersUl = $("#orders");
  const placeBody = $("#place-body");
  const createBody = $("#create-body");
  const respPre = $("#orders-response");
  let selectedOrderId = null;
  async function loadOrders() {
    ordersErr.style.display = "none";
    try {
      const data = await API.getJson("/api/orders/");
      const list = (data.results ?? data);
      ordersUl.innerHTML = list.map(o => (
        `<li style="display:flex; gap:8; align-items:center;">
          <label><input type="radio" name="oid" data-oid="${o.id}"> #${o.id}</label>
          <span class="muted">${o.status ?? ""}</span>
        </li>`
      )).join("");
      ordersUl.querySelectorAll('input[name="oid"]').forEach(inp => {
        inp.addEventListener("change", () => { selectedOrderId = inp.getAttribute("data-oid"); });
      });
    } catch (e) {
      ordersErr.textContent = (e.detail || e.message || "Failed to load orders");
      ordersErr.style.display = "";
    }
  }
  $("#reload-orders")?.addEventListener("click", loadOrders);
  $("#place-order")?.addEventListener("click", async () => {
    if (!selectedOrderId) return;
    try {
      const body = JSON.parse(placeBody.value);
      const { ok, data } = await API.sendJson(`/api/orders/${selectedOrderId}/place/`, "POST", body);
      respPre.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      respPre.textContent = e.message || String(e);
    }
  });
  $("#create-order")?.addEventListener("click", async () => {
    try {
      const body = JSON.parse(createBody.value);
      const { ok, data } = await API.sendJson(`/api/orders/`, "POST", body);
      respPre.textContent = JSON.stringify(data, null, 2);
      await loadOrders();
    } catch (e) {
      respPre.textContent = e.message || String(e);
    }
  });
  // Explorer
  const schemaErr = $("#schema-error");
  const pathSel = $("#path");
  const methodSel = $("#method");
  const bodyTxt = $("#body");
  const resp = $("#response");
  async function loadSchema() {
    schemaErr.style.display = "none";
    try {
      const s = await API.getJson("/api/schema/");
      const paths = Object.keys(s.paths || {}).sort();
      pathSel.innerHTML = `<option value="">-- Pick an endpoint --</option>` +
        paths.map(p => `<option>${p}</option>`).join("");
    } catch (e) {
      schemaErr.textContent = (e.detail || e.message || "Failed to load /api/schema/");
      schemaErr.style.display = "";
    }
  }
  $("#reload-schema")?.addEventListener("click", loadSchema);
  $("#send")?.addEventListener("click", async () => {
    const p = pathSel.value;
    const m = methodSel.value.toUpperCase();
    if (!p) return;
    let payload = {};
    if (["POST", "PUT", "PATCH"].includes(m)) {
      try { payload = JSON.parse(bodyTxt.value || "{}"); } catch (e) { resp.textContent = "Invalid JSON body"; return; }
    }
    try {
      const { ok, data } = await API.sendJson(p, m, payload);
      resp.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    } catch (e) {
      resp.textContent = e.message || String(e);
    }
  });
  // initial loads
  loadMenu();
  loadOrders();
  loadSchema();
  // restore badge
  badge.textContent = API.tokens ? "Signed in" : "Not signed in";
})();
