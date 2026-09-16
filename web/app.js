/** UI v2 — r3_ship default, Acc/F1 + cost/time, questions drawer. */
const BIO_ACC = 96.37;
const BIO_F1 = 90.85;
const AMBER_CONF = 0.55;
const DEFAULT_WORKERS = 8;
const INPUT_USD_PER_MTOK = 0.042;
const RULE_ID = "r3_ship_cd_choice_plus_reports_exp095";

const NOUL_ORDER = [
  "has_random_allocation",
  "parallel_intervention_arms",
  "is_cluster_random",
  "is_secondary_or_nested_only",
  "is_protocol_or_single_arm",
  "reports_or_reanalyzes_an_rct",
  "parent_study_was_rct",
  "experimental_allocation_implied",
  "is_review_or_meta",
];

const COMBINE_TEXT =
  "RCT iff choice==RCT\n" +
  "  OR ((rand|cluster|parallel)>=0.5 AND secondary<0.5 AND protocol<0.5)\n" +
  "  OR (reports>=0.5 AND review<0.5)\n" +
  "  OR (exp>=0.95 AND secondary<0.5 AND protocol<0.5 AND review<0.5)";

const $ = (id) => document.getElementById(id);

let pubs = [];
let selectedIdx = null;
let running = false;
let stopFlag = false;
let mode = "idle";
let questionsMeta = null;
let runStartedAt = 0;

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

function fmtProb(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(3) : "—";
}

function fmtUsd(v) {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  const n = Number(v);
  if (n < 0.01) return `$${n.toFixed(5)}`;
  return `$${n.toFixed(4)}`;
}

function tokenCost(tokens) {
  if (tokens == null || !Number.isFinite(Number(tokens))) return null;
  return (Number(tokens) * INPUT_USD_PER_MTOK) / 1_000_000;
}

function answerValue(r, key) {
  if (key === "label") return r.choice || r.answers?.label?.choice || "—";
  let v = r[key];
  if ((v == null || v === "") && r.answers && r.answers[key]) v = r.answers[key].noul;
  return v;
}

function usedInCombine(id) {
  if (["has_random_allocation", "parallel_intervention_arms", "is_cluster_random"].includes(id))
    return "positive ≥0.5";
  if (["is_secondary_or_nested_only", "is_protocol_or_single_arm"].includes(id))
    return "exclude <0.5";
  if (id === "reports_or_reanalyzes_an_rct") return "reports path ≥0.5";
  if (id === "is_review_or_meta") return "review gate <0.5";
  if (id === "experimental_allocation_implied") return "exp path ≥0.95";
  if (id === "parent_study_was_rct") return "queried · not in ship rule";
  return "";
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
  $("d-combine").textContent = COMBINE_TEXT;

  const r = pub.result;
  const ansBox = $("d-answers");
  ansBox.innerHTML = "";

  if (!r) {
    $("d-pred").textContent = pub.state === "running" ? "…" : pub.error ? "error" : "—";
    $("d-choice").textContent = "—";
    $("d-conf").textContent = "—";
    $("d-p-rct").textContent = "—";
    $("d-p-non").textContent = "—";
    $("d-lat").textContent = "—";
    $("d-tok").textContent = "—";
    $("d-cost").textContent = "—";
    $("d-gold").textContent = pub.gold || "—";
    $("d-match").textContent = pub.error || pub.state || "pending";
    $("d-match").className = "v";
    return;
  }

  $("d-pred").textContent = r.pred || "—";
  $("d-choice").textContent = r.choice || r.answers?.label?.choice || "—";
  const conf = Number(r.confidence);
  $("d-conf").textContent = Number.isFinite(conf) ? conf.toFixed(3) : "—";
  $("d-p-rct").textContent = fmtProb(r.p_RCT ?? r.probabilities?.RCT);
  $("d-p-non").textContent = fmtProb(r.p_non_RCT ?? r.probabilities?.non_RCT);
  $("d-lat").textContent = r.latency_ms != null ? `${Math.round(Number(r.latency_ms))} ms` : "—";

  const liveTok = r.input_tokens != null && r.input_tokens !== "";
  const toks = liveTok ? r.input_tokens : r.input_tokens_est;
  $("d-tok").textContent =
    toks != null && toks !== ""
      ? `${Number(toks).toLocaleString()}${liveTok ? "" : " est"}`
      : "—";
  const cost = r.cost_usd != null ? Number(r.cost_usd) : tokenCost(toks);
  $("d-cost").textContent = cost != null ? `${fmtUsd(cost)}${liveTok ? "" : " est"}` : "—";
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

  const rows = [{ id: "label", type: "choice", used: "choice==RCT" }].concat(
    NOUL_ORDER.map((id) => ({ id, type: "noul", used: usedInCombine(id) }))
  );
  for (const row of rows) {
    const el = document.createElement("div");
    el.className = "ans";
    const val = answerValue(r, row.id);
    const shown = row.type === "choice" ? String(val) : fmtProb(val);
    el.innerHTML = `
      <div>
        <div class="name">${row.id}</div>
        <div class="type">${row.type}</div>
      </div>
      <div style="text-align:right">
        <div class="val">${shown}</div>
        <div class="used">${row.used || ""}</div>
      </div>`;
    ansBox.appendChild(el);
  }
}

