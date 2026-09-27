"""Context, tables and quotes for the docs - all read from committed result files."""
from __future__ import annotations

import json

from .dataset import DERIVED_DIR, LABEL_DIR, RESULTS_DIR

STOREFRONT_NAMES = {"sa": "Saudi Arabia", "kw": "Kuwait", "ae": "UAE", "qa": "Qatar", "bh": "Bahrain", "om": "Oman",
                    "hk": "Hong Kong", "gulf": "Gulf (pooled)"}
LABEL_TITLES = {
    "delivery_time": "Delivery time", "order_fulfilment": "Order fulfilment", "food_quality": "Food quality",
    "rider_behavior": "Rider behaviour", "merchant_availability": "Merchant/menu availability",
    "pricing_promos": "Pricing & promos", "payment_refund": "Payment & refunds", "customer_service": "Customer service",
    "app_ux": "App bugs & UX", "positive_praise": "Positive praise", "other": "Other",
}
GULF = ("sa", "kw", "ae", "qa", "bh", "om")
MIN_STOREFRONT_NEG = 30   # storefronts with fewer 1-2 star reviews are not ranked on their own


def load_results() -> dict:
    return {
        "metrics": json.loads((RESULTS_DIR / "metrics.json").read_text(encoding="utf-8")),
        "quality": json.loads((RESULTS_DIR / "label_quality.json").read_text(encoding="utf-8")),
        "manifest": json.loads((DERIVED_DIR / "snapshot_manifest.json").read_text(encoding="utf-8")),
    }


def _fmt_pct(x, d=0):
    return f"{100 * x:.{d}f}%"


def _fmt_ci(ci):
    return f"{100 * ci[0]:.0f}–{100 * ci[1]:.0f}%"


def _f2(x):
    return "n/a" if x is None else f"{x:.2f}"


def build_context() -> dict:
    res = load_results()
    m, q, man = res["metrics"], res["quality"], res["manifest"]
    prim = m["primary_method"]
    ctx = {"m": m, "q": q, "man": man, "prim": prim, "sec": m["secondary_method"]}
    ov = {o["storefront"]: o for o in m["overview"]}
    ctx["ov"] = ov
    pains = {}
    for method in ("rules", "llm"):
        pains[method] = {}
        for sf, labs in m["pain_point_intervals"][method].items():
            ranked = sorted(labs.items(), key=lambda kv: (kv[1]["rank"], -kv[1]["share"], kv[0]))
            pains[method][sf] = {"top": [dict(label=k, title=LABEL_TITLES[k], **v) for k, v in ranked],
                                 **{k: v for k, v in labs.items()}}
    ctx["pain"] = pains[prim]
    ctx["pain_sec"] = pains[m["secondary_method"]]
    ctx["pain_all"] = pains
    ctx["n_storefronts"] = len(ov)
    ctx["n_gulf"] = sum(ov[s]["n_reviews"] for s in ov if s in GULF)
    ctx["qo"] = {meth: q[meth]["overall"] for meth in ("rules", "llm")}
    ctx["diff"] = q["llm_minus_rules"]
    ctx["min_neg"] = MIN_STOREFRONT_NEG

    # storefronts with enough 1-2 star reviews to rank, and where each issue ranks first
    ranked = [sf for sf in pains[prim] if pains[prim][sf]["top"][0]["n_negative"] >= MIN_STOREFRONT_NEG]
    ctx["ranked"] = {"n": len(ranked), "names": ", ".join(STOREFRONT_NAMES[s] for s in ranked)}
    firsts = {}
    for sf in ranked:
        for row in pains[prim][sf]["top"]:
            if row["rank"] == 1:
                firsts.setdefault(row["label"], []).append(sf)
    ctx["rank1"] = {lab: {"n": len(v), "names": ", ".join(STOREFRONT_NAMES[s] for s in v)} for lab, v in firsts.items()}
    cs = [pains[prim][sf]["customer_service"]["share"] for sf in ranked if sf in GULF]
    ctx["cs_gulf_range"] = [min(cs), max(cs)]
    negs = [ov[s]["share_negative"] for s in ranked]
    ctx["neg_range"] = [min(negs), max(negs)]
    avg = [man["lookups"][s]["averageUserRating"] for s in ranked]
    ctx["store_avg_range"] = [min(avg), max(avg)]
    means = [ov[s]["mean_rating"] for s in ranked]
    ctx["written_mean_range"] = [min(means), max(means)]

    # region x band shares, co-occurrence, per-version rows, recent change
    band = {}
    for r in m["methods"][prim]["region_band"]:
        band.setdefault(r["region"], {}).setdefault(r["band"], {})[r["label"]] = r
    ctx["band"] = band
    cooc = {}
    for r in m["methods"][prim]["cooccurrence"]:
        cooc.setdefault(r["region"], {}).setdefault(r["label_a"], {})[r["label_b"]] = r
    ctx["cooc"] = cooc
    ver = {}
    for r in m["methods"][prim]["by_version"]:
        ver.setdefault(r["storefront"], {}).setdefault(r["app_version"].replace(".", "_"), r)
    ctx["ver"] = ver
    ctx["recent"] = m["recent_change"][prim]
    ctx["lang"] = q["language_detection"]
    ctx["snapshot_date"] = man["fetched_at"][:10]
    ctx["n_labels"] = len(q["labels"])
    ctx["boot"] = q["n_boot"]
    ctx["n_quotes"] = len(build_quotes())
    f1s = [(v["f1"], lab) for lab, v in q["rules"]["per_label"].items() if v["f1"] is not None]
    lo, hi = min(f1s), max(f1s)
    ctx["rules_f1_min"] = {"f1": lo[0], "title": LABEL_TITLES[lo[1]]}
    ctx["rules_f1_max"] = {"f1": hi[0], "title": LABEL_TITLES[hi[1]]}
    wins = [LABEL_TITLES[lab] for lab in q["labels"] if (q["llm_minus_rules"][lab]["ci"][0] or 0) > 0]
    losses = [LABEL_TITLES[lab] for lab in q["labels"] if (q["llm_minus_rules"][lab]["ci"][1] or 0) < 0]
    clear_cs = [pains[prim][sf]["customer_service"]["p_rank1"] for sf in ranked
                if pains[prim][sf]["customer_service"]["rank"] == 1 and sf in GULF]
    ctx["cs_rank1_gulf_pmin"] = min(clear_cs) if clear_cs else None
    ctx["words"] = {
        "llm_vs_rules": "lower" if q["llm"]["overall"]["micro_f1"] < q["rules"]["overall"]["micro_f1"] else "higher",
        "llm_wins": ", ".join(wins) if wins else "none",
        "llm_losses": ", ".join(losses) if losses else "none",
    }
    return ctx


