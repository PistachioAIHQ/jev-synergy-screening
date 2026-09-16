const BIO_ACC = 96.37;
const BIO_F1 = 90.85;

const $ = (id) => document.getElementById(id);
let rows = [];
let metrics = null;
let delayMs = 420;
let running = false;

async function loadData() {
  const [predRes, metRes] = await Promise.all([
    fetch("/api/predictions"),
    fetch("/api/metrics"),
  ]);
  if (!predRes.ok) throw new Error("Missing predictions — run: python -m src.run_eval");
  const pred = await predRes.json();
  rows = pred.rows || [];
  if (metRes.ok) metrics = await metRes.json();
}

function spawnFlyer(text) {
  const el = document.createElement("div");
  el.className = "flyer";
  el.textContent = text.slice(0, 90) + (text.length > 90 ? "…" : "");
  el.style.top = `${Math.random() * 18}px`;
  $("lane").appendChild(el);
  setTimeout(() => el.remove(), 2500);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function updateScoreboard(subset) {
  const n = subset.length;
  if (!n) return;
  let correct = 0, tp = 0, fp = 0, fn = 0, lat = 0;
  for (const r of subset) {
    const ok = String(r.correct) === "True" || String(r.correct) === "true" || r.pred === r.gold;
    if (ok) correct++;
    if (r.gold === "RCT" && r.pred === "RCT") tp++;
    if (r.gold !== "RCT" && r.pred === "RCT") fp++;
    if (r.gold === "RCT" && r.pred !== "RCT") fn++;
    lat += Number(r.latency_ms) || 0;
  }
  const acc = (correct / n) * 100;
  const prec = tp + fp ? tp / (tp + fp) : 0;
  const rec = tp + fn ? tp / (tp + fn) : 0;
  const f1 = (prec + rec ? (2 * prec * rec) / (prec + rec) : 0) * 100;
  $("bar-jev-acc").style.width = `${Math.min(acc, 100)}%`;
  $("bar-jev-f1").style.width = `${Math.min(f1, 100)}%`;
  $("val-jev-acc").textContent = `${acc.toFixed(2)}%`;
  $("val-jev-f1").textContent = `${f1.toFixed(2)}%`;
  $("latency").textContent = `mean latency ${(lat / n).toFixed(0)} ms · n=${n} · BioBERT Acc ${BIO_ACC}% / F1 ${BIO_F1}%`;
}

async function runDemo() {
  if (running) return;
  running = true;
  $("btn-start").disabled = true;
  const useAll = $("chk-all").checked;
  const subset = useAll ? rows.slice() : rows.slice(0, Math.min(24, rows.length));
  $("card").hidden = false;
  const seen = [];

  for (let i = 0; i < subset.length; i++) {
    const r = subset[i];
    spawnFlyer(r.title || r.text || "");
    $("pmid").textContent = `PMID ${r.pmid}`;
    $("progress").textContent = `${i + 1} / ${subset.length}`;
    $("title").textContent = r.title || "(no title)";
    $("abstract").textContent = r.abstract || "";
    const pred = r.pred || "—";
    $("pred-label").textContent = pred;
    $("pred-label").className = `label ${pred}`;
    $("pred-conf").textContent = `conf ${(Number(r.confidence) || 0).toFixed(2)} · noul ${(Number(r.noul_is_rct) || 0).toFixed(2)}`;
    const ok = String(r.correct) === "True" || String(r.correct) === "true" || r.pred === r.gold;
    $("gold-line").innerHTML = ok
      ? `<span class="hit">✓ match · gold ${r.gold}</span>`
      : `<span class="miss">✗ miss · gold ${r.gold}</span>`;
    $("card").className = `card ${ok ? "ok" : "bad"}`;
    seen.push(r);
    updateScoreboard(seen);
    await sleep(delayMs);
  }

  if (metrics && useAll) {
    $("bar-jev-acc").style.width = `${(metrics.accuracy * 100).toFixed(2)}%`;
    $("bar-jev-f1").style.width = `${(metrics.f1_RCT * 100).toFixed(2)}%`;
    $("val-jev-acc").textContent = `${(metrics.accuracy * 100).toFixed(2)}%`;
    $("val-jev-f1").textContent = `${(metrics.f1_RCT * 100).toFixed(2)}%`;
    $("latency").textContent = `mean latency ${metrics.mean_latency_ms.toFixed(0)} ms · n=${metrics.n} · live metrics.json`;
  }

  running = false;
  $("btn-start").disabled = false;
}

$("btn-start").addEventListener("click", runDemo);
$("btn-fast").addEventListener("click", () => {
  delayMs = delayMs > 200 ? 160 : 420;
  $("btn-fast").textContent = delayMs < 200 ? "Slower" : "Faster";
});

loadData()
  .then(() => {
    $("btn-start").textContent = `Start demo (${rows.length} ready)`;
    if (metrics) {
      $("bar-jev-acc").style.width = `${(metrics.accuracy * 100).toFixed(2)}%`;
      $("bar-jev-f1").style.width = `${(metrics.f1_RCT * 100).toFixed(2)}%`;
      $("val-jev-acc").textContent = `${(metrics.accuracy * 100).toFixed(2)}%`;
      $("val-jev-f1").textContent = `${(metrics.f1_RCT * 100).toFixed(2)}%`;
      $("latency").textContent = `mean latency ${metrics.mean_latency_ms.toFixed(0)} ms · n=${metrics.n}`;
    }
  })
  .catch((e) => {
    $("btn-start").textContent = "Data missing";
    $("latency").textContent = String(e.message || e);
  });