function updateScoreboard() {
  const done = pubs.filter((p) => p.state === "done" && p.result);
  const n = done.length;
  $("progress").textContent = `n=${n} / ${pubs.length}`;

  const wallMs = runStartedAt ? performance.now() - runStartedAt : 0;
  if (running || n) {
    $("val-wall").textContent =
      wallMs >= 1000 ? `${(wallMs / 1000).toFixed(1)} s` : `${Math.round(wallMs)} ms`;
  }

  if (!n) {
    $("val-acc").textContent = "—";
    $("val-f1").textContent = "—";
    $("val-latency").textContent = "—";
    $("val-cost").textContent = "—";
    $("cost-per").textContent = "— / paper";
    $("bar-acc").style.width = "0%";
    $("bar-f1").style.width = "0%";
    return;
  }

  let correct = 0,
    tp = 0,
    fp = 0,
    fn = 0,
    lat = 0,
    tok = 0,
    tokN = 0,
    liveTok = false;
  for (const p of done) {
    const pred = p.result.pred;
    const gold = p.gold;
    if (pred === gold) correct++;
    if (gold === "RCT" && pred === "RCT") tp++;
    if (gold !== "RCT" && pred === "RCT") fp++;
    if (gold === "RCT" && pred !== "RCT") fn++;
    lat += Number(p.result.latency_ms) || 0;
    const t = p.result.input_tokens ?? p.result.input_tokens_est;
    if (t != null && t !== "" && Number.isFinite(Number(t))) {
      tok += Number(t);
      tokN++;
      if (p.result.input_tokens != null && p.result.input_tokens !== "") liveTok = true;
    }
  }
  const acc = (correct / n) * 100;
  const prec = tp + fp ? tp / (tp + fp) : 0;
  const rec = tp + fn ? tp / (tp + fn) : 0;
  const f1 = (prec + rec ? (2 * prec * rec) / (prec + rec) : 0) * 100;
  $("bar-acc").style.width = `${Math.min(acc, 100)}%`;
  $("bar-f1").style.width = `${Math.min(f1, 100)}%`;
  $("val-acc").textContent = `${acc.toFixed(2)}%`;
  $("val-f1").textContent = `${f1.toFixed(2)}%`;
  $("val-latency").textContent = `${(lat / n).toFixed(0)} ms`;

  if (tokN) {
    const meanTok = tok / tokN;
    const shownCost = tokenCost(meanTok * n);
    $("val-cost").textContent = `${fmtUsd(shownCost)}${liveTok ? "" : " est"}`;
    $("cost-per").textContent = `${fmtUsd(tokenCost(meanTok))} / paper${liveTok ? "" : " · est"}`;
    $("cost-detail").textContent = liveTok
      ? `$0.042/MTok in · out free · ${Math.round(tok).toLocaleString()} tok`
      : `$0.042/MTok in · Replay uses token estimate (no live usage log)`;
  } else {
    $("val-cost").textContent = "—";
    $("cost-per").textContent = "— / paper";
    $("cost-detail").textContent = "$0.042 / MTok in · out free";
  }
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

async function loadQuestions() {
  try {
    const res = await fetch("/api/questions");
    if (!res.ok) return;
    questionsMeta = await res.json();
    $("q-combine").textContent = questionsMeta.combine || COMBINE_TEXT;
    const list = $("q-list");
    list.innerHTML = "";
    for (const q of questionsMeta.questions || []) {
      const card = document.createElement("div");
      card.className = "q-card";
      const crit = Object.entries(q.criteria || {})
        .map(([k, v]) => `<li><strong>${k}</strong>: ${v}</li>`)
        .join("");
      card.innerHTML = `
        <div><span class="qid">${q.id}</span><span class="qtype">${q.type || ""}</span></div>
        <p class="instr">${q.instructions || ""}</p>
        <ul>${crit}</ul>`;
      list.appendChild(card);
    }
  } catch (_) {
    $("q-combine").textContent = COMBINE_TEXT;
  }
}

function openDrawer(open) {
  $("questions-drawer").hidden = !open;
  $("drawer-backdrop").hidden = !open;
}

async function loadDemo() {
  const res = await fetch("/api/demo");
  if (!res.ok) throw new Error("Missing data/demo_200.csv");
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
  $("status").textContent = `${pubs.length} pubs · r3_ship`;
  await loadQuestions();
}

async function classifyOne(pub) {
  const res = await fetch("/api/classify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pmid: pub.pmid, title: pub.title, abstract: pub.abstract }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function runPool(workerFn) {
  const workers = Math.max(1, Math.min(32, Number($("sel-workers").value) || DEFAULT_WORKERS));
  let next = 0;
  const total = pubs.length;
  async function worker() {
    while (!stopFlag) {
      const i = next++;
      if (i >= total) return;
      await workerFn(pubs[i], i);
    }
  }
  await Promise.all(Array.from({ length: workers }, () => worker()));
}

async function runLive() {
  if (running) return;
  mode = "live";
  stopFlag = false;
  setBusy(true);
  resetStates();
  runStartedAt = performance.now();
  const workers = Math.max(1, Math.min(32, Number($("sel-workers").value) || DEFAULT_WORKERS));
  $("status").textContent = `Live r3_ship · ${workers} workers`;
  $("wall-note").textContent = "live";

  await runPool(async (pub) => {
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
  });

  setBusy(false);
  $("wall-note").textContent = "final";
  updateScoreboard();
  $("status").textContent = stopFlag
    ? "Stopped"
    : `Done · ${pubs.filter((p) => p.state === "done").length}/${pubs.length}`;
}

function rowToResult(row) {
  const num = (v) => (v === "" || v == null ? null : Number(v));
  const input_tokens = num(row.input_tokens);
  const input_tokens_est = num(row.input_tokens_est);
  const toks = input_tokens ?? input_tokens_est;
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
    reports_or_reanalyzes_an_rct: num(row.reports_or_reanalyzes_an_rct),
    parent_study_was_rct: num(row.parent_study_was_rct),
    experimental_allocation_implied: num(row.experimental_allocation_implied),
    is_review_or_meta: num(row.is_review_or_meta),
    latency_ms: Number(row.latency_ms),
    input_tokens,
    input_tokens_est,
    cost_usd: tokenCost(toks),
    rule: row.rule || RULE_ID,
  };
}

async function runReplay() {
  if (running) return;
  mode = "replay";
  stopFlag = false;
  setBusy(true);
  resetStates();
  runStartedAt = performance.now();
  $("status").textContent = "Loading cached r3_ship…";
  $("wall-note").textContent = "replay";

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
  $("status").textContent = `Replay r3_ship · ${workers} workers`;

  await runPool(async (pub, i) => {
    pub.state = "running";
    updateBlock(pub.demo_idx);
    await sleep(35 + (i % workers) * 10);
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
  });

  setBusy(false);
  $("wall-note").textContent = "final";
  updateScoreboard();
  $("status").textContent = stopFlag
    ? "Stopped"
    : `Replay done · r3_ship Acc 93.5% / F1 93.12% · vs BioBERT ${BIO_ACC}% / ${BIO_F1}%`;
}

$("btn-start").addEventListener("click", () =>
  runLive().catch((e) => {
    setBusy(false);
    $("status").textContent = String(e.message || e);
  })
);
$("btn-replay").addEventListener("click", () =>
  runReplay().catch((e) => {
    setBusy(false);
    $("status").textContent = String(e.message || e);
  })
);
$("btn-stop").addEventListener("click", () => {
  stopFlag = true;
  $("status").textContent = "Stopping…";
});
$("btn-questions").addEventListener("click", () => openDrawer(true));
$("btn-close-q").addEventListener("click", () => openDrawer(false));
$("drawer-backdrop").addEventListener("click", () => openDrawer(false));

loadDemo().catch((e) => {
  $("status").textContent = String(e.message || e);
  $("btn-start").disabled = true;
  $("btn-replay").disabled = true;
});
