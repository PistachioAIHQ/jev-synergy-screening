/** UI v2 — 200-block grid, live parallel hybrid Jev classify, optional cached replay. */
const BIO_ACC = 96.37;
const BIO_F1 = 90.85;
const AMBER_CONF = 0.55; // confidence < this → amber (agree or disagree)
const DEFAULT_WORKERS = 8;
const NOUL_FIELDS = [
  ["has_random_allocation", "d-noul-rand"],
  ["parallel_intervention_arms", "d-noul-par"],
  ["is_cluster_random", "d-noul-clu"],
  ["is_secondary_or_nested_only", "d-noul-sec"],
  ["is_protocol_or_single_arm", "d-noul-prot"],
];

const $ = (id) => document.getElementById(id);

let pubs = [];
let selectedIdx = null;
let running = false;
let stopFlag = false;
let mode = "idle";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function blockClass(pub) {
  if (pub.state === "running") return "running";
  if (pub.state === "error") return "error";
  if (pub.state !== "done" || !pub.result) return "";
  const conf = Number(pub.result.confidence);
  const agree = pub.result.pred === pub.gold;
  if (!Number.isFinite(conf) || conf < AMBER_CONF) return "amber";
  return agree ? "agree" : "disagree";
}

function renderGrid() {
  const grid = $("grid");
  grid.innerHTML = "";
  const frag = document.createDocumentFragment();
  for (const pub of pubs) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = `block ${blockClass(pub)}${selectedIdx === pub.demo_idx ? " selected" : ""}`;
    el.title = `PMID ${pub.pmid} · ${pub.gold}`;
    el.dataset.idx = String(pub.demo_idx);
    el.setAttribute("aria-label", `Publication ${pub.demo_idx} PMID ${pub.pmid}`);
    el.addEventListener("click", () => selectPub(pub.demo_idx));
    frag.appendChild(el);
  }
  grid.appendChild(frag);
}

function updateBlock(demoIdx) {
  const el = $("grid").querySelector(`[data-idx="${demoIdx}"]`);
  if (!el) return;
  const pub = pubs[demoIdx];
  el.className = `block ${blockClass(pub)}${selectedIdx === demoIdx ? " selected" : ""}`;
}

function selectPub(demoIdx) {
  selectedIdx = demoIdx;
  for (const el of $("grid").querySelectorAll(".block.selected")) el.classList.remove("selected");
  const el = $("grid").querySelector(`[data-idx="${demoIdx}"]`);
  if (el) el.classList.add("selected");
  showDetail(pubs[demoIdx]);
}

function clearNouls() {
  for (const [, id] of NOUL_FIELDS) $(id).textContent = "—";
}

function setNouls(r) {
  for (const [key, id] of NOUL_FIELDS) {
    let v = r[key];
    if ((v == null || v === "") && r.answers && r.answers[key]) v = r.answers[key].noul;
    $(id).textContent = fmtProb(v);
  }
}

function showDetail(pub) {
  if (!pub) {
    $("detail-empty").hidden = false;
    $("detail-body").hidden = true;
    return;
  }
  $("detail-empty").hidden = true;
  $("detail-body").hidden = false;
  $("d-pmid").textContent = `PMID ${pub.pmid}`;
  $("d-idx").textContent = `#${pub.demo_idx}`;
  $("d-title").textContent = pub.title || "(no title)";
  $("d-abstract").textContent = pub.abstract || "";
  const r = pub.result;
  if (!r) {
    $("d-pred").textContent = pub.state === "running" ? "…" : pub.error ? "error" : "—";
    $("d-pred").className = "v";
    $("d-choice").textContent = "—";
    $("d-conf").textContent = "—";
    $("d-p-rct").textContent = "—";
    $("d-p-non").textContent = "—";
    clearNouls();
    $("d-lat").textContent = "—";
    $("d-gold").textContent = pub.gold || "—";
    $("d-match").textContent = pub.error || pub.state || "pending";
    $("d-match").className = "v";
    return;
  }
  $("d-pred").textContent = r.pred || "—";
  $("d-pred").className = `v pred-${r.pred || ""}`;
  $("d-choice").textContent = r.choice || r.answers?.label?.choice || "—";
  const conf = Number(r.confidence);
  $("d-conf").textContent = Number.isFinite(conf) ? conf.toFixed(3) : "—";
  $("d-p-rct").textContent = fmtProb(r.p_RCT ?? r.probabilities?.RCT);
  $("d-p-non").textContent = fmtProb(r.p_non_RCT ?? r.probabilities?.non_RCT);
  setNouls(r);
  $("d-lat").textContent = r.latency_ms != null ? `${Math.round(Number(r.latency_ms))} ms` : "—";
  $("d-gold").textContent = pub.gold || "—";
  const agree = r.pred === pub.gold;
  const low = Number.isFinite(conf) && conf < AMBER_CONF;
  if (low) {
    $("d-match").textContent = agree ? "agree · low conf" : "disagree · low conf";
    $("d-match").className = "v warn";
  } else {
    $("d-match").textContent = agree ? "agree" : "disagree";
    $("d-match").className = agree ? "v hit" : "v miss";
  }
}