def _table(header, rows, align=None):
    align = align or ["---"] * len(header)
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(align) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def table_overview():
    res = load_results()
    man, m = res["manifest"], res["metrics"]
    lang = {}
    for r in m["language_mix"]:
        lang.setdefault(r["storefront"], {})[r["lang"]] = r["n_reviews"]
    rows = []
    for o in m["overview"]:
        sf = o["storefront"]
        mix = ", ".join(f"{k} {v}" for k, v in sorted(lang[sf].items(), key=lambda kv: -kv[1]))
        rows.append([f"{STOREFRONT_NAMES[sf]} (`{sf}`)", o["n_reviews"], f"{o['first_date']} → {o['last_date']}",
                     f"{o['mean_rating']:.2f}", _fmt_pct(o["share_negative"]), mix,
                     f"{man['lookups'][sf]['userRatingCount']:,}", f"{man['lookups'][sf]['averageUserRating']:.2f}"])
    return _table(["Storefront", "Written reviews (n)", "Date range", "Mean ★", "1–2★ share", "Language mix",
                   "All ratings on store (n)", "Store average ★"], rows,
                  ["---", "---:", "---", "---:", "---:", "---", "---:", "---:"])


def table_quality():
    q = load_results()["quality"]
    rows = []
    for lab in q["labels"]:
        a, b, d = q["rules"]["per_label"][lab], q["llm"]["per_label"][lab], q["llm_minus_rules"][lab]
        ci = lambda r, k: "" if r[k + "_ci"][0] is None else f"[{r[k + '_ci'][0]:.2f}–{r[k + '_ci'][1]:.2f}]"  # noqa: E731
        dci = "" if d["ci"][0] is None else f"[{d['ci'][0]:+.2f}, {d['ci'][1]:+.2f}]"
        rows.append([LABEL_TITLES[lab], a["support"],
                     f"{_f2(a['precision'])} / {_f2(a['recall'])}", f"{_f2(a['f1'])} {ci(a, 'f1')}", _f2(a["kappa"]),
                     f"{_f2(b['precision'])} / {_f2(b['recall'])}", f"{_f2(b['f1'])} {ci(b, 'f1')}", _f2(b["kappa"]),
                     ("n/a" if d["diff"] is None else f"{d['diff']:+.2f}") + f" {dci}"])
    oa, ob, dd = q["rules"]["overall"], q["llm"]["overall"], q["llm_minus_rules"]["micro_f1"]
    rows.append(["**Micro-F1, all labels**", q["n_reference"], "", f"**{oa['micro_f1']:.2f}** "
                 f"[{oa['micro_f1_ci'][0]:.2f}–{oa['micro_f1_ci'][1]:.2f}]", "", "",
                 f"**{ob['micro_f1']:.2f}** [{ob['micro_f1_ci'][0]:.2f}–{ob['micro_f1_ci'][1]:.2f}]", "",
                 f"{dd['diff']:+.2f} [{dd['ci'][0]:+.2f}, {dd['ci'][1]:+.2f}]"])
    return _table(["Label", "Ref. n", "Rules P / R", "Rules F1 [95% CI]", "Rules κ", "LLM P / R", "LLM F1 [95% CI]",
                   "LLM κ", "LLM − rules F1 [95% CI]"], rows,
                  ["---", "---:", "---:", "---", "---:", "---:", "---", "---:", "---"])


