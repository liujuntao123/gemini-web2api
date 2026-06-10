"""Built-in usage analytics dashboard page."""


def dashboard_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>gemini-web2api usage dashboard</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --panel-2: #f1f4f7;
      --text: #18202a;
      --muted: #667382;
      --line: #d8dee6;
      --accent: #0f766e;
      --accent-2: #134e4a;
      --danger: #b42318;
      --warn: #b45309;
      --ok: #0f766e;
      --shadow: 0 12px 34px rgb(22 31 44 / 0.08);
      color-scheme: light;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }
    button, input, select { font: inherit; }
    .shell { max-width: 1440px; margin: 0 auto; padding: 22px; }
    .topbar {
      display: grid;
      grid-template-columns: minmax(260px, 1fr) auto;
      gap: 18px;
      align-items: center;
      margin-bottom: 18px;
    }
    .brand h1 { margin: 0; font-size: 24px; line-height: 1.2; font-weight: 760; }
    .brand p { margin: 6px 0 0; color: var(--muted); font-size: 14px; }
    .auth {
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }
    .field, .select {
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--text);
      padding: 0 10px;
      outline: none;
    }
    .field:focus, .select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgb(15 118 110 / 0.14); }
    .key-input { width: 230px; }
    .btn {
      height: 38px;
      border: 1px solid var(--accent);
      border-radius: 8px;
      background: var(--accent);
      color: #fff;
      padding: 0 14px;
      cursor: pointer;
      font-weight: 650;
    }
    .btn.secondary { background: var(--panel); color: var(--accent-2); border-color: var(--line); }
    .btn:active { transform: translateY(1px); }
    .status { min-width: 110px; color: var(--muted); font-size: 13px; text-align: right; }
    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      margin-bottom: 18px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    .filters label { display: flex; gap: 7px; align-items: center; color: var(--muted); font-size: 13px; }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }
    .metric, .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    .metric { padding: 16px; min-height: 110px; }
    .metric .label { color: var(--muted); font-size: 13px; }
    .metric .value { margin-top: 10px; font-size: 30px; line-height: 1; font-weight: 780; }
    .metric .sub { margin-top: 10px; color: var(--muted); font-size: 13px; }
    .dashboard-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(340px, 0.9fr);
      gap: 12px;
      margin-bottom: 12px;
    }
    .panel { min-width: 0; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }
    .panel-title { font-weight: 720; }
    .panel-note { color: var(--muted); font-size: 13px; }
    .panel-body { padding: 16px; }
    .chart { width: 100%; height: 260px; display: block; overflow: visible; }
    .axis { stroke: #c8d0da; stroke-width: 1; }
    .grid { stroke: #e7ebf0; stroke-width: 1; }
    .line { fill: none; stroke: var(--accent); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }
    .area { fill: rgb(15 118 110 / 0.11); }
    .dot { fill: var(--accent-2); }
    .bar { fill: var(--accent); }
    .latency { fill: #64748b; opacity: 0.55; }
    .legend { display: flex; gap: 14px; color: var(--muted); font-size: 13px; margin-top: 8px; }
    .legend span::before { content: ""; display: inline-block; width: 10px; height: 10px; margin-right: 6px; border-radius: 2px; background: var(--accent); }
    .legend .lat::before { background: #64748b; opacity: 0.55; }
    .bars { display: grid; gap: 12px; }
    .bar-row { display: grid; grid-template-columns: minmax(120px, 1fr) 3fr 72px; gap: 10px; align-items: center; font-size: 13px; }
    .bar-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
    .track { height: 10px; background: var(--panel-2); border-radius: 999px; overflow: hidden; }
    .fill { height: 100%; background: var(--accent); border-radius: 999px; }
    .bar-value { text-align: right; color: var(--muted); }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 1060px; }
    th, td { padding: 11px 12px; border-bottom: 1px solid var(--line); text-align: left; font-size: 13px; }
    th { color: var(--muted); font-weight: 650; background: #fafbfc; position: sticky; top: 0; }
    td { color: #27313f; }
    .pill {
      display: inline-flex;
      align-items: center;
      height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      background: var(--panel-2);
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .pill.ok { background: rgb(15 118 110 / 0.12); color: var(--ok); }
    .pill.err { background: rgb(180 35 24 / 0.12); color: var(--danger); }
    .empty, .error {
      min-height: 180px;
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--muted);
      padding: 24px;
    }
    .error { color: var(--danger); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .hide { display: none !important; }
    @media (max-width: 980px) {
      .topbar { grid-template-columns: 1fr; }
      .auth { justify-content: flex-start; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .dashboard-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 620px) {
      .shell { padding: 14px; }
      .metric-grid { grid-template-columns: 1fr; }
      .key-input { width: 100%; }
      .auth, .filters, .filters label { width: 100%; }
      .field, .select, .btn { width: 100%; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <h1>gemini-web2api 调用看板</h1>
        <p>查看调用量、错误、响应耗时、模型分布和最近请求日志。</p>
      </div>
      <div class="auth">
        <input id="apiKey" class="field key-input" type="password" autocomplete="off" placeholder="API Key">
        <button id="saveKey" class="btn secondary" type="button">保存密钥</button>
        <button id="refresh" class="btn" type="button">刷新</button>
        <div id="status" class="status">等待加载</div>
      </div>
    </header>

    <section class="filters" aria-label="筛选">
      <label>时间
        <select id="days" class="select">
          <option value="1">最近 1 天</option>
          <option value="7">最近 7 天</option>
          <option value="30">最近 30 天</option>
          <option value="90">最近 90 天</option>
        </select>
      </label>
      <label>API
        <select id="apiType" class="select">
          <option value="">全部</option>
          <option value="chat">Chat</option>
          <option value="responses">Responses</option>
          <option value="google">Google native</option>
        </select>
      </label>
      <label>结果
        <select id="success" class="select">
          <option value="">全部</option>
          <option value="true">成功</option>
          <option value="false">失败</option>
        </select>
      </label>
      <label>模型
        <input id="model" class="field" type="text" placeholder="按模型过滤">
      </label>
      <label>日志条数
        <select id="limit" class="select">
          <option value="50">50</option>
          <option value="100">100</option>
          <option value="200">200</option>
        </select>
      </label>
    </section>

    <section class="metric-grid" aria-label="核心指标">
      <div class="metric"><div class="label">总调用</div><div id="totalCalls" class="value">0</div><div id="totalCallsSub" class="sub">当前筛选范围</div></div>
      <div class="metric"><div class="label">成功率</div><div id="successRate" class="value">0%</div><div id="successSub" class="sub">成功 0, 失败 0</div></div>
      <div class="metric"><div class="label">平均响应</div><div id="avgMs" class="value">0ms</div><div class="sub">端到端响应时间</div></div>
      <div class="metric"><div class="label">估算 token</div><div id="totalTokens" class="value">0</div><div id="tokenSub" class="sub">输入 0, 输出 0</div></div>
    </section>

    <section class="dashboard-grid">
      <article class="panel">
        <div class="panel-head"><div class="panel-title">每日调用趋势</div><div class="panel-note">调用量与平均耗时</div></div>
        <div class="panel-body">
          <svg id="dailyChart" class="chart" role="img" aria-label="每日调用趋势图"></svg>
          <div class="legend"><span>调用量</span><span class="lat">平均耗时</span></div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head"><div class="panel-title">模型分布</div><div class="panel-note">按调用量排序</div></div>
        <div id="modelBars" class="panel-body bars"></div>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="panel">
        <div class="panel-head"><div class="panel-title">最近调用日志</div><div id="logCount" class="panel-note">0 条</div></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>时间</th><th>结果</th><th>模型</th><th>API</th><th>接口</th><th>耗时</th><th>Token</th><th>响应</th><th>错误</th><th>请求 ID</th>
              </tr>
            </thead>
            <tbody id="logsBody"></tbody>
          </table>
        </div>
        <div id="logsEmpty" class="empty hide">暂无调用日志。产生一次模型调用后这里会自动出现记录。</div>
      </article>
      <article class="panel">
        <div class="panel-head"><div class="panel-title">接口分布</div><div class="panel-note">成功与错误</div></div>
        <div id="endpointBars" class="panel-body bars"></div>
      </article>
    </section>
  </main>

  <script>
    const els = {
      apiKey: document.getElementById("apiKey"),
      saveKey: document.getElementById("saveKey"),
      refresh: document.getElementById("refresh"),
      status: document.getElementById("status"),
      days: document.getElementById("days"),
      apiType: document.getElementById("apiType"),
      success: document.getElementById("success"),
      model: document.getElementById("model"),
      limit: document.getElementById("limit"),
      totalCalls: document.getElementById("totalCalls"),
      totalCallsSub: document.getElementById("totalCallsSub"),
      successRate: document.getElementById("successRate"),
      successSub: document.getElementById("successSub"),
      avgMs: document.getElementById("avgMs"),
      totalTokens: document.getElementById("totalTokens"),
      tokenSub: document.getElementById("tokenSub"),
      dailyChart: document.getElementById("dailyChart"),
      modelBars: document.getElementById("modelBars"),
      endpointBars: document.getElementById("endpointBars"),
      logsBody: document.getElementById("logsBody"),
      logsEmpty: document.getElementById("logsEmpty"),
      logCount: document.getElementById("logCount")
    };

    const fmt = new Intl.NumberFormat("zh-CN");
    const keyName = "gemini-web2api-dashboard-key";
    els.apiKey.value = localStorage.getItem(keyName) || "";

    function setStatus(text, kind) {
      els.status.textContent = text;
      els.status.style.color = kind === "error" ? "var(--danger)" : "var(--muted)";
    }

    function params(extra) {
      const q = new URLSearchParams();
      q.set("days", els.days.value);
      if (els.apiType.value) q.set("api_type", els.apiType.value);
      if (els.success.value) q.set("success", els.success.value);
      if (els.model.value.trim()) q.set("model", els.model.value.trim());
      Object.entries(extra || {}).forEach(([k, v]) => q.set(k, v));
      return q.toString();
    }

    async function api(path) {
      const headers = {};
      const key = els.apiKey.value.trim();
      if (key) headers.Authorization = "Bearer " + key;
      const res = await fetch(path, {headers});
      if (res.status === 401) throw new Error("API Key 无效或缺失");
      if (!res.ok) throw new Error("请求失败: HTTP " + res.status);
      return res.json();
    }

    function pct(ok, total) {
      if (!total) return "0%";
      return Math.round((ok / total) * 1000) / 10 + "%";
    }

    function updateMetrics(summary) {
      const total = Number(summary.total_calls || 0);
      const ok = Number(summary.success_calls || 0);
      const err = Number(summary.error_calls || 0);
      els.totalCalls.textContent = fmt.format(total);
      els.totalCallsSub.textContent = "最近 " + els.days.value + " 天";
      els.successRate.textContent = pct(ok, total);
      els.successSub.textContent = "成功 " + fmt.format(ok) + ", 失败 " + fmt.format(err);
      els.avgMs.textContent = fmt.format(Math.round(summary.avg_response_ms || 0)) + "ms";
      els.totalTokens.textContent = fmt.format(summary.total_tokens || 0);
      els.tokenSub.textContent = "输入 " + fmt.format(summary.prompt_tokens || 0) + ", 输出 " + fmt.format(summary.completion_tokens || 0);
    }

    function drawDaily(rows) {
      const svg = els.dailyChart;
      const w = svg.clientWidth || 720;
      const h = 260;
      const pad = {l: 42, r: 22, t: 18, b: 34};
      svg.setAttribute("viewBox", "0 0 " + w + " " + h);
      svg.innerHTML = "";
      if (!rows.length) {
        svg.innerHTML = '<text x="' + w / 2 + '" y="130" text-anchor="middle" fill="#667382">暂无趋势数据</text>';
        return;
      }
      const maxCalls = Math.max(1, ...rows.map(r => Number(r.calls || 0)));
      const maxMs = Math.max(1, ...rows.map(r => Number(r.avg_response_ms || 0)));
      const innerW = w - pad.l - pad.r;
      const innerH = h - pad.t - pad.b;
      const x = i => pad.l + (rows.length === 1 ? innerW / 2 : (innerW * i) / (rows.length - 1));
      const yCalls = v => pad.t + innerH - (Number(v || 0) / maxCalls) * innerH;
      const yMs = v => pad.t + innerH - (Number(v || 0) / maxMs) * innerH;
      for (let i = 0; i < 4; i++) {
        const yy = pad.t + (innerH * i) / 3;
        svg.insertAdjacentHTML("beforeend", '<line class="grid" x1="' + pad.l + '" y1="' + yy + '" x2="' + (w - pad.r) + '" y2="' + yy + '"/>');
      }
      rows.forEach((r, i) => {
        const bw = Math.max(8, Math.min(28, innerW / Math.max(rows.length, 1) * 0.42));
        const bx = x(i) - bw / 2;
        const by = yMs(r.avg_response_ms);
        svg.insertAdjacentHTML("beforeend", '<rect class="latency" x="' + bx + '" y="' + by + '" width="' + bw + '" height="' + (pad.t + innerH - by) + '" rx="3"/>');
      });
      const points = rows.map((r, i) => [x(i), yCalls(r.calls)]);
      const area = "M" + points.map(p => p.join(",")).join(" L") + " L" + points[points.length - 1][0] + "," + (pad.t + innerH) + " L" + points[0][0] + "," + (pad.t + innerH) + " Z";
      const line = "M" + points.map(p => p.join(",")).join(" L");
      svg.insertAdjacentHTML("beforeend", '<path class="area" d="' + area + '"/><path class="line" d="' + line + '"/>');
      points.forEach(p => svg.insertAdjacentHTML("beforeend", '<circle class="dot" cx="' + p[0] + '" cy="' + p[1] + '" r="3"/>'));
      rows.forEach((r, i) => {
        if (i === 0 || i === rows.length - 1 || rows.length <= 8) {
          svg.insertAdjacentHTML("beforeend", '<text x="' + x(i) + '" y="' + (h - 10) + '" text-anchor="middle" fill="#667382" font-size="11">' + String(r.date || "").slice(5) + '</text>');
        }
      });
    }

    function renderBars(el, rows, nameKey, valueKey, emptyText) {
      el.innerHTML = "";
      if (!rows.length) {
        el.innerHTML = '<div class="empty">' + emptyText + '</div>';
        return;
      }
      const max = Math.max(1, ...rows.map(r => Number(r[valueKey] || 0)));
      rows.slice(0, 10).forEach(r => {
        const value = Number(r[valueKey] || 0);
        const width = Math.max(2, (value / max) * 100);
        const name = String(r[nameKey] || "unknown");
        el.insertAdjacentHTML("beforeend",
          '<div class="bar-row"><div class="bar-name" title="' + escapeHtml(name) + '">' + escapeHtml(name) + '</div>' +
          '<div class="track"><div class="fill" style="width:' + width + '%"></div></div>' +
          '<div class="bar-value">' + fmt.format(value) + '</div></div>'
        );
      });
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function renderLogs(data) {
      const logs = data.logs || [];
      els.logCount.textContent = fmt.format(data.total || 0) + " 条";
      els.logsBody.innerHTML = "";
      els.logsEmpty.classList.toggle("hide", logs.length > 0);
      logs.forEach(item => {
        const ok = item.success;
        const date = item.created_at ? new Date(item.created_at).toLocaleString("zh-CN", {hour12: false}) : "";
        els.logsBody.insertAdjacentHTML("beforeend",
          '<tr>' +
          '<td class="mono">' + escapeHtml(date) + '</td>' +
          '<td><span class="pill ' + (ok ? "ok" : "err") + '">' + (ok ? "成功" : "失败") + '</span></td>' +
          '<td>' + escapeHtml(item.model || "") + '</td>' +
          '<td><span class="pill">' + escapeHtml(item.api_type || "") + '</span></td>' +
          '<td class="mono">' + escapeHtml(item.endpoint || "") + '</td>' +
          '<td>' + fmt.format(item.response_ms || 0) + 'ms</td>' +
          '<td>' + fmt.format(item.total_tokens || 0) + '</td>' +
          '<td>' + fmt.format(item.response_chars || 0) + ' 字符</td>' +
          '<td title="' + escapeHtml(item.error_message || "") + '">' + escapeHtml(item.error_type || "") + '</td>' +
          '<td class="mono">' + escapeHtml(item.request_id || "") + '</td>' +
          '</tr>'
        );
      });
    }

    async function load() {
      setStatus("加载中", "");
      try {
        const [stats, logs] = await Promise.all([
          api("/v1/usage/stats?" + params()),
          api("/v1/usage/logs?" + params({limit: els.limit.value, offset: 0}))
        ]);
        updateMetrics(stats.summary || {});
        drawDaily(stats.by_day || []);
        renderBars(els.modelBars, stats.by_model || [], "model", "calls", "暂无模型数据");
        renderBars(els.endpointBars, stats.by_endpoint || [], "endpoint", "calls", "暂无接口数据");
        renderLogs(logs);
        setStatus("已更新", "");
      } catch (err) {
        setStatus(err.message, "error");
      }
    }

    els.saveKey.addEventListener("click", () => {
      localStorage.setItem(keyName, els.apiKey.value.trim());
      setStatus("密钥已保存", "");
      load();
    });
    els.refresh.addEventListener("click", load);
    [els.days, els.apiType, els.success, els.limit].forEach(el => el.addEventListener("change", load));
    els.model.addEventListener("keydown", ev => { if (ev.key === "Enter") load(); });
    window.addEventListener("resize", () => load());
    load();
  </script>
</body>
</html>"""