function fmtProb(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(3) : "—";
}

function updateScoreboard() {
  const done = pubs.filter((p) => p.state === "done" && p.result);
  const n = done.length;
  $("progress").textContent = `n=${n} / ${pubs.length}`;
  if (!n) {
    $("val-jev-acc").textContent = "—";
    $("val-jev-f1").textContent = "—";
    $("val-latency").textContent = "—";
    $("bar-jev-acc").style.width = "0%";
    $("bar-jev-f1").style.width = "0%";
    return;
  }
  let correct = 0, tp = 0, fp = 0, fn = 0, lat = 0;
  for (const p of done) {
    const pred = p.result.pred;
    const gold = p.gold;
    if (pred === gold) correct++;
    if (gold === "RCT" && pred === "RCT") tp++;
    if (gold !== "RCT" && pred === "RCT") fp++;
    if (gold === "RCT" && pred !== "RCT") fn++;
    lat += Number(p.result.latency_ms) || 0;
  }
  const acc = (correct / n) * 100;
  const prec = tp + fp ? tp / (tp + fp) : 0;
  const rec = tp + fn ? tp / (tp + fn) : 0;
  const f1 = (prec + rec ? (2 * prec * rec) / (prec + rec) : 0) * 100;
  $("bar-jev-acc").style.width = `${Math.min(acc, 100)}%`;
  $("bar-jev-f1").style.width = `${Math.min(f1, 100)}%`;
  $("val-jev-acc").textContent = `${acc.toFixed(2)}%`;
  $("val-jev-f1").textContent = `${f1.toFixed(2)}%`;
  $("val-latency").textContent = `${(lat / n).toFixed(0)} ms`;
}

function setBusy(busy) {
  running = busy;
  $("btn-start").disabled = busy;
  $("btn-replay").disabled = busy;
  $("btn-stop").disabled = !busy;
  $("sel-workers").disabled = busy;
}

function resetStates() {
  for (const p of pubs) {
    p.state = "pending";
    delete p.result;
    delete p.error;
  }
  selectedIdx = null;
  renderGrid();
  showDetail(null);
  updateScoreboard();
}

async function loadDemo() {
  const res = await fetch("/api/demo");
  if (!res.ok) throw new Error("Missing data/demo_200.csv — run: python -m src.prepare_demo");
  const data = await res.json();
  pubs = (data.rows || []).map((r) => ({
    demo_idx: Number(r.demo_idx),
    pmid: String(r.pmid || ""),
    title: r.title || "",
    abstract: r.abstract || "",
    gold: r.gold || "",
    state: "pending",
  }));
  pubs.sort((a, b) => a.demo_idx - b.demo_idx);
  renderGrid();
  updateScoreboard();
  $("status").textContent = `${pubs.length} pubs ready · hybrid default`;
  $("btn-start").textContent = "Start";
}