def table_pain(method=None, min_neg=MIN_STOREFRONT_NEG, top=3):
    res = load_results()
    m = res["metrics"]
    method = method or m["primary_method"]
    rows = []
    for sf, labs in m["pain_point_intervals"][method].items():
        ranked = sorted(labs.items(), key=lambda kv: (kv[1]["rank"], -kv[1]["share"], kv[0]))
        n_neg = ranked[0][1]["n_negative"]
        if n_neg < min_neg:
            rows.append([STOREFRONT_NAMES[sf], n_neg, f"too few 1–2★ reviews to rank (< {min_neg})", "", ""])
            continue
        for i, (lab, v) in enumerate(ranked[:top]):
            rows.append([STOREFRONT_NAMES[sf] if i == 0 else "", n_neg if i == 0 else "",
                         f"{v['rank']}. {LABEL_TITLES[lab]}", f"{_fmt_pct(v['share'])} [{_fmt_ci(v['share_ci'])}]",
                         f"{v['p_rank1']:.2f}"])
    return _table(["Storefront", "1–2★ reviews", "Issue (rank)", "Share of 1–2★ [95% CI]", "P(rank 1)"], rows,
                  ["---", "---:", "---", "---", "---:"])


def table_cooc(region="gulf", label_a="customer_service"):
    ctx = build_context()
    rows = []
    for lab_b, r in sorted(ctx["cooc"][region][label_a].items(), key=lambda kv: -kv[1]["share_b_given_a"]):
        rows.append([LABEL_TITLES[lab_b], f"{r['n_ab']} / {r['n_a']}", _fmt_pct(r["share_b_given_a"])])
    return _table([f"Also mentions ({LABEL_TITLES[label_a]} complaints, {STOREFRONT_NAMES.get(region, region)})",
                   "Reviews", "Share"], rows, ["---", "---:", "---:"])


def table_recent(sf="ae"):
    ctx = build_context()
    e = ctx["recent"][sf]
    rows = [["1–2★ reviews", _fmt_pct(e["negative"]["base"]), _fmt_pct(e["negative"]["recent"]),
             f"{100 * e['negative']['diff']:+.0f} pp [{100 * e['negative']['diff_ci'][0]:+.0f}, "
             f"{100 * e['negative']['diff_ci'][1]:+.0f}]"]]
    for lab, v in e["labels"].items():
        if v["diff_ci"][0] > 0 or v["diff_ci"][1] < 0:
            rows.append([f"mentions {LABEL_TITLES[lab]}", _fmt_pct(v["base"]), _fmt_pct(v["recent"]),
                         f"{100 * v['diff']:+.0f} pp [{100 * v['diff_ci'][0]:+.0f}, {100 * v['diff_ci'][1]:+.0f}]"])
    base = ", ".join(e["base_months"])
    return _table(["Share of written reviews", f"{base} (n = {e['n_base']})", f"{e['recent_month']} (n = {e['n_recent']})",
                   "Difference [95% CI]"], rows, ["---", "---:", "---:", "---"])


def table_versions(sf="ae"):
    m = load_results()["metrics"]
    prim = m["primary_method"]
    seen, rows = set(), []
    recs = [r for r in m["methods"][prim]["by_version"] if r["storefront"] == sf]
    key = lambda v: tuple(int(x) for x in v.split("."))  # noqa: E731
    for r in sorted(recs, key=lambda r: key(r["app_version"])):
        if r["app_version"] in seen:
            continue
        seen.add(r["app_version"])
        rows.append([r["app_version"], r["n_reviews"], f"{r['mean_rating']:.2f}", _fmt_pct(r["share_negative"])])
    return _table(["App version", "Reviews", "Mean ★", "1–2★ share"], rows, ["---", "---:", "---:", "---:"])


def build_tables() -> dict:
    return {"overview": table_overview, "quality": table_quality, "pain": table_pain,
            "cooc_gulf_cs": table_cooc, "recent_ae": table_recent, "versions_ae": table_versions,
            "pain_secondary": lambda: table_pain(load_results()["metrics"]["secondary_method"])}


def build_quotes() -> dict:
    path = DERIVED_DIR / "excerpts.json"
    if not path.exists():
        return {}
    ex = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for e in ex:
        gloss = f" — *{e['gloss']}*" if e.get("gloss") else ""
        out[e["id"]] = f"“{e['excerpt']}”{gloss} ({STOREFRONT_NAMES[e['storefront']]}, {e['rating']}★)"
    return out


_ = LABEL_DIR  # noqa: F841 (kept for scripts that import paths from here)
