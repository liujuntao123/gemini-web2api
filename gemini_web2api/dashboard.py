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
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-soft: #f8fafc;
      --text: #17202e;
      --muted: #647185;
      --faint: #8a96a8;
      --line: #dce3ec;
      --line-soft: #edf1f6;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --accent-soft: #e6f4f2;
      --danger: #b42318;
      --danger-soft: #fef0ec;
      --warn: #b45309;
      --ok: #0f766e;
      --shadow: 0 14px 38px rgb(30 41 59 / 0.08);
      color-scheme: light;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-width: 320px;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        linear-gradient(180deg, #eef4f8 0, var(--bg) 280px),
        var(--bg);
      letter-spacing: 0;
    }
    button, input, select { font: inherit; }
    button { -webkit-tap-highlight-color: transparent; }
    .shell {
      width: min(100%, 1480px);
      margin: 0 auto;
      padding: 24px;
    }
    .topbar {
      display: grid;
      grid-template-columns: minmax(280px, 1fr) auto;
      gap: 18px;
      align-items: start;
      margin-bottom: 16px;
    }
    .brand {
      display: grid;
      gap: 8px;
    }
    .brand h1 {
      margin: 0;
      font-size: 26px;
      line-height: 1.18;
      font-weight: 780;
    }
    .brand p {
      margin: 0;
      max-width: 760px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }
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
      transition: border-color .15s ease, box-shadow .15s ease, background .15s ease;
    }
    .field::placeholder { color: var(--faint); }
    .field:focus, .select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgb(15 118 110 / 0.14);
    }
    .key-input { width: 236px; }
    .btn {
      height: 38px;
      border: 1px solid var(--accent);
      border-radius: 8px;
      background: var(--accent);
      color: #fff;
      padding: 0 14px;
      cursor: pointer;
      font-weight: 700;
      transition: transform .12s ease, background .15s ease, border-color .15s ease;
    }
    .btn:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
    .btn.secondary {
      background: var(--panel);
      color: var(--accent-strong);
      border-color: var(--line);
    }
    .btn.secondary:hover { background: var(--accent-soft); border-color: #a8d8d3; }
    .btn:active { transform: translateY(1px); }
    .btn[disabled] { cursor: wait; opacity: .7; }
    .status {
      min-width: 118px;
      color: var(--muted);
      font-size: 13px;
      text-align: right;
    }
    .toolbar {
      display: grid;
      grid-template-columns: repeat(5, minmax(136px, 1fr));
      gap: 10px;
      align-items: end;
      margin-bottom: 14px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgb(255 255 255 / 0.92);
      box-shadow: var(--shadow);
    }
    .toolbar label {
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 680;
    }
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
    .metric {
      min-height: 122px;
      padding: 16px;
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .metric-top {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
    }
    .metric .label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 720;
    }
    .metric .value {
      font-size: 31px;
      line-height: 1;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }
    .metric .sub {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .metric-meter {
      height: 5px;
      overflow: hidden;
      border-radius: 999px;
      background: var(--line-soft);
    }
    .metric-meter span {
      display: block;
      width: 0%;
      height: 100%;
      border-radius: inherit;
      background: var(--accent);
      transition: width .25s ease;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 24px;
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--panel-soft);
      color: var(--muted);
      border: 1px solid var(--line-soft);
      font-size: 12px;
      font-weight: 720;
      white-space: nowrap;
    }
    .badge.ok {
      background: var(--accent-soft);
      color: var(--ok);
      border-color: #bfe5df;
    }
    .badge.err {
      background: var(--danger-soft);
      color: var(--danger);
      border-color: #fac9be;
    }
    .dashboard-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(340px, .9fr);
      gap: 12px;
      margin-bottom: 12px;
    }
    .dashboard-grid.compact {
      grid-template-columns: minmax(0, 1.2fr) minmax(360px, .8fr);
    }
    .panel { min-width: 0; overflow: hidden; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line-soft);
      background: linear-gradient(180deg, #fff, #fbfcfe);
    }
    .panel-title {
      font-weight: 760;
      line-height: 1.25;
    }
    .panel-note {
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .panel-body { padding: 14px 16px 16px; }
    .chart {
      width: 100%;
      height: 318px;
      min-height: 280px;
    }
    .chart.sm { height: 286px; }
    .chart-state {
      min-height: 240px;
      display: grid;
      place-items: center;
      padding: 24px;
      color: var(--muted);
      text-align: center;
      line-height: 1.6;
      background: repeating-linear-gradient(
        -45deg,
        var(--panel-soft),
        var(--panel-soft) 8px,
        #ffffff 8px,
        #ffffff 16px
      );
      border: 1px dashed var(--line);
      border-radius: 8px;
    }
    .split-list {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .split-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      padding: 10px 0;
      border-top: 1px solid var(--line-soft);
      font-size: 13px;
    }
    .split-row:first-child { border-top: 0; padding-top: 0; }
    .split-name {
      overflow: hidden;
      color: var(--text);
      font-weight: 700;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .split-meta {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      text-align: right;
      white-space: nowrap;
    }
    .table-panel .panel-head { border-bottom: 0; }
    .table-tools {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .table-search { width: 220px; }
    .table-wrap {
      overflow: auto;
      border-top: 1px solid var(--line-soft);
    }
    table {
      width: 100%;
      min-width: 1280px;
      border-collapse: separate;
      border-spacing: 0;
    }
    th, td {
      padding: 11px 12px;
      border-bottom: 1px solid var(--line-soft);
      text-align: left;
      font-size: 13px;
      vertical-align: middle;
    }
    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: var(--muted);
      font-weight: 760;
      box-shadow: inset 0 -1px 0 var(--line-soft);
    }
    tbody tr { background: #fff; }
    tbody tr:hover { background: #f8fbfb; }
    tbody tr.error-row { background: #fffdfc; }
    tbody tr.error-row:hover { background: #fff7f5; }
    td {
      color: #27313f;
      max-width: 260px;
    }
    .num {
      text-align: right;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .truncate {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .empty, .error {
      min-height: 180px;
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--muted);
      padding: 24px;
      line-height: 1.6;
    }
    .error { color: var(--danger); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .hide { display: none !important; }
    @media (max-width: 1080px) {
      .topbar { grid-template-columns: 1fr; }
      .auth { justify-content: flex-start; }
      .toolbar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .dashboard-grid, .dashboard-grid.compact { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
      .shell { padding: 14px; }
      .brand h1 { font-size: 22px; }
      .auth, .toolbar, .toolbar label { width: 100%; }
      .toolbar { grid-template-columns: 1fr; }
      .field, .select, .btn, .key-input, .table-search { width: 100%; }
      .metric-grid { grid-template-columns: 1fr; }
      .panel-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .panel-note { white-space: normal; }
      .chart { height: 300px; }
      .chart.sm { height: 270px; }
      .table-tools { width: 100%; justify-content: stretch; }
      .status { width: 100%; text-align: left; }
    }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <h1>gemini-web2api 调用看板</h1>
        <p>集中查看调用量、错误、响应耗时、Token 消耗、模型分布和最近请求日志。</p>
      </div>
      <div class="auth">
        <input id="apiKey" class="field key-input" type="password" autocomplete="off" placeholder="API Key">
        <button id="saveKey" class="btn secondary" type="button">保存密钥</button>
        <button id="refresh" class="btn" type="button">刷新</button>
        <div id="status" class="status">等待加载</div>
      </div>
    </header>

    <section class="toolbar" aria-label="筛选">
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
        <input id="model" class="field" type="text" placeholder="按模型过滤后回车">
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
      <div class="metric">
        <div class="metric-top"><div class="label">总调用</div><span id="totalWindow" class="badge">当前范围</span></div>
        <div id="totalCalls" class="value">0</div>
        <div id="totalCallsSub" class="sub">等待数据</div>
        <div class="metric-meter"><span id="totalMeter"></span></div>
      </div>
      <div class="metric">
        <div class="metric-top"><div class="label">成功率</div><span id="successBadge" class="badge">0%</span></div>
        <div id="successRate" class="value">0%</div>
        <div id="successSub" class="sub">成功 0, 失败 0</div>
        <div class="metric-meter"><span id="successMeter"></span></div>
      </div>
      <div class="metric">
        <div class="metric-top"><div class="label">平均响应</div><span id="latencyBadge" class="badge">延迟</span></div>
        <div id="avgMs" class="value">0ms</div>
        <div class="sub">端到端响应时间</div>
        <div class="metric-meter"><span id="latencyMeter"></span></div>
      </div>
      <div class="metric">
        <div class="metric-top"><div class="label">估算 Token</div><span id="tokenBadge" class="badge">输入/输出</span></div>
        <div id="totalTokens" class="value">0</div>
        <div id="tokenSub" class="sub">输入 0, 输出 0</div>
        <div class="metric-meter"><span id="tokenMeter"></span></div>
      </div>
    </section>

    <section class="dashboard-grid">
      <article class="panel">
        <div class="panel-head">
          <div class="panel-title">每日趋势</div>
          <div class="panel-note">成功、失败、Token 与平均耗时</div>
        </div>
        <div class="panel-body">
          <div id="dailyChart" class="chart" role="img" aria-label="每日调用趋势图"></div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head">
          <div class="panel-title">模型用量</div>
          <div class="panel-note">调用与 Token 占比</div>
        </div>
        <div class="panel-body">
          <div id="modelChart" class="chart sm" role="img" aria-label="模型用量图"></div>
          <div id="modelList" class="split-list"></div>
        </div>
      </article>
    </section>

    <section class="dashboard-grid compact">
      <article class="panel">
        <div class="panel-head">
          <div class="panel-title">接口健康度</div>
          <div class="panel-note">按接口统计成功和失败</div>
        </div>
        <div class="panel-body">
          <div id="endpointChart" class="chart sm" role="img" aria-label="接口健康度图"></div>
        </div>
      </article>
      <article class="panel">
        <div class="panel-head">
          <div class="panel-title">上游模式</div>
          <div class="panel-note">匿名纯文本调用</div>
        </div>
        <div class="panel-body">
          <div id="upstreamChart" class="chart sm" role="img" aria-label="上游模式图"></div>
          <div id="upstreamList" class="split-list"></div>
        </div>
      </article>
    </section>

    <section class="panel" style="margin-bottom:12px">
      <div class="panel-head">
        <div class="panel-title">Token 构成</div>
        <div class="panel-note">输入和输出占比</div>
      </div>
      <div class="panel-body">
        <div id="tokenChart" class="chart sm" role="img" aria-label="Token 构成图"></div>
      </div>
    </section>

    <section class="panel table-panel">
      <div class="panel-head">
        <div>
          <div class="panel-title">最近调用日志</div>
          <div id="logCount" class="panel-note">0 条</div>
        </div>
        <div class="table-tools">
          <input id="tableSearch" class="field table-search" type="search" placeholder="在当前日志中搜索">
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>结果</th>
              <th>模型</th>
              <th>API</th>
              <th>模式</th>
              <th>接口</th>
              <th class="num">耗时</th>
              <th class="num">Token</th>
              <th class="num">响应</th>
              <th>错误</th>
              <th>请求 ID</th>
            </tr>
          </thead>
          <tbody id="logsBody"></tbody>
        </table>
      </div>
      <div id="logsEmpty" class="empty hide">暂无调用日志。产生一次模型调用后这里会自动出现记录。</div>
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
      tableSearch: document.getElementById("tableSearch"),
      totalWindow: document.getElementById("totalWindow"),
      totalCalls: document.getElementById("totalCalls"),
      totalCallsSub: document.getElementById("totalCallsSub"),
      totalMeter: document.getElementById("totalMeter"),
      successRate: document.getElementById("successRate"),
      successBadge: document.getElementById("successBadge"),
      successSub: document.getElementById("successSub"),
      successMeter: document.getElementById("successMeter"),
      avgMs: document.getElementById("avgMs"),
      latencyBadge: document.getElementById("latencyBadge"),
      latencyMeter: document.getElementById("latencyMeter"),
      totalTokens: document.getElementById("totalTokens"),
      tokenBadge: document.getElementById("tokenBadge"),
      tokenSub: document.getElementById("tokenSub"),
      tokenMeter: document.getElementById("tokenMeter"),
      dailyChart: document.getElementById("dailyChart"),
      modelChart: document.getElementById("modelChart"),
      modelList: document.getElementById("modelList"),
      endpointChart: document.getElementById("endpointChart"),
      upstreamChart: document.getElementById("upstreamChart"),
      upstreamList: document.getElementById("upstreamList"),
      tokenChart: document.getElementById("tokenChart"),
      logsBody: document.getElementById("logsBody"),
      logsEmpty: document.getElementById("logsEmpty"),
      logCount: document.getElementById("logCount")
    };

    const fmt = new Intl.NumberFormat("zh-CN");
    const compactFmt = new Intl.NumberFormat("zh-CN", {notation: "compact", maximumFractionDigits: 1});
    const pctFmt = new Intl.NumberFormat("zh-CN", {maximumFractionDigits: 1});
    const keyName = "gemini-web2api-dashboard-key";
    const charts = {daily: null, model: null, endpoint: null, upstream: null, token: null};
    const chartPalette = ["#0f766e", "#f97316", "#64748b", "#14b8a6", "#94a3b8", "#0ea5e9"];
    let currentLogs = [];
    let lastLoadId = 0;

    els.apiKey.value = localStorage.getItem(keyName) || "";

    function setStatus(text, kind) {
      els.status.textContent = text;
      els.status.style.color = kind === "error" ? "var(--danger)" : "var(--muted)";
    }

    function setLoading(isLoading) {
      els.refresh.disabled = isLoading;
      els.saveKey.disabled = isLoading;
      document.body.classList.toggle("is-loading", isLoading);
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

    function successPct(ok, total) {
      if (!total) return 0;
      return Math.round((ok / total) * 1000) / 10;
    }

    function formatPct(value) {
      return pctFmt.format(value) + "%";
    }

    function latencyLevel(ms) {
      if (!ms) return "暂无";
      if (ms <= 1200) return "良好";
      if (ms <= 3000) return "偏慢";
      return "拥堵";
    }

    function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    function updateMetrics(summary) {
      const total = Number(summary.total_calls || 0);
      const ok = Number(summary.success_calls || 0);
      const err = Number(summary.error_calls || 0);
      const avgMs = Math.round(Number(summary.avg_response_ms || 0));
      const tokens = Number(summary.total_tokens || 0);
      const promptTokens = Number(summary.prompt_tokens || 0);
      const completionTokens = Number(summary.completion_tokens || 0);
      const anonymousCalls = Number(summary.anonymous_calls || 0);
      const rate = successPct(ok, total);
      const outputShare = tokens ? Math.round((completionTokens / tokens) * 100) : 0;

      els.totalWindow.textContent = "最近 " + els.days.value + " 天";
      els.totalCalls.textContent = fmt.format(total);
      els.totalCallsSub.textContent = total ? "匿名 " + fmt.format(anonymousCalls) : "当前筛选范围无调用";
      els.totalMeter.style.width = total ? "100%" : "0%";

      els.successRate.textContent = formatPct(rate);
      els.successBadge.textContent = err ? "失败 " + fmt.format(err) : "无失败";
      els.successBadge.className = "badge " + (err ? "err" : "ok");
      els.successSub.textContent = "成功 " + fmt.format(ok) + ", 失败 " + fmt.format(err);
      els.successMeter.style.width = Math.max(0, Math.min(100, rate)) + "%";

      els.avgMs.textContent = fmt.format(avgMs) + "ms";
      els.latencyBadge.textContent = latencyLevel(avgMs);
      els.latencyBadge.className = "badge " + (avgMs > 3000 ? "err" : "ok");
      els.latencyMeter.style.width = Math.max(4, Math.min(100, avgMs ? 100 - (avgMs / 5000) * 100 : 0)) + "%";

      els.totalTokens.textContent = fmt.format(tokens);
      els.tokenBadge.textContent = outputShare ? "输出 " + outputShare + "%" : "输入/输出";
      els.tokenSub.textContent = "输入 " + fmt.format(promptTokens) + ", 输出 " + fmt.format(completionTokens);
      els.tokenMeter.style.width = Math.max(0, Math.min(100, outputShare)) + "%";
    }

    function ensureChart(name, el) {
      if (!window.echarts) return null;
      if (!charts[name]) {
        el.innerHTML = "";
        charts[name] = echarts.init(el, null, {renderer: "canvas"});
      }
      return charts[name];
    }

    function showChartState(name, el, text) {
      if (charts[name]) {
        charts[name].dispose();
        charts[name] = null;
      }
      el.innerHTML = '<div class="chart-state">' + escapeHtml(text) + '</div>';
    }

    function chartBase() {
      return {
        color: chartPalette,
        backgroundColor: "transparent",
        animationDuration: 420,
        textStyle: {
          color: "#17202e",
          fontFamily: 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
        },
        tooltip: {
          trigger: "axis",
          confine: true,
          backgroundColor: "rgba(255,255,255,.98)",
          borderColor: "#dce3ec",
          borderWidth: 1,
          textStyle: {color: "#17202e"},
          extraCssText: "box-shadow: 0 12px 28px rgba(15,23,42,.12); border-radius: 8px;"
        },
        grid: {left: 42, right: 52, top: 38, bottom: 36, containLabel: true}
      };
    }

    function renderDaily(rows) {
      if (!rows.length) {
        showChartState("daily", els.dailyChart, "暂无趋势数据");
        return;
      }
      const chart = ensureChart("daily", els.dailyChart);
      if (!chart) {
        showChartState("daily", els.dailyChart, "ECharts 静态资源未加载，无法渲染趋势图");
        return;
      }
      const labels = rows.map(r => String(r.date || "").slice(5) || "未知");
      chart.setOption({
        ...chartBase(),
        legend: {
          top: 4,
          right: 0,
          itemWidth: 10,
          itemHeight: 10,
          textStyle: {color: "#647185"}
        },
        xAxis: {
          type: "category",
          data: labels,
          axisLine: {lineStyle: {color: "#dce3ec"}},
          axisTick: {show: false},
          axisLabel: {color: "#647185"}
        },
        yAxis: [
          {
            type: "value",
            name: "调用",
            minInterval: 1,
            axisLabel: {color: "#647185"},
            splitLine: {lineStyle: {color: "#edf1f6"}}
          },
          {
            type: "value",
            name: "ms",
            axisLabel: {color: "#647185"},
            splitLine: {show: false}
          },
          {
            type: "value",
            name: "Token",
            show: false,
            splitLine: {show: false}
          }
        ],
        series: [
          {
            name: "成功",
            type: "bar",
            stack: "calls",
            data: rows.map(r => Number(r.success_calls || 0)),
            barMaxWidth: 28,
            itemStyle: {borderRadius: [5, 5, 0, 0]}
          },
          {
            name: "失败",
            type: "bar",
            stack: "calls",
            data: rows.map(r => Number(r.error_calls || 0)),
            barMaxWidth: 28,
            itemStyle: {color: "#b42318", borderRadius: [5, 5, 0, 0]}
          },
          {
            name: "Token",
            type: "line",
            smooth: true,
            yAxisIndex: 2,
            data: rows.map(r => Number(r.total_tokens || 0)),
            symbolSize: 6,
            lineStyle: {width: 2, color: "#64748b"},
            itemStyle: {color: "#64748b"}
          },
          {
            name: "平均耗时",
            type: "line",
            smooth: true,
            yAxisIndex: 1,
            data: rows.map(r => Number(r.avg_response_ms || 0)),
            symbolSize: 6,
            lineStyle: {width: 3, color: "#f97316"},
            itemStyle: {color: "#f97316"}
          }
        ]
      }, true);
    }

    function renderModel(rows) {
      els.modelList.innerHTML = "";
      if (!rows.length) {
        showChartState("model", els.modelChart, "暂无模型数据");
        return;
      }
      const chart = ensureChart("model", els.modelChart);
      if (!chart) {
        showChartState("model", els.modelChart, "ECharts 静态资源未加载，无法渲染模型图");
        return;
      }
      const topRows = rows.slice(0, 8);
      chart.setOption({
        ...chartBase(),
        tooltip: {trigger: "item", confine: true},
        legend: {show: false},
        series: [{
          name: "调用",
          type: "pie",
          radius: ["48%", "72%"],
          center: ["50%", "48%"],
          avoidLabelOverlap: true,
          itemStyle: {borderRadius: 6, borderColor: "#fff", borderWidth: 2},
          label: {
            formatter: "{b}\\n{d}%",
            color: "#17202e",
            lineHeight: 17
          },
          labelLine: {length: 12, length2: 8},
          data: topRows.map(r => ({
            name: String(r.model || "unknown"),
            value: Number(r.calls || 0),
            tokens: Number(r.total_tokens || 0),
            avgMs: Number(r.avg_response_ms || 0)
          }))
        }]
      }, true);
      topRows.slice(0, 6).forEach(r => {
        const name = String(r.model || "unknown");
        els.modelList.insertAdjacentHTML("beforeend",
          '<div class="split-row">' +
          '<div class="split-name" title="' + escapeHtml(name) + '">' + escapeHtml(name) + '</div>' +
          '<div class="split-meta">' + fmt.format(r.calls || 0) + ' 次 · ' + compactFmt.format(r.total_tokens || 0) + ' Token</div>' +
          '</div>'
        );
      });
    }

    function renderEndpoint(rows) {
      if (!rows.length) {
        showChartState("endpoint", els.endpointChart, "暂无接口数据");
        return;
      }
      const chart = ensureChart("endpoint", els.endpointChart);
      if (!chart) {
        showChartState("endpoint", els.endpointChart, "ECharts 静态资源未加载，无法渲染接口图");
        return;
      }
      const topRows = rows.slice(0, 10).reverse();
      chart.setOption({
        ...chartBase(),
        legend: {
          top: 4,
          right: 0,
          itemWidth: 10,
          itemHeight: 10,
          textStyle: {color: "#647185"}
        },
        grid: {left: 8, right: 32, top: 38, bottom: 8, containLabel: true},
        xAxis: {
          type: "value",
          minInterval: 1,
          axisLabel: {color: "#647185"},
          splitLine: {lineStyle: {color: "#edf1f6"}}
        },
        yAxis: {
          type: "category",
          data: topRows.map(r => String(r.endpoint || "unknown")),
          axisLabel: {
            color: "#647185",
            width: 160,
            overflow: "truncate"
          },
          axisLine: {lineStyle: {color: "#dce3ec"}},
          axisTick: {show: false}
        },
        series: [
          {
            name: "成功",
            type: "bar",
            stack: "endpoint",
            data: topRows.map(r => Number(r.success_calls || 0)),
            barMaxWidth: 18,
            itemStyle: {borderRadius: [0, 5, 5, 0]}
          },
          {
            name: "失败",
            type: "bar",
            stack: "endpoint",
            data: topRows.map(r => Number(r.error_calls || 0)),
            barMaxWidth: 18,
            itemStyle: {color: "#b42318", borderRadius: [0, 5, 5, 0]}
          }
        ]
      }, true);
    }

    function renderToken(summary) {
      const prompt = Number(summary.prompt_tokens || 0);
      const completion = Number(summary.completion_tokens || 0);
      const total = prompt + completion;
      if (!total) {
        showChartState("token", els.tokenChart, "暂无 Token 数据");
        return;
      }
      const chart = ensureChart("token", els.tokenChart);
      if (!chart) {
        showChartState("token", els.tokenChart, "ECharts 静态资源未加载，无法渲染 Token 图");
        return;
      }
      chart.setOption({
        ...chartBase(),
        tooltip: {trigger: "item", confine: true},
        legend: {
          bottom: 0,
          itemWidth: 10,
          itemHeight: 10,
          textStyle: {color: "#647185"}
        },
        series: [{
          name: "Token",
          type: "pie",
          radius: ["50%", "74%"],
          center: ["50%", "44%"],
          itemStyle: {borderRadius: 6, borderColor: "#fff", borderWidth: 2},
          label: {
            formatter: "{b}\\n{d}%",
            color: "#17202e",
            lineHeight: 17
          },
          data: [
            {name: "输入", value: prompt},
            {name: "输出", value: completion}
          ]
        }]
      }, true);
    }

    function upstreamLabel(mode) {
      if (mode === "anonymous") return "匿名";
      return "未发送";
    }

    function renderUpstream(rows) {
      els.upstreamList.innerHTML = "";
      if (!rows.length) {
        showChartState("upstream", els.upstreamChart, "暂无上游模式数据");
        return;
      }
      const chart = ensureChart("upstream", els.upstreamChart);
      if (!chart) {
        showChartState("upstream", els.upstreamChart, "ECharts 静态资源未加载，无法渲染模式图");
        return;
      }
      const mapped = rows.map(r => ({
        name: upstreamLabel(r.upstream_mode),
        value: Number(r.calls || 0),
        mode: r.upstream_mode,
        errors: Number(r.error_calls || 0)
      }));
      chart.setOption({
        ...chartBase(),
        tooltip: {trigger: "item", confine: true},
        legend: {
          bottom: 0,
          itemWidth: 10,
          itemHeight: 10,
          textStyle: {color: "#647185"}
        },
        series: [{
          name: "上游模式",
          type: "pie",
          radius: ["48%", "72%"],
          center: ["50%", "44%"],
          itemStyle: {borderRadius: 6, borderColor: "#fff", borderWidth: 2},
          label: {
            formatter: "{b}\\n{d}%",
            color: "#17202e",
            lineHeight: 17
          },
          data: mapped
        }]
      }, true);
      mapped.forEach(r => {
        els.upstreamList.insertAdjacentHTML("beforeend",
          '<div class="split-row">' +
          '<div class="split-name">' + escapeHtml(r.name) + '</div>' +
          '<div class="split-meta">' + fmt.format(r.value) + ' 次 · 失败 ' + fmt.format(r.errors) + '</div>' +
          '</div>'
        );
      });
    }

    function renderLogs(data) {
      currentLogs = data.logs || [];
      renderFilteredLogs();
    }

    function renderFilteredLogs() {
      const keyword = els.tableSearch.value.trim().toLowerCase();
      const logs = keyword
        ? currentLogs.filter(item => JSON.stringify(item).toLowerCase().includes(keyword))
        : currentLogs;
      els.logCount.textContent = fmt.format(logs.length) + " / " + fmt.format(currentLogs.length) + " 条";
      els.logsBody.innerHTML = "";
      els.logsEmpty.classList.toggle("hide", logs.length > 0);
      logs.forEach(item => {
        const ok = item.success;
        const date = item.created_at ? new Date(item.created_at).toLocaleString("zh-CN", {hour12: false}) : "";
        const model = item.model || "";
        const endpoint = item.endpoint || "";
        const err = item.error_type || item.error_message || "";
        const mode = item.upstream_mode || "not_sent";
        els.logsBody.insertAdjacentHTML("beforeend",
          '<tr class="' + (ok ? "" : "error-row") + '">' +
          '<td class="mono">' + escapeHtml(date) + '</td>' +
          '<td><span class="badge ' + (ok ? "ok" : "err") + '">' + (ok ? "成功" : "失败") + '</span></td>' +
          '<td><div class="truncate" title="' + escapeHtml(model) + '">' + escapeHtml(model) + '</div></td>' +
          '<td><span class="badge">' + escapeHtml(item.api_type || "") + '</span></td>' +
          '<td><span class="badge">' + escapeHtml(upstreamLabel(mode)) + '</span></td>' +
          '<td class="mono"><div class="truncate" title="' + escapeHtml(endpoint) + '">' + escapeHtml(endpoint) + '</div></td>' +
          '<td class="num">' + fmt.format(item.response_ms || 0) + 'ms</td>' +
          '<td class="num">' + fmt.format(item.total_tokens || 0) + '</td>' +
          '<td class="num">' + fmt.format(item.response_chars || 0) + ' 字符</td>' +
          '<td><div class="truncate" title="' + escapeHtml(item.error_message || "") + '">' + escapeHtml(err) + '</div></td>' +
          '<td class="mono"><div class="truncate" title="' + escapeHtml(item.request_id || "") + '">' + escapeHtml(item.request_id || "") + '</div></td>' +
          '</tr>'
        );
      });
    }

    async function load() {
      const loadId = ++lastLoadId;
      setLoading(true);
      setStatus("加载中", "");
      try {
        const [stats, logs] = await Promise.all([
          api("/v1/usage/stats?" + params()),
          api("/v1/usage/logs?" + params({limit: els.limit.value, offset: 0}))
        ]);
        if (loadId !== lastLoadId) return;
        const summary = stats.summary || {};
        updateMetrics(summary);
        renderDaily(stats.by_day || []);
        renderModel(stats.by_model || []);
        renderEndpoint(stats.by_endpoint || []);
        renderUpstream(stats.by_upstream_mode || []);
        renderToken(summary);
        renderLogs(logs);
        setStatus("已更新 " + new Date().toLocaleTimeString("zh-CN", {hour12: false}), "");
      } catch (err) {
        setStatus(err.message, "error");
      } finally {
        if (loadId === lastLoadId) setLoading(false);
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
    els.tableSearch.addEventListener("input", renderFilteredLogs);
    window.addEventListener("resize", () => {
      Object.values(charts).forEach(chart => { if (chart) chart.resize(); });
    });
    load();
  </script>
</body>
</html>"""