async function classifyOne(pub) {
  const res = await fetch("/api/classify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pmid: pub.pmid,
      title: pub.title,
      abstract: pub.abstract,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function runLive() {
  if (running) return;
  mode = "live";
  stopFlag = false;
  setBusy(true);
  resetStates();
  const workers = Math.max(1, Math.min(32, Number($("sel-workers").value) || DEFAULT_WORKERS));
  $("status").textContent = `Live hybrid · ${workers} workers`;

  let next = 0;
  const total = pubs.length;

  async function worker() {
    while (!stopFlag) {
      const i = next++;
      if (i >= total) return;
      const pub = pubs[i];
      pub.state = "running";
      updateBlock(pub.demo_idx);
      if (selectedIdx === pub.demo_idx) showDetail(pub);
      try {
        const result = await classifyOne(pub);
        if (stopFlag) return;
        pub.result = result;
        pub.state = "done";
      } catch (e) {
        pub.error = String(e.message || e);
        pub.state = "error";
        $("status").textContent = pub.error.slice(0, 80);
      }
      updateBlock(pub.demo_idx);
      if (selectedIdx === pub.demo_idx) showDetail(pub);
      updateScoreboard();
    }
  }

  await Promise.all(Array.from({ length: workers }, () => worker()));
  setBusy(false);
  $("status").textContent = stopFlag ? "Stopped" : `Done · ${pubs.filter((p) => p.state === "done").length}/${total}`;
}

function rowToResult(row) {
  const num = (v) => (v === "" || v == null ? null : Number(v));
  return {
    pred: row.pred,
    choice: row.choice || null,
    confidence: Number(row.confidence),
    p_RCT: Number(row.p_RCT),
    p_non_RCT: Number(row.p_non_RCT),
    probabilities: { RCT: Number(row.p_RCT), non_RCT: Number(row.p_non_RCT) },
    has_random_allocation: num(row.has_random_allocation),
    parallel_intervention_arms: num(row.parallel_intervention_arms),
    is_cluster_random: num(row.is_cluster_random),
    is_secondary_or_nested_only: num(row.is_secondary_or_nested_only),
    is_protocol_or_single_arm: num(row.is_protocol_or_single_arm),
    latency_ms: Number(row.latency_ms),
    rule: row.rule || "hybrid_cd_choice_plus_r2_nouls",
  };
}

async function runReplay() {
  if (running) return;
  mode = "replay";
  stopFlag = false;
  setBusy(true);
  resetStates();
  $("status").textContent = "Loading cached hybrid…";

  const res = await fetch("/api/predictions");
  if (!res.ok) {
    setBusy(false);
    $("status").textContent = "No results/predictions.csv — run eval or use Start";
    return;
  }
  const data = await res.json();
  const byPmid = new Map();
  for (const row of data.rows || []) byPmid.set(String(row.pmid), row);

  const workers = Math.max(1, Math.min(32, Number($("sel-workers").value) || DEFAULT_WORKERS));
  $("status").textContent = `Replay hybrid · ${workers} workers`;

  let next = 0;
  const total = pubs.length;

  async function worker() {
    while (!stopFlag) {
      const i = next++;
      if (i >= total) return;
      const pub = pubs[i];
      pub.state = "running";
      updateBlock(pub.demo_idx);
      await sleep(40 + (i % workers) * 12);
      if (stopFlag) return;
      const row = byPmid.get(pub.pmid);
      if (!row) {
        pub.state = "error";
        pub.error = "missing in cache";
      } else {
        pub.result = rowToResult(row);
        pub.state = "done";
      }
      updateBlock(pub.demo_idx);
      if (selectedIdx === pub.demo_idx) showDetail(pub);
      updateScoreboard();
    }
  }

  await Promise.all(Array.from({ length: workers }, () => worker()));
  setBusy(false);
  $("status").textContent = stopFlag
    ? "Stopped"
    : `Replay done · hybrid Acc 89.5% / F1 88.4% · vs BioBERT ${BIO_ACC}% / ${BIO_F1}%`;
}

$("btn-start").addEventListener("click", () => runLive().catch((e) => {
  setBusy(false);
  $("status").textContent = String(e.message || e);
}));
$("btn-replay").addEventListener("click", () => runReplay().catch((e) => {
  setBusy(false);
  $("status").textContent = String(e.message || e);
}));
$("btn-stop").addEventListener("click", () => {
  stopFlag = true;
  $("status").textContent = "Stopping…";
});

loadDemo().catch((e) => {
  $("status").textContent = String(e.message || e);
  $("btn-start").disabled = true;
  $("btn-replay").disabled = true;
});
