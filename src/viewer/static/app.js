"use strict";

const app = document.querySelector("#app");
const liveRegion = document.querySelector("#live-region");

const palette = {
  experiment: "#98a3af", state: "#62c2ca", observation: "#73a7ff",
  risk: "#ee7d82", communication: "#62c2ca", decision: "#ae92f7",
  action: "#d8ae61", validation: "#68c997", execution: "#68c997",
  resource: "#d8ae61", reassessment: "#ae92f7", failure: "#ee7d82", other: "#707b87"
};
const agentColors = ["#73a7ff", "#d8ae61", "#ae92f7", "#68c997", "#ee7d82", "#62c2ca"];

let rootManifest = null;
let currentRun = null;
let comparison = null;
let activeRunIndex = 0;
let selectedEventIndex = 0;
let selectedTime = 0;
let selectedAgent = null;
let visualMode = "truth";
let activeCategories = new Set();
let playTimer = null;
let sweepState = { x: null, y: null, metric: "resolved_conjunctions" };

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const prettyKey = (key) => String(key).replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
const shortId = (value, length = 14) => {
  const text = String(value ?? "—");
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
};
const formatValue = (value) => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return value.length ? value.map(item => typeof item === "object" ? JSON.stringify(item) : item).join(", ") : "none";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};
const classForStatus = (value) => {
  const text = String(value ?? "").toLowerCase();
  if (["resolved", "valid", "executed", "delivered", "accepted", "yes"].some(token => text.includes(token))) return "success";
  if (["reject", "fail", "drop", "unresolved", "invalid", "no"].some(token => text.includes(token))) return "failure";
  return "warning";
};

async function boot() {
  const savedTheme = localStorage.getItem("themis-theme");
  if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  try {
    const response = await fetch("/api/manifest");
    if (!response.ok) throw new Error(`Viewer API returned ${response.status}`);
    rootManifest = await response.json();
    if (rootManifest.kind === "run") mountRun(rootManifest);
    else if (rootManifest.kind === "comparison") mountComparison(rootManifest);
    else if (rootManifest.kind === "sweep") mountSweep(rootManifest);
    else throw new Error(`Unsupported viewer mode: ${rootManifest.kind}`);
  } catch (error) {
    app.innerHTML = `<main class="error-shell"><h1>Unable to load experiment</h1><code>${escapeHtml(error.message)}</code></main>`;
  }
}

function headerTemplate(run, extra = "") {
  const summary = run.summary;
  const network = run.config.network || {};
  return `<header class="topbar">
    <div class="brand-block">
      <div class="wordmark">THEMIS</div><div class="brand-rule"></div>
      <div class="run-heading"><h1>${escapeHtml(summary.experiment || summary.scenario)}</h1>
        <div class="run-subtitle"><span>${escapeHtml(run.benchmark)}</span><span class="dot-separator">·</span><span>${escapeHtml(summary.protocol)}</span><span class="dot-separator">·</span><span>seed ${escapeHtml(summary.seed)}</span><span class="dot-separator">·</span><span>${escapeHtml(formatValue(network.packet_loss_rate * 100 || 0))}% loss</span><span class="dot-separator">·</span><span>${escapeHtml(network.latency_steps || 0)} step latency</span></div>
      </div>
    </div>
    <div class="top-actions">${extra}<span class="panel-kicker" title="Full run identifier">${escapeHtml(shortId(summary.run_id, 22))}</span><button class="icon-button" id="theme-toggle" aria-label="Toggle light and dark theme">◐</button></div>
  </header>`;
}

function themeHandler() {
  document.querySelector("#theme-toggle")?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("themis-theme", next);
    drawTimeline();
    if (currentRun) drawDomain();
    if (rootManifest?.kind === "sweep" && !currentRun) drawSweepChart();
  });
}

function mountComparison(manifest) {
  comparison = manifest;
  activeRunIndex = 0;
  mountRun(manifest.runs[0], true);
}

function mountRun(run, isComparison = comparison !== null) {
  stopPlayback();
  currentRun = run;
  const previousTime = selectedTime;
  selectedEventIndex = 0;
  selectedTime = isComparison ? Math.min(previousTime, maximumTime(run)) : run.events[0]?.time || 0;
  selectedEventIndex = nearestEventIndex(selectedTime);
  selectedAgent = run.agents[0]?.agent_id || null;
  activeCategories = new Set(run.event_categories);
  visualMode = "truth";
  const comparisonBar = comparison ? comparisonModebar() : "";
  const back = rootManifest?.kind === "sweep" ? `<button class="button ghost back-button" id="back-to-sweep">← Sweep</button>` : "";
  app.innerHTML = `<div class="app-shell">${headerTemplate(run, back)}${comparisonBar}
    <main id="workspace" class="content">
      <section class="workspace">
        <article class="panel visual-panel">
          <header class="panel-header"><div><h2 class="panel-title">Benchmark state</h2><span class="panel-kicker" id="visual-time">t = ${selectedTime}</span></div>
            <div class="segmented" aria-label="Visualization mode"><button data-visual="truth" class="active">Physical truth</button><button data-visual="network">Observed communication</button></div>
          </header>
          <div class="visual-stage"><svg id="domain-svg" role="img" aria-label="Spacecraft benchmark state at selected simulation time"></svg><div class="visual-note" id="visual-note">Simplified local-frame geometry · distances in km</div></div>
          <div class="agent-bar" id="agent-bar"></div>
        </article>
        <aside class="panel inspector" aria-label="Selected event inspector"><header class="panel-header"><h2 class="panel-title">Event inspector</h2><span class="panel-kicker" id="event-position"></span></header><div class="inspector-scroll" id="inspector"></div></aside>
      </section>
      ${timelineTemplate(run)}
      <section class="metrics-strip" id="metrics-strip" aria-label="Run outcome metrics"></section>
      <section class="evidence-grid">
        <article class="panel"><header class="panel-header"><h2 class="panel-title">Truth vs agent knowledge</h2><span class="panel-kicker">at selected time</span></header><div class="evidence-body" id="knowledge-panel"></div></article>
        <article class="panel"><header class="panel-header"><h2 class="panel-title">Observed communication</h2><span class="panel-kicker">not network topology</span></header><div class="evidence-body" id="network-panel"></div></article>
        <article class="panel provenance-panel"><header class="panel-header"><h2 class="panel-title">Provenance</h2><span class="panel-kicker">reproducibility</span></header><div class="evidence-body" id="provenance-panel"></div></article>
      </section>
      ${comparison ? comparisonEvidenceTemplate() : ""}
    </main>
  </div>`;
  bindRunInteractions();
  renderRunState();
}

