"""Generate docs/dashboard.html: one self-contained file (inline CSS/JS/SVG, no external requests).

    python scripts/build_dashboard.py           # write
    python scripts/build_dashboard.py --check   # fail if the committed file is stale
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from keeta_voc.facts import LABEL_TITLES, MIN_STOREFRONT_NEG, STOREFRONT_NAMES, load_results  # noqa: E402

OUT = ROOT / "docs" / "dashboard.html"

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Keeta review VOC</title>
<style>
:root { color-scheme: light; --surface:#fcfcfb; --panel:#ffffff; --ink:#0b0b0b; --ink2:#52514e; --muted:#8a8984;
  --grid:#e4e3df; --bar:#2a78d6; --whisker:#0b0b0b; --line:#d9d8d3; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark; --surface:#1a1a19;
  --panel:#222221; --ink:#ffffff; --ink2:#c3c2b7; --muted:#8f8e86; --grid:#34332f; --bar:#3987e5; --whisker:#ffffff;
  --line:#3a3935; } }
:root[data-theme="dark"] { color-scheme: dark; --surface:#1a1a19; --panel:#222221; --ink:#ffffff; --ink2:#c3c2b7;
  --muted:#8f8e86; --grid:#34332f; --bar:#3987e5; --whisker:#ffffff; --line:#3a3935; }
* { box-sizing: border-box; }
body { margin:0; background:var(--surface); color:var(--ink); font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width: 1080px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 16px; margin: 28px 0 8px; }
p.sub { color: var(--ink2); margin: 0 0 16px; }
.tiles { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.tile { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; }
.tile .k { color:var(--ink2); font-size:12px; } .tile .v { font-size:22px; font-weight:600; font-variant-numeric: tabular-nums; }
.tile .s { color:var(--muted); font-size:12px; }
.grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: 16px; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; min-width:0; }
.card h3 { font-size:14px; margin:0 0 2px; } .card .n { color:var(--ink2); font-size:12px; margin-bottom:6px; }
svg { display:block; width:100%; height:auto; overflow:visible; }
svg text { fill: var(--ink2); font-size: 11px; } svg .val { fill: var(--ink); font-variant-numeric: tabular-nums; }
svg .gl { stroke: var(--grid); } svg .bar { fill: var(--bar); } svg .ci { stroke: var(--whisker); stroke-width: 1.5; }
svg .hit { fill: transparent; } svg .hit:hover + .bar, svg .row:hover .bar { opacity: .8; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); }
th { color: var(--ink2); font-weight: 600; font-size: 12px; } td.num { text-align: right; }
.tablewrap { overflow-x:auto; background:var(--panel); border:1px solid var(--line); border-radius:8px; }
#tip { position: fixed; pointer-events: none; background: var(--panel); color: var(--ink); border:1px solid var(--line);
  border-radius:6px; padding:6px 8px; font-size:12px; box-shadow:0 2px 8px rgba(0,0,0,.15); display:none; max-width:260px; }
.note { color: var(--ink2); font-size: 12px; margin-top: 12px; }
</style>
</head>
<body>
<main>
<h1>Keeta App Store reviews: voice of customer</h1>
<p class="sub" id="sub"></p>
<div class="tiles" id="tiles"></div>
<h2>Pain points: share of 1&ndash;2&#9733; reviews mentioning each issue</h2>
<p class="sub" id="painsub"></p>
<div class="grid" id="pain"></div>
<h2>Label quality against the reference set</h2>
<div class="tablewrap"><table id="quality"></table></div>
<p class="note" id="note"></p>
</main>
<div id="tip" role="tooltip"></div>
<script>
const DATA = __DATA__;
const $ = (id) => document.getElementById(id);
const pct = (x) => (100 * x).toFixed(0) + "%";
const f2 = (x) => x == null ? "n/a" : x.toFixed(2);
$("sub").textContent = `${DATA.n_reviews} public App Store reviews, snapshot ${DATA.fetched_at}. Labels: ${DATA.primary} (primary labeler). Personal project; not affiliated with Keeta or Meituan.`;
$("painsub").textContent = "Bars: share of 1\\u20132\\u2605 reviews; whiskers: 95% bootstrap interval. Hover a bar for counts.";
for (const o of DATA.overview) {
  const d = document.createElement("div"); d.className = "tile";
  d.innerHTML = `<div class="k">${DATA.names[o.storefront] || o.storefront}</div><div class="v">${o.n_reviews}</div>` +
    `<div class="s">reviews &middot; mean ${o.mean_rating.toFixed(2)}&#9733; &middot; ${pct(o.share_negative)} are 1&ndash;2&#9733;</div>`;
  $("tiles").appendChild(d);
}
const tip = $("tip");
function showTip(e, html) { tip.innerHTML = html; tip.style.display = "block";
  const x = Math.min(e.clientX + 12, window.innerWidth - 270); tip.style.left = x + "px"; tip.style.top = (e.clientY + 12) + "px"; }
function hideTip() { tip.style.display = "none"; }
const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, parent) { const x = document.createElementNS(NS, tag); for (const k in attrs) x.setAttribute(k, attrs[k]); if (parent) parent.appendChild(x); return x; }
for (const sf of Object.keys(DATA.pain)) {
  const rows = Object.entries(DATA.pain[sf]).sort((a, b) => a[1].rank - b[1].rank || b[1].share - a[1].share);
  const card = document.createElement("div"); card.className = "card";
  const nneg = rows.length ? rows[0][1].n_negative : 0;
  card.innerHTML = `<h3>${DATA.names[sf] || sf}</h3><div class="n">n = ${nneg} reviews rated 1&ndash;2&#9733;</div>`;
  if (nneg < DATA.min_negative) {
    const note = document.createElement("p"); note.className = "note";
    note.textContent = `Too few 1–2★ reviews to rank (< ${DATA.min_negative}). No ranking or intervals shown.`;
    card.appendChild(note); $("pain").appendChild(card); continue;
  }
  const W = 380, L = 164, R = 44, rowH = 22, H = rows.length * rowH + 18;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Pain points, ${sf}` }, card);
  const x = (v) => L + v * (W - L - R);
  for (const t of [0, 0.25, 0.5, 0.75, 1]) { el("line", { x1: x(t), x2: x(t), y1: 0, y2: H - 16, class: "gl" }, svg);
    const tx = el("text", { x: x(t), y: H - 3, "text-anchor": "middle" }, svg); tx.textContent = pct(t); }
  rows.forEach(([lab, r], i) => {
    const y = i * rowH + 3, g = el("g", { class: "row" }, svg);
    const lt = el("text", { x: L - 6, y: y + 12, "text-anchor": "end" }, g); lt.textContent = DATA.titles[lab] || lab;
    el("rect", { x: x(0), y: y + 2, width: Math.max(0, x(r.share) - x(0)), height: 14, rx: 2, class: "bar" }, g);
    el("line", { x1: x(r.share_ci[0]), x2: x(r.share_ci[1]), y1: y + 9, y2: y + 9, class: "ci" }, g);
    const vt = el("text", { x: x(r.share_ci[1]) + 4, y: y + 13, class: "val" }, g); vt.textContent = pct(r.share);
    const hit = el("rect", { x: 0, y: y, width: W, height: rowH, class: "hit" }, g);
    hit.addEventListener("mousemove", (e) => showTip(e, `<b>${DATA.titles[lab] || lab}</b><br>${r.n_label} of ${r.n_negative} (${pct(r.share)})<br>95% CI ${pct(r.share_ci[0])}\\u2013${pct(r.share_ci[1])}<br>P(rank 1) = ${r.p_rank1.toFixed(2)}`));
    hit.addEventListener("mouseleave", hideTip);
  });
  $("pain").appendChild(card);
}
const q = DATA.quality;
let html = "<thead><tr><th>Label</th><th class=num>Ref. n</th><th class=num>Rules F1</th><th>95% CI</th><th class=num>LLM F1</th><th>95% CI</th></tr></thead><tbody>";
for (const lab of q.labels) {
  const a = q.rules.per_label[lab], b = q.llm.per_label[lab];
  const ci = (r) => r.f1_ci[0] == null ? "" : `${f2(r.f1_ci[0])}\\u2013${f2(r.f1_ci[1])}`;
  html += `<tr><td>${DATA.titles[lab] || lab}</td><td class=num>${a.support}</td><td class=num>${f2(a.f1)}</td><td>${ci(a)}</td><td class=num>${f2(b.f1)}</td><td>${ci(b)}</td></tr>`;
}
const oa = q.rules.overall, ob = q.llm.overall;
html += `<tr><td><b>Micro-F1 (all labels)</b></td><td class=num>${q.n_reference}</td><td class=num>${f2(oa.micro_f1)}</td><td>${f2(oa.micro_f1_ci[0])}\\u2013${f2(oa.micro_f1_ci[1])}</td><td class=num>${f2(ob.micro_f1)}</td><td>${f2(ob.micro_f1_ci[0])}\\u2013${f2(ob.micro_f1_ci[1])}</td></tr></tbody>`;
$("quality").innerHTML = html;
$("note").textContent = "Reference labels are AI-assisted labels by the project author, not independent human annotation. App Store reviews are a self-selected sample; this is not Keeta internal data.";
</script>
</body>
</html>
"""


def payload() -> dict:
    res = load_results()
    m, q, man = res["metrics"], res["quality"], res["manifest"]
    prim = m["primary_method"]
    return {
        "n_reviews": m["n_reviews"], "fetched_at": man["fetched_at"][:10], "primary": prim,
        "overview": m["overview"], "pain": m["pain_point_intervals"][prim],
        "min_negative": MIN_STOREFRONT_NEG,
        "names": STOREFRONT_NAMES, "titles": LABEL_TITLES,
        "quality": {k: q[k] for k in ("labels", "n_reference", "rules", "llm")},
    }


def build() -> str:
    data = json.dumps(payload(), ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return PAGE.replace("__DATA__", data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    html = build()
    if args.check:
        if OUT.read_text(encoding="utf-8") != html:
            sys.exit("docs/dashboard.html is stale; run scripts/build_dashboard.py")
        print("dashboard.html is current")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