function comparisonModebar() {
  return `<nav class="modebar" aria-label="Compared runs"><div class="run-tabs">${comparison.runs.map((run, index) => `<button class="run-tab ${index === activeRunIndex ? "active" : ""}" data-run-index="${index}">${escapeHtml(run.summary.protocol)} · ${escapeHtml(run.summary.outcome)}</button>`).join("")}</div><div class="comparison-fact">Synchronized at <span class="mono">t = ${selectedTime}</span> · facts aligned by simulation time</div></nav>`;
}

function timelineTemplate(run) {
  return `<section class="panel timeline-panel" aria-label="Synchronized event timeline">
    <header class="panel-header"><h2 class="panel-title">Synchronized timeline</h2><span class="panel-kicker">← → step · space play/pause</span></header>
    <div class="timeline-tools" id="category-filters">${run.event_categories.map(category => `<button class="filter-chip active cat-${category}" data-category="${escapeHtml(category)}"><span class="tiny-mark"></span>${escapeHtml(category)}</button>`).join("")}</div>
    <div class="timeline-wrap"><canvas id="timeline-canvas" role="img" aria-label="Event timeline; use the range input or arrow keys to navigate"></canvas><input class="scrubber" id="time-scrubber" type="range" min="0" max="${maximumTime(run)}" step="1" value="${selectedTime}" aria-label="Selected simulation time"></div>
    <div class="transport"><button id="previous-event" aria-label="Previous event">←</button><button id="play-toggle" aria-label="Play through events">▶</button><button id="next-event" aria-label="Next event">→</button><span class="time-readout" id="time-readout">t = ${selectedTime} · event ${selectedEventIndex + 1}/${run.events.length}</span></div>
  </section>`;
}

function maximumTime(run) {
  return Math.max(0, ...run.events.map(event => Number(event.time) || 0));
}

function bindRunInteractions() {
  themeHandler();
  document.querySelector("#back-to-sweep")?.addEventListener("click", () => { currentRun = null; comparison = null; mountSweep(rootManifest); });
  document.querySelectorAll("[data-run-index]").forEach(button => button.addEventListener("click", () => {
    activeRunIndex = Number(button.dataset.runIndex);
    mountRun(comparison.runs[activeRunIndex], true);
  }));
  document.querySelectorAll("[data-visual]").forEach(button => button.addEventListener("click", () => {
    visualMode = button.dataset.visual;
    document.querySelectorAll("[data-visual]").forEach(item => item.classList.toggle("active", item === button));
    drawDomain();
  }));
  document.querySelectorAll("[data-category]").forEach(button => button.addEventListener("click", () => {
    const category = button.dataset.category;
    if (activeCategories.has(category)) activeCategories.delete(category); else activeCategories.add(category);
    button.classList.toggle("active", activeCategories.has(category));
    selectedEventIndex = nearestVisibleEventIndex(selectedEventIndex);
    selectedTime = currentRun.events[selectedEventIndex]?.time ?? selectedTime;
    renderRunState();
  }));
  document.querySelector("#time-scrubber").addEventListener("input", event => {
    selectedTime = Number(event.target.value);
    selectedEventIndex = nearestEventIndex(selectedTime);
    renderRunState();
  });
  document.querySelector("#previous-event").addEventListener("click", () => stepEvent(-1));
  document.querySelector("#next-event").addEventListener("click", () => stepEvent(1));
  document.querySelector("#play-toggle").addEventListener("click", togglePlayback);
  const canvas = document.querySelector("#timeline-canvas");
  canvas.addEventListener("click", event => {
    const rect = canvas.getBoundingClientRect();
    const visible = visibleEvents();
    if (!visible.length) return;
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left - 20) / Math.max(1, rect.width - 40)));
    const target = ratio * maximumTime(currentRun);
    const chosen = visible.reduce((best, candidate) => Math.abs(candidate.time - target) < Math.abs(best.time - target) ? candidate : best);
    selectEventById(chosen.event_id);
  });
  window.onkeydown = event => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    if (event.key === "ArrowLeft") { event.preventDefault(); stepEvent(-1); }
    if (event.key === "ArrowRight") { event.preventDefault(); stepEvent(1); }
    if (event.key === " ") { event.preventDefault(); togglePlayback(); }
  };
}

function visibleEvents() { return currentRun.events.filter(event => activeCategories.has(event.category)); }
function nearestEventIndex(time) {
  if (!currentRun.events.length) return 0;
  let best = 0;
  currentRun.events.forEach((event, index) => {
    if (event.time <= time) best = index;
  });
  return best;
}
function nearestVisibleEventIndex(start) {
  if (activeCategories.has(currentRun.events[start]?.category)) return start;
  for (let offset = 1; offset < currentRun.events.length; offset++) {
    if (activeCategories.has(currentRun.events[start + offset]?.category)) return start + offset;
    if (activeCategories.has(currentRun.events[start - offset]?.category)) return start - offset;
  }
  return start;
}
function stepEvent(direction) {
  stopPlayback();
  let index = selectedEventIndex + direction;
  while (index >= 0 && index < currentRun.events.length && !activeCategories.has(currentRun.events[index].category)) index += direction;
  if (index < 0 || index >= currentRun.events.length) return;
  selectedEventIndex = index;
  selectedTime = currentRun.events[index].time;
  renderRunState();
}
function togglePlayback() {
  if (playTimer) { stopPlayback(); return; }
  document.querySelector("#play-toggle").textContent = "Ⅱ";
  playTimer = window.setInterval(() => {
    const before = selectedEventIndex;
    let index = before + 1;
    while (index < currentRun.events.length && !activeCategories.has(currentRun.events[index].category)) index++;
    if (index >= currentRun.events.length) { stopPlayback(); return; }
    selectedEventIndex = index; selectedTime = currentRun.events[index].time; renderRunState();
  }, 650);
}
function stopPlayback() {
  if (playTimer) window.clearInterval(playTimer);
  playTimer = null;
  const button = document.querySelector("#play-toggle");
  if (button) button.textContent = "▶";
}
function selectEventById(eventId) {
  const index = currentRun.events.findIndex(event => event.event_id === eventId);
  if (index < 0) return;
  selectedEventIndex = index; selectedTime = currentRun.events[index].time;
  renderRunState();
}

function renderRunState() {
  if (!currentRun?.events.length) return;
  const event = currentRun.events[selectedEventIndex];
  selectedTime = event.time;
  const scrubber = document.querySelector("#time-scrubber");
  if (scrubber) scrubber.value = selectedTime;
  document.querySelector("#time-readout").textContent = `t = ${selectedTime} · event ${selectedEventIndex + 1}/${currentRun.events.length}`;
  document.querySelector("#visual-time").textContent = `t = ${selectedTime}`;
  document.querySelector("#event-position").textContent = `#${event.sequence} of ${currentRun.events.length}`;
  renderAgents(); renderInspector(); renderMetrics(); renderKnowledge(); renderNetworkTable(); renderProvenance();
  drawTimeline(); drawDomain();
  if (comparison) renderComparisonEvidence();
  liveRegion.textContent = `${event.title}, simulation time ${event.time}`;
}

function renderAgents() {
  const bar = document.querySelector("#agent-bar");
  bar.innerHTML = `<span class="agent-bar-label">Inspect agent</span>${currentRun.agents.map(agent => `<button class="chip ${selectedAgent === agent.agent_id ? "active" : ""}" data-agent="${escapeHtml(agent.agent_id)}">${escapeHtml(agent.agent_id)}</button>`).join("")}`;
  bar.querySelectorAll("[data-agent]").forEach(button => button.addEventListener("click", () => { selectedAgent = button.dataset.agent; renderAgents(); renderKnowledge(); drawDomain(); }));
}

const detailPriority = ["message_id", "message_type", "sender_id", "recipient_id", "sent_time", "delivered_time", "latency_steps", "drop_reason", "protocol", "rationale", "agent_id", "risk_event_id", "maneuver_id", "valid", "reason_code", "explanation", "delta_v_magnitude_km_per_step", "delta_v_vector_km_per_step", "estimated_fuel_cost", "expected_post_maneuver_separation_km", "outcome", "pre_minimum_distance_km", "post_minimum_distance_km", "resource", "before", "after", "change"];
function flattenedDisplayPayload(event) {
  const payload = event.payload;
  const maneuver = payload.maneuver && typeof payload.maneuver === "object" ? payload.maneuver : {};
  const combined = {...maneuver, ...payload};
  delete combined.maneuver; delete combined.metrics; delete combined.trajectories; delete combined.before; delete combined.after; delete combined.inputs;
  const keys = [...detailPriority.filter(key => combined[key] !== undefined), ...Object.keys(combined).filter(key => !detailPriority.includes(key)).slice(0, 5)];
  return keys.map(key => [key, combined[key]]);
}
function renderInspector() {
  const event = currentRun.events[selectedEventIndex];
  const pairs = flattenedDisplayPayload(event);
  const related = [event, ...event.related_event_ids.map(id => currentRun.events.find(item => item.event_id === id)).filter(Boolean)]
    .sort((a, b) => a.sequence - b.sequence)
    .filter(item => ["PROTOCOL_DECISION", "MANEUVER_PROPOSED", "MANEUVER_VALIDATED", "MANEUVER_REJECTED", "MANEUVER_EXECUTED", "MANEUVER_FAILED", "TRAJECTORY_REPROPAGATED", "RISK_REASSESSED", "CONJUNCTION_RESOLVED", "MESSAGE_SENT", "MESSAGE_DELIVERED", "MESSAGE_DROPPED"].includes(item.event_type));
  const refs = Object.entries(event.references || {});
  document.querySelector("#inspector").innerHTML = `<section class="event-summary"><div class="event-category cat-${escapeHtml(event.category)}"><span class="category-mark"></span>${escapeHtml(event.category)}</div><h2>${escapeHtml(event.title)}</h2><div class="event-meta"><span>t = ${escapeHtml(event.time)}</span><span>seq ${escapeHtml(event.sequence)}</span>${event.actor ? `<span>${escapeHtml(event.actor)}</span>` : ""}</div></section>
    <section class="detail-section"><h3 class="section-label">Structured facts</h3><dl class="detail-grid">${pairs.length ? pairs.map(([key, value]) => `<dt>${escapeHtml(prettyKey(key))}</dt><dd class="${["valid", "outcome", "reason_code", "drop_reason"].includes(key) ? `status-value ${classForStatus(value)}` : ""}">${escapeHtml(formatValue(value))}</dd>`).join("") : `<dt>Event</dt><dd>${escapeHtml(event.event_type)}</dd>`}</dl></section>
    ${refs.length ? `<section class="detail-section"><h3 class="section-label">Causal references</h3><dl class="detail-grid">${refs.map(([key,value]) => `<dt>${escapeHtml(prettyKey(key))}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl></section>` : ""}
    ${related.length > 1 ? `<section class="detail-section"><h3 class="section-label">Related causal chain</h3><div class="causal-chain">${related.map(item => `<button class="causal-link ${item.event_id === event.event_id ? "active" : ""}" data-related="${escapeHtml(item.event_id)}"><span class="causal-time">t ${escapeHtml(item.time)}</span><span class="causal-kind">${escapeHtml(item.title)}</span><span class="causal-seq">#${escapeHtml(item.sequence)}</span></button>`).join("")}</div></section>` : ""}
    <section class="detail-section"><details class="raw"><summary>Raw event JSON</summary><pre>${escapeHtml(JSON.stringify(event, null, 2))}</pre></details></section>`;
  document.querySelectorAll("[data-related]").forEach(button => button.addEventListener("click", () => selectEventById(button.dataset.related)));
}

function metricCard(label, value, note = "") { return `<div class="metric"><span class="metric-label">${escapeHtml(label)}</span><strong class="metric-value">${escapeHtml(formatValue(value))}</strong><span class="metric-note">${escapeHtml(note)}</span></div>`; }
function renderMetrics() {
  const metrics = currentRun.summary.metrics;
  const minSep = metrics.minimum_post_maneuver_separation_km ?? metrics.minimum_pre_maneuver_separation_km;
  document.querySelector("#metrics-strip").innerHTML = [
    metricCard("Outcome", currentRun.summary.outcome, "simulation result"),
    metricCard("Minimum separation", minSep === null || minSep === undefined ? "—" : `${formatValue(minSep)} km`, "derived over horizon"),
    metricCard("Messages", `${metrics.messages_delivered} / ${metrics.messages_sent}`, `${metrics.messages_dropped} dropped`),
    metricCard("Actions", metrics.maneuvers_executed, `${metrics.maneuvers_rejected} rejected`),
    metricCard("Δv proxy", `${formatValue(metrics.total_delta_v_used_km_per_step)} km/step`, "simulator proxy"),
    metricCard("Unresolved", metrics.unresolved_conjunctions, `${metrics.original_conjunctions} initial conflict(s)`)
  ].join("");
}

function activeTruthRisks() {
  const detected = new Map();
  for (const event of currentRun.events) {
    if (event.time > selectedTime || (event.time === selectedTime && event.sequence > currentRun.events[selectedEventIndex].sequence)) break;
    const riskId = event.references?.risk_event_id || event.payload?.risk_event_id;
    if (event.event_type === "CONJUNCTION_DETECTED" && riskId) detected.set(riskId, {status: "OPEN", ...event.payload});
    if (event.event_type === "CONJUNCTION_RESOLVED" && riskId && detected.has(riskId)) detected.get(riskId).status = "RESOLVED";
  }
  return [...detected.values()];
}
function agentSnapshot(agentId) {
  const agent = currentRun.agents.find(item => item.agent_id === agentId);
  if (!agent) return null;
  const sequence = currentRun.events[selectedEventIndex]?.sequence ?? Infinity;
  return agent.snapshots.filter(snapshot => snapshot.time < selectedTime || (snapshot.time === selectedTime && snapshot.sequence <= sequence)).at(-1) || agent.snapshots[0] || null;
}
function renderKnowledge() {
  const truth = activeTruthRisks();
  const snapshot = agentSnapshot(selectedAgent);
  const known = snapshot?.known_risk_event_ids || [];
  document.querySelector("#knowledge-panel").innerHTML = `<div class="truth-belief">
    <div class="state-box truth"><h4>Global simulation truth</h4>${truth.length ? truth.map(risk => `<p><span class="status-dot ${risk.status === "RESOLVED" ? "delivered" : "dropped"}"></span><span class="mono">${escapeHtml(risk.risk_event_id)}</span><br>${escapeHtml(risk.satellite_a)} ↔ ${escapeHtml(risk.satellite_b)} · ${escapeHtml(formatValue(risk.distance_km))} km · ${escapeHtml(risk.status)}</p>`).join("") : `<p>No modeled risks at this time.</p>`}</div>
    <div class="state-box belief"><h4>${escapeHtml(selectedAgent || "Agent")} local belief</h4>${known.length ? known.map(id => `<p><span class="status-dot delivered"></span>knows <span class="mono">${escapeHtml(id)}</span></p>`).join("") : `<p>No delivered risk information recorded.</p>`}${snapshot?.fuel_budget !== undefined ? `<p>Fuel proxy: <span class="mono">${escapeHtml(formatValue(snapshot.fuel_budget))}</span></p>` : ""}<p class="panel-kicker">${escapeHtml(snapshot?.source || "No snapshot available")}</p></div>
  </div>`;
}

function messageEvent(message) {
  const preferred = message.status === "dropped" ? "MESSAGE_DROPPED" : message.status === "late" ? "MESSAGE_DELAYED_BEYOND_USEFULNESS" : "MESSAGE_DELIVERED";
  const id = message.events.map(eventId => currentRun.events.find(event => event.event_id === eventId)).find(event => event?.event_type === preferred)?.event_id || message.events[0];
  return id;
}
function renderNetworkTable() {
  const visible = currentRun.messages.filter(message => (message.sent_time ?? 0) <= selectedTime);
  document.querySelector("#network-panel").innerHTML = visible.length ? `<table class="message-table"><thead><tr><th>Status</th><th>From → to</th><th>Type</th><th>Latency</th></tr></thead><tbody>${visible.map(message => `<tr class="message-row" data-message-event="${escapeHtml(messageEvent(message))}"><td><span class="status-dot ${escapeHtml(message.status)}"></span>${escapeHtml(message.status)}</td><td>${escapeHtml(shortId(message.sender_id, 8))} → ${escapeHtml(shortId(message.recipient_id, 8))}</td><td>${escapeHtml(message.message_type || "—")}</td><td>${escapeHtml(message.latency_steps ?? (message.status === "dropped" ? "—" : "pending"))}</td></tr>`).join("")}</tbody></table>` : `<div class="empty-state">No messages sent by this time.</div>`;
  document.querySelectorAll("[data-message-event]").forEach(row => row.addEventListener("click", () => selectEventById(row.dataset.messageEvent)));
}

function renderProvenance() {
  const meta = currentRun.metadata || {};
  document.querySelector("#provenance-panel").innerHTML = `<div class="copy-row"><code title="${escapeHtml(currentRun.reproduction_command)}">${escapeHtml(currentRun.reproduction_command)}</code><button class="button" id="copy-command">Copy</button></div>
    <ul class="provenance-list"><li><span>Run ID</span><span title="${escapeHtml(currentRun.summary.run_id)}">${escapeHtml(currentRun.summary.run_id)}</span></li><li><span>Artifact schema</span><span>v${escapeHtml(currentRun.artifact_schema_version)}</span></li><li><span>Themis version</span><span>${escapeHtml(meta.themis_version || "legacy / unknown")}</span></li><li><span>Git commit</span><span title="${escapeHtml(meta.git_commit || "not recorded")}">${escapeHtml(shortId(meta.git_commit || "not recorded", 14))}</span></li><li><span>Seed</span><span>${escapeHtml(currentRun.summary.seed)}</span></li></ul>
    <details class="raw"><summary>Resolved configuration</summary><pre>${escapeHtml(currentRun.config_text)}</pre></details>`;
  document.querySelector("#copy-command").addEventListener("click", async event => {
    await navigator.clipboard.writeText(currentRun.reproduction_command);
    event.target.textContent = "Copied";
    window.setTimeout(() => event.target.textContent = "Copy", 1200);
  });
}

function canvasTheme() {
  const css = getComputedStyle(document.documentElement);
  return { text: css.getPropertyValue("--text-2").trim(), faint: css.getPropertyValue("--border").trim(), surface: css.getPropertyValue("--surface-1").trim(), accent: css.getPropertyValue("--accent").trim() };
}
function setupCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width * ratio)); canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const context = canvas.getContext("2d"); context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return {context, width: rect.width, height: rect.height};
}
function drawTimeline() {
  const canvas = document.querySelector("#timeline-canvas");
  if (!canvas || !currentRun) return;
  const {context, width, height} = setupCanvas(canvas); const theme = canvasTheme();
  context.clearRect(0, 0, width, height); context.strokeStyle = theme.faint; context.lineWidth = 1;
  const left = 20, right = width - 20, axisY = 31, max = Math.max(1, maximumTime(currentRun));
  context.beginPath(); context.moveTo(left, axisY); context.lineTo(right, axisY); context.stroke();
  context.font = "10px ui-monospace, monospace"; context.fillStyle = theme.text; context.textAlign = "center";
  for (let time = 0; time <= max; time++) { const x = left + (right-left) * time / max; context.fillRect(x, axisY-3, 1, 7); context.fillText(`t${time}`, x, 53); }
  const visible = visibleEvents(); const groups = new Map();
  visible.forEach(event => { const list = groups.get(event.time) || []; list.push(event); groups.set(event.time, list); });
  visible.forEach(event => {
    const list = groups.get(event.time); const slot = list.indexOf(event); const x = left + (right-left) * event.time / max + (slot - (list.length-1)/2) * 7; const y = axisY;
    context.fillStyle = palette[event.category] || palette.other; context.strokeStyle = palette[event.category] || palette.other;
    const selected = event.event_id === currentRun.events[selectedEventIndex].event_id;
    if (event.category === "failure") { context.lineWidth = selected ? 3 : 2; context.beginPath(); context.moveTo(x-4,y-4); context.lineTo(x+4,y+4); context.moveTo(x+4,y-4); context.lineTo(x-4,y+4); context.stroke(); }
    else if (event.category === "action" || event.category === "decision") { context.beginPath(); context.moveTo(x,y-5); context.lineTo(x+5,y+4); context.lineTo(x-5,y+4); context.closePath(); context.fill(); if(selected){context.strokeStyle=theme.text;context.stroke();} }
    else { context.beginPath(); context.arc(x,y,selected?5:3.5,0,Math.PI*2); context.fill(); if(selected){context.strokeStyle=theme.text;context.lineWidth=1.5;context.stroke();} }
  });
  const playX = left + (right-left) * selectedTime / max; context.strokeStyle = theme.accent; context.lineWidth = 1; context.beginPath(); context.moveTo(playX, 4); context.lineTo(playX, 47); context.stroke();
}

function initialTrajectories() {
  return currentRun.events.find(event => event.event_type === "STATE_UPDATED" && event.payload.trajectories)?.payload.trajectories || {};
}
function trajectoriesAt(time) {
  const trajectories = structuredClone(initialTrajectories());
  currentRun.events.filter(event => event.event_type === "TRAJECTORY_REPROPAGATED" && event.time <= time).forEach(event => { trajectories[event.payload.agent_id] = event.payload.trajectory; });
  return trajectories;
}
function positionAt(trajectory, time) {
  const elapsed = time - Number(trajectory.reference_time || 0); const p = trajectory.position_km || [0,0,0]; const v = trajectory.velocity_km_per_step || [0,0,0];
  return [0,1,2].map(index => Number(p[index] || 0) + Number(v[index] || 0) * elapsed);
}
function allSamplePositions() {
  const ids = Object.keys(initialTrajectories()); const max = maximumTime(currentRun); const points = [];
  const interval = Math.max(1, Math.ceil(max / 240));
  const times = new Set([0, max, selectedTime, ...currentRun.events.map(event => event.time)]);
  for (let time=0; time<=max; time+=interval) times.add(time);
  [...times].sort((a,b)=>a-b).forEach(time => { const trajectories = trajectoriesAt(time); ids.forEach(id => points.push({id,time,position:positionAt(trajectories[id],time)})); });
  return points;
}
function svgElement(name, attributes = {}, text = "") {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key,value]) => element.setAttribute(key, value));
  if (text) element.textContent = text;
  return element;
}
function drawDomain() {
  const svg = document.querySelector("#domain-svg"); if (!svg) return;
  svg.replaceChildren(); svg.setAttribute("viewBox", "0 0 900 387");
  if (visualMode === "network") { drawNetworkGraph(svg); document.querySelector("#visual-note").textContent = "Observed message traffic only · no persistent topology is modeled"; return; }
  document.querySelector("#visual-note").textContent = "Simplified local-frame geometry · positions and thresholds in km";
  const theme = canvasTheme(); const points = allSamplePositions(); if (!points.length) return;
  const xs = points.map(item=>item.position[0]), ys = points.map(item=>item.position[1]);
  const risks = currentRun.events.filter(event=>event.event_type === "CONJUNCTION_DETECTED").map(event=>event.payload);
  const threshold = Math.max(...risks.map(r=>Number(r.threshold_km)||0), 0);
  let minX=Math.min(...xs)-threshold*.35-10,maxX=Math.max(...xs)+threshold*.35+10,minY=Math.min(...ys)-Math.max(threshold,40),maxY=Math.max(...ys)+Math.max(threshold,40);
  if(maxX-minX<100){minX-=50;maxX+=50;} if(maxY-minY<100){minY-=50;maxY+=50;}
  const left=64,right=870,top=24,bottom=342; const sx=x=>left+(x-minX)/(maxX-minX)*(right-left); const sy=y=>bottom-(y-minY)/(maxY-minY)*(bottom-top);
  const grid=svgElement("g",{"aria-hidden":"true"});
  for(let i=0;i<=5;i++){const x=left+(right-left)*i/5;const value=minX+(maxX-minX)*i/5;grid.append(svgElement("line",{x1:x,y1:top,x2:x,y2:bottom,stroke:theme.faint,"stroke-width":"1"}));grid.append(svgElement("text",{x,y:368,fill:theme.text,"font-size":"10","text-anchor":"middle","font-family":"monospace"},value.toFixed(0)));}
  for(let i=0;i<=4;i++){const y=top+(bottom-top)*i/4;grid.append(svgElement("line",{x1:left,y1:y,x2:right,y2:y,stroke:theme.faint,"stroke-width":"1"}));}
  grid.append(svgElement("text",{x:467,y:382,fill:theme.text,"font-size":"10","text-anchor":"middle"},"LOCAL X (km)")); svg.append(grid);
  const ids=Object.keys(initialTrajectories()).sort(); ids.forEach((id,index)=>{const pathPoints=points.filter(item=>item.id===id).map(item=>`${sx(item.position[0])},${sy(item.position[1])}`).join(" ");svg.append(svgElement("polyline",{points:pathPoints,fill:"none",stroke:agentColors[index%agentColors.length],"stroke-width":selectedAgent===id?"3":"1.5","stroke-opacity":selectedAgent===id?"1":".65"}));});
  const trajectories=trajectoriesAt(selectedTime); const current={}; ids.forEach((id,index)=>{const pos=positionAt(trajectories[id],selectedTime);current[id]=pos;const color=agentColors[index%agentColors.length];svg.append(svgElement("circle",{cx:sx(pos[0]),cy:sy(pos[1]),r:selectedAgent===id?"7":"5",fill:color,stroke:theme.surface,"stroke-width":"2"}));svg.append(svgElement("text",{x:sx(pos[0])+9,y:sy(pos[1])-9,fill:theme.text,"font-size":"11","font-family":"monospace"},id));});
  risks.forEach(risk=>{const a=current[risk.satellite_a],b=current[risk.satellite_b];if(!a||!b)return;const distance=Math.sqrt(a.reduce((sum,value,index)=>sum+(value-b[index])**2,0));svg.append(svgElement("line",{x1:sx(a[0]),y1:sy(a[1]),x2:sx(b[0]),y2:sy(b[1]),stroke:palette.risk,"stroke-width":"1","stroke-dasharray":"4 4"}));const midX=(sx(a[0])+sx(b[0]))/2,midY=(sy(a[1])+sy(b[1]))/2;svg.append(svgElement("text",{x:midX,y:midY-7,fill:palette.risk,"font-size":"10","text-anchor":"middle","font-family":"monospace"},`${distance.toFixed(1)} km`));});
  const proposal=currentRun.events.slice(0,selectedEventIndex+1).reverse().find(event=>event.event_type==="MANEUVER_PROPOSED")?.payload;if(proposal&&current[proposal.agent_id]){const pos=current[proposal.agent_id],dv=proposal.delta_v_vector_km_per_step||[0,0,0],mag=Math.max(1,Math.hypot(dv[0],dv[1]));const length=54;const x1=sx(pos[0]),y1=sy(pos[1]),x2=x1+dv[0]/mag*length,y2=y1-dv[1]/mag*length;svg.append(svgElement("line",{x1,y1,x2,y2,stroke:palette.action,"stroke-width":"2"}));svg.append(svgElement("circle",{cx:x2,cy:y2,r:"3",fill:palette.action}));svg.append(svgElement("text",{x:x2+7,y:y2+4,fill:palette.action,"font-size":"10"},"proposed Δv"));}
}

function drawNetworkGraph(svg) {
  const theme=canvasTheme();const agents=currentRun.agents.map(agent=>agent.agent_id);const nodes=["GROUND_TRUTH_MONITOR",...agents];const positions={};nodes.forEach((id,index)=>{const x=110+(680*(index/(Math.max(1,nodes.length-1))));const y=id==="GROUND_TRUTH_MONITOR"?90:260;positions[id]=[x,y];svg.append(svgElement("circle",{cx:x,cy:y,r:id===selectedAgent?"25":"20",fill:theme.surface,stroke:id===selectedAgent?theme.accent:theme.faint,"stroke-width":"2"}));svg.append(svgElement("text",{x,y:y+40,fill:theme.text,"font-size":"11","text-anchor":"middle","font-family":"monospace"},id.replace("GROUND_TRUTH_MONITOR","RISK MONITOR")));});
  currentRun.messages.filter(message=>(message.sent_time??0)<=selectedTime).forEach(message=>{const from=positions[message.sender_id],to=positions[message.recipient_id];if(!from||!to)return;const color=message.status==="dropped"?palette.failure:message.status==="delivered"?palette.execution:palette.communication;svg.append(svgElement("line",{x1:from[0],y1:from[1],x2:to[0],y2:to[1],stroke:color,"stroke-width":"2","stroke-dasharray":message.status==="dropped"?"6 5":"none","stroke-opacity":".8"}));const mx=(from[0]+to[0])/2,my=(from[1]+to[1])/2;svg.append(svgElement("text",{x:mx,y:my-8,fill:color,"font-size":"10","text-anchor":"middle","font-family":"monospace"},message.status==="dropped"?"× dropped":`${message.latency_steps??"…"} step`));});
}

function comparisonEvidenceTemplate() {
  return `<section class="panel" id="comparison-evidence"><header class="panel-header"><h2 class="panel-title">Run divergence</h2><span class="panel-kicker">reported facts, not causal claims</span></header><div id="comparison-body"></div></section>`;
}
function eventsAt(run,time){return run.events.filter(event=>event.time===time).map(event=>event.title);}
function comparisonFactSummary() {
  const [left,right]=comparison.runs;const leftMessages=left.messages.reduce((acc,item)=>({...acc,[item.message_id]:item.status}),{});const rightMessages=right.messages.reduce((acc,item)=>({...acc,[item.message_id]:item.status}),{});const messageDiff=Object.keys({...leftMessages,...rightMessages}).filter(key=>leftMessages[key]!==rightMessages[key]).length;
  return `${comparison.config_differences.length} configuration difference(s) · ${comparison.metric_differences.length} metric difference(s) · ${messageDiff} message-status difference(s)`;
}
function renderComparisonEvidence(){const [left,right]=comparison.runs;const configRows=comparison.config_differences.slice(0,12).map(diff=>`<tr><td>${escapeHtml(diff.field)}</td><td>${escapeHtml(formatValue(diff.left))}</td><td>${escapeHtml(formatValue(diff.right))}</td></tr>`).join("");const metricRows=comparison.metric_differences.filter(diff=>["resolved_conjunctions","unresolved_conjunctions","messages_dropped","messages_delivered","maneuvers_executed","maneuvers_rejected","total_delta_v_used_km_per_step"].includes(diff.metric)).map(diff=>`<tr><td>${escapeHtml(prettyKey(diff.metric))}</td><td>${escapeHtml(formatValue(diff.left))}</td><td>${escapeHtml(formatValue(diff.right))}</td><td>${escapeHtml(diff.delta===null?"—":formatValue(diff.delta))}</td></tr>`).join("");document.querySelector("#comparison-body").innerHTML=`<div class="comparison-overview"><div class="compare-run"><h3>${escapeHtml(left.summary.protocol)}</h3><div class="outcome ${classForStatus(left.summary.outcome)}">${escapeHtml(left.summary.outcome)}</div><p class="panel-kicker">At t=${selectedTime}: ${escapeHtml(eventsAt(left,selectedTime).join(" · ")||"no event")}</p></div><div class="compare-run"><h3>${escapeHtml(right.summary.protocol)}</h3><div class="outcome ${classForStatus(right.summary.outcome)}">${escapeHtml(right.summary.outcome)}</div><p class="panel-kicker">At t=${selectedTime}: ${escapeHtml(eventsAt(right,selectedTime).join(" · ")||"no event")}</p></div></div><div class="difference-columns"><div><h3 class="section-label">Configuration differences</h3><table class="diff-table"><thead><tr><th>Field</th><th>${escapeHtml(left.summary.protocol)}</th><th>${escapeHtml(right.summary.protocol)}</th></tr></thead><tbody>${configRows||"<tr><td colspan=3>None</td></tr>"}</tbody></table></div><div><h3 class="section-label">Metric differences</h3><table class="diff-table"><thead><tr><th>Metric</th><th>A</th><th>B</th><th>Δ B−A</th></tr></thead><tbody>${metricRows||"<tr><td colspan=4>None</td></tr>"}</tbody></table></div></div>`;document.querySelector(".comparison-fact").innerHTML=`Synchronized at <span class="mono">t = ${selectedTime}</span> · ${escapeHtml(comparisonFactSummary())}`;}

function mountSweep(manifest) {
  stopPlayback(); currentRun=null; comparison=null; rootManifest=manifest;
  const numericMetrics=["resolved_conjunctions","unresolved_conjunctions","messages_dropped","messages_delivered","maneuvers_executed","maneuvers_rejected","total_delta_v_used_km_per_step"];
  sweepState.x=manifest.parameters.find(parameter=>parameter.includes("packet_loss"))||manifest.parameters[0]||null;
  sweepState.y=manifest.parameters.find(parameter=>parameter.includes("latency"))||manifest.parameters.find(parameter=>parameter!==sweepState.x)||sweepState.x;
  app.innerHTML=`<div class="app-shell"><header class="topbar"><div class="brand-block"><div class="wordmark">THEMIS</div><div class="brand-rule"></div><div class="run-heading"><h1>Sweep analysis</h1><div class="run-subtitle"><span>${manifest.records.length} experiment cells</span><span class="dot-separator">·</span><span>artifact-driven</span></div></div></div><div class="top-actions"><span class="panel-kicker">${escapeHtml(shortId(manifest.path,35))}</span><button class="icon-button" id="theme-toggle" aria-label="Toggle theme">◐</button></div></header><main class="sweep-shell"><section class="sweep-hero"><div><h1>Completed parameter sweep</h1><p>Explore aggregate outcomes, then open the underlying causal trace.</p></div><div class="sweep-controls"><div class="field"><label for="x-param">X parameter</label><select id="x-param">${manifest.parameters.map(p=>`<option ${p===sweepState.x?"selected":""}>${escapeHtml(p)}</option>`).join("")}</select></div><div class="field"><label for="y-param">Y parameter</label><select id="y-param">${manifest.parameters.map(p=>`<option ${p===sweepState.y?"selected":""}>${escapeHtml(p)}</option>`).join("")}</select></div><div class="field"><label for="metric-select">Metric</label><select id="metric-select">${numericMetrics.map(m=>`<option>${escapeHtml(m)}</option>`).join("")}</select></div></div></section><section class="sweep-grid"><article class="panel"><header class="panel-header"><h2 class="panel-title">Parameter response</h2><span class="panel-kicker" id="chart-caption"></span></header><div class="chart-area"><canvas id="sweep-canvas" role="img" aria-label="Sweep parameter heatmap"></canvas></div></article><article class="panel"><header class="panel-header"><h2 class="panel-title">Outcome distribution</h2><span class="panel-kicker">across all cells</span></header><div class="outcome-bars" id="outcome-bars"></div></article></section><section class="panel"><header class="panel-header"><h2 class="panel-title">Experiment cells</h2><span class="panel-kicker">click a run to inspect its trace</span></header><div class="sweep-table-wrap" id="sweep-table"></div></section></main></div>`;
  themeHandler();["x-param","y-param","metric-select"].forEach(id=>document.querySelector(`#${id}`).addEventListener("change",()=>{sweepState.x=document.querySelector("#x-param").value;sweepState.y=document.querySelector("#y-param").value;sweepState.metric=document.querySelector("#metric-select").value;drawSweepChart();renderSweepTable();}));
  renderSweepOutcomes();renderSweepTable();drawSweepChart();window.onkeydown=null;
}
function uniqueValues(parameter){return [...new Set(rootManifest.records.map(record=>String(record[parameter])))].sort((a,b)=>Number(a)-Number(b)||a.localeCompare(b));}
function renderSweepOutcomes(){const counts={};rootManifest.records.forEach(record=>counts[record.outcome||record.status]=(counts[record.outcome||record.status]||0)+1);const max=Math.max(1,...Object.values(counts));document.querySelector("#outcome-bars").innerHTML=Object.entries(counts).map(([key,value])=>`<div class="bar-row"><div class="bar-head"><span>${escapeHtml(key)}</span><span class="mono">${value}</span></div><div class="bar-track"><div class="bar-fill ${escapeHtml(key)}" data-bar-width="${value/max*100}"></div></div></div>`).join("");document.querySelectorAll("[data-bar-width]").forEach(bar=>bar.style.width=`${bar.dataset.barWidth}%`);}
function renderSweepTable(){const records=rootManifest.records.slice(0,200);const params=[...new Set([sweepState.x,sweepState.y].filter(Boolean))];document.querySelector("#sweep-table").innerHTML=`<table class="sweep-table"><thead><tr><th>Run</th>${params.map(p=>`<th>${escapeHtml(p)}</th>`).join("")}<th>${escapeHtml(sweepState.metric)}</th><th>Outcome</th></tr></thead><tbody>${records.map(record=>`<tr><td>${record.run_available?`<button class="open-run" data-run-path="${escapeHtml(record.run_path)}">${escapeHtml(shortId(record.run_id,18))}</button>`:escapeHtml(shortId(record.run_id||"failed",18))}</td>${params.map(p=>`<td>${escapeHtml(formatValue(record[p]))}</td>`).join("")}<td>${escapeHtml(formatValue(record[sweepState.metric]))}</td><td class="${classForStatus(record.outcome)}">${escapeHtml(record.outcome||record.status)}</td></tr>`).join("")}</tbody></table>`;document.querySelectorAll("[data-run-path]").forEach(button=>button.addEventListener("click",async()=>{button.textContent="Loading…";const response=await fetch(`/api/run?path=${encodeURIComponent(button.dataset.runPath)}`);const run=await response.json();if(!response.ok){alert(run.error);return;}mountRun(run);}));}
function drawSweepChart(){const canvas=document.querySelector("#sweep-canvas");if(!canvas)return;const {context,width,height}=setupCanvas(canvas),theme=canvasTheme(),xs=uniqueValues(sweepState.x),ys=uniqueValues(sweepState.y);context.clearRect(0,0,width,height);const left=78,top=32,right=width-24,bottom=height-58,cellW=(right-left)/Math.max(1,xs.length),cellH=(bottom-top)/Math.max(1,ys.length);const cells=[];ys.forEach((y,yi)=>xs.forEach((x,xi)=>{const records=rootManifest.records.filter(r=>String(r[sweepState.x])===x&&String(r[sweepState.y])===y);const nums=records.map(r=>Number(r[sweepState.metric])).filter(Number.isFinite);const value=nums.length?nums.reduce((a,b)=>a+b,0)/nums.length:null;cells.push({x,y,xi,yi,value,count:nums.length});}));const values=cells.map(c=>c.value).filter(v=>v!==null),min=Math.min(...values,0),max=Math.max(...values,1);cells.forEach(cell=>{const ratio=cell.value===null?0:(cell.value-min)/Math.max(.0001,max-min);context.fillStyle=cell.value===null?theme.surface:`rgba(115,167,255,${.12+ratio*.78})`;context.fillRect(left+cell.xi*cellW+1,top+cell.yi*cellH+1,cellW-2,cellH-2);context.fillStyle=ratio>.58?"#07101d":theme.text;context.font="11px ui-monospace, monospace";context.textAlign="center";context.fillText(cell.value===null?"—":formatValue(cell.value),left+(cell.xi+.5)*cellW,top+(cell.yi+.5)*cellH+4);});context.fillStyle=theme.text;context.font="10px ui-monospace, monospace";xs.forEach((x,i)=>context.fillText(x,left+(i+.5)*cellW,bottom+20));context.textAlign="right";ys.forEach((y,i)=>context.fillText(y,left-9,top+(i+.5)*cellH+4));context.textAlign="center";context.fillText(sweepState.x,(left+right)/2,height-12);context.save();context.translate(15,(top+bottom)/2);context.rotate(-Math.PI/2);context.fillText(sweepState.y,0,0);context.restore();document.querySelector("#chart-caption").textContent=`mean ${sweepState.metric} across seeds`;}

window.addEventListener("resize",()=>{if(currentRun){drawTimeline();drawDomain();}else if(rootManifest?.kind==="sweep")drawSweepChart();});
boot();
