"""Render the paper figures as IEEE Access submission-grade assets.

Data-driven figures (2, 3, 5, 6, 7, 8, noise_sweep) are computed live from
experiments/results.json so they match the canonical run / MANIFEST.md exactly.
Timing figures (4, 9) carry the published values unchanged and are re-exported
to vector PDF for submission quality.

Every figure is written as a true vector PDF (plt.savefig .pdf) plus a 600-DPI
PNG fallback, with Type-42 (TrueType) embedded fonts, and each data series is
distinguished by BOTH colour and line-style/marker (IEEE grayscale rule).
"""
import os
import json
import statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(OUT)
R = json.load(open(os.path.join(ROOT, "experiments", "results.json")))

# ---------------------------------------------------------------- global style
plt.rcParams.update({
    "pdf.fonttype": 42,          # embed TrueType (IEEE #1 reject cause)
    "ps.fonttype": 42,
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "lines.linewidth": 1.3,      # >= 1pt
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

# Consistent palette + marker/linestyle per system (colour AND style).
STYLE = {
    "trkg":       dict(color="#1f4e79", marker="o", linestyle="-",  hatch=""),
    "trkg_xdom":  dict(color="#2e7d32", marker="s", linestyle="-.", hatch=".."),
    "siloed":     dict(color="#c4641c", marker="^", linestyle="--", hatch="//"),
    "noont":      dict(color="#a02828", marker="d", linestyle=":",  hatch="xx"),
}

SEEDS_N = 10


def line(key):
    """Line/marker kwargs for a series (drops the bar-only 'hatch')."""
    return {k: v for k, v in STYLE[key].items() if k != "hatch"}


def mean(xs):
    return statistics.mean(xs)


def sd(xs):
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"{name}.pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, f"{name}.png"), dpi=600, bbox_inches="tight")
    plt.close(fig)


report = {}  # name -> dict of plotted arrays, for value-match printout

# ============================================================ DATA-DRIVEN FIGS
SCALES = [1000, 5000, 10000, 25000, 50000, 100000]
e1c = R["e1_conflicts"]


def scale_series(field):
    return ([mean(e1c[str(s)][field]) for s in SCALES],
            [sd(e1c[str(s)][field]) for s in SCALES])


trkg_total, trkg_total_sd = scale_series("conflicts")
trkg_xdom, trkg_xdom_sd = scale_series("cross_domain")
siloed_total, siloed_total_sd = scale_series("siloed_conflicts")
noont_total, noont_total_sd = scale_series("untyped_conflicts")
scales = np.array(SCALES)

# ---- Figure 2: conflict counts vs scale ------------------------------------
fig, ax = plt.subplots(figsize=(3.5, 2.7))
ax.errorbar(scales, trkg_total, yerr=trkg_total_sd, label="T-RKG total",
            ms=4, capsize=2, **line("trkg"))
ax.errorbar(scales, trkg_xdom, yerr=trkg_xdom_sd, label="T-RKG cross-domain",
            ms=4, capsize=2, **line("trkg_xdom"))
ax.errorbar(scales, siloed_total, yerr=siloed_total_sd, label="Siloed total",
            ms=4, capsize=2, **line("siloed"))
ax.plot(scales, noont_total, label="No-Ontology total", ms=4, **line("noont"))
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Dataset size (records)")
ax.set_ylabel("Conflicts detected (log)")
ax.set_title("Conflict detection across scales (10 seeds, mean $\\pm$ $\\sigma$)")
ax.legend(loc="lower right", framealpha=0.85)
save(fig, "fig2_conflicts_vs_scale")
report["fig2_conflicts_vs_scale"] = dict(
    scales=SCALES, trkg_total=trkg_total, trkg_xdom=trkg_xdom,
    siloed_total=siloed_total, noont_total=noont_total)

# ---- Figure 3: cross-domain bars -------------------------------------------
fig, ax = plt.subplots(figsize=(3.5, 2.5))
x = np.arange(len(SCALES))
w = 0.27
ax.bar(x - w, trkg_xdom, w, yerr=trkg_xdom_sd, label="T-RKG", capsize=2,
       color=STYLE["trkg"]["color"], hatch=STYLE["trkg"]["hatch"],
       edgecolor="black", linewidth=0.5)
ax.bar(x, np.zeros(len(SCALES)), w, label="Siloed",
       color=STYLE["siloed"]["color"], hatch=STYLE["siloed"]["hatch"],
       edgecolor="black", linewidth=0.5)
ax.bar(x + w, np.zeros(len(SCALES)), w, label="No-Ontology",
       color=STYLE["noont"]["color"], hatch=STYLE["noont"]["hatch"],
       edgecolor="black", linewidth=0.5)
ax.set_xticks(x)
ax.set_xticklabels([f"{s // 1000}K" for s in SCALES])
ax.set_xlabel("Dataset size")
ax.set_ylabel("Cross-domain conflicts detected")
ax.set_title("Cross-domain conflicts: only T-RKG sees them")
ax.legend(loc="upper left")
save(fig, "fig3_cross_domain_bars")
report["fig3_cross_domain_bars"] = dict(
    scales=SCALES, trkg_xdom=trkg_xdom, siloed_xdom=[0] * 6, noont_xdom=[0] * 6)

# ---- Figure 5: applicability F1 clean vs noised ----------------------------
e7 = R["e7_pr_f1"]


def f1(regime, det):
    vals = [t[2] for t in e7[regime][det]]
    return mean(vals), sd(vals)


systems = ["T-RKG", "Siloed", "No-Ontology"]
det_keys = ["trkg", "siloed", "untyped"]
clean = [f1("clean", d)[0] for d in det_keys]
clean_sd = [f1("clean", d)[1] for d in det_keys]
noised = [f1("noised", d)[0] for d in det_keys]
noised_sd = [f1("noised", d)[1] for d in det_keys]

x = np.arange(len(systems))
w = 0.35
fig, ax = plt.subplots(figsize=(3.5, 2.6))
ax.bar(x - w / 2, clean, w, yerr=clean_sd, capsize=3, label="Clean regime",
       color="#1f4e79", hatch="", edgecolor="black", linewidth=0.5)
ax.bar(x + w / 2, noised, w, yerr=noised_sd, capsize=3, label="10% noise regime",
       color="#a02828", hatch="//", edgecolor="black", linewidth=0.5)
ax.set_xticks(x)
ax.set_xticklabels(systems)
ax.set_ylabel("Per-record applicability F1")
ax.set_ylim(0, 1.12)
ax.set_title("Applicability F1: baseline gap and T-RKG robustness")
ax.legend(loc="upper right")
save(fig, "fig5_f1_clean_vs_noise")
report["fig5_f1_clean_vs_noise"] = dict(
    systems=systems, clean=clean, noised=noised)

# ---- Figure noise_sweep: e12 per-rate F1 -----------------------------------
e12 = R["e12_noise_sweep"]
rates = [0.02, 0.05, 0.10, 0.15, 0.20]


def sweep_f1(det):
    return ([mean([t[2] for t in e12[f"{r:.2f}"][det]]) for r in rates],
            [sd([t[2] for t in e12[f"{r:.2f}"][det]]) for r in rates])


ns_trkg, ns_trkg_sd = sweep_f1("trkg")
ns_siloed, ns_siloed_sd = sweep_f1("siloed")
ns_noont, ns_noont_sd = sweep_f1("untyped")
rate_pct = np.array(rates) * 100

fig, ax = plt.subplots(figsize=(3.5, 2.6))
ax.errorbar(rate_pct, ns_trkg, yerr=ns_trkg_sd, label="T-RKG", ms=4, capsize=2,
            **line("trkg"))
ax.errorbar(rate_pct, ns_siloed, yerr=ns_siloed_sd, label="Siloed", ms=4,
            capsize=2, **line("siloed"))
ax.errorbar(rate_pct, ns_noont, yerr=ns_noont_sd, label="No-Ontology", ms=4,
            capsize=2, **line("noont"))
ax.set_xlabel("Jurisdiction-noise rate (%)")
ax.set_ylabel("Applicability F1")
ax.set_ylim(0, 1.05)
ax.set_title("Applicability F1 under increasing label noise (10 seeds)")
ax.legend(loc="center right")
save(fig, "fig_noise_sweep")
report["fig_noise_sweep"] = dict(
    rates=rates, trkg=ns_trkg, siloed=ns_siloed, noont=ns_noont)

# ---- Figure 7: robustness sweep (e9) ---------------------------------------
e9 = R["e9_robustness_sweep"]
eu_fracs = [0.05, 0.15, 0.30, 0.40]
xdom = [mean(e9[f"eu{f:.2f}_pii0.05"]["cross_dom"]) for f in eu_fracs]
xdom_sd = [sd(e9[f"eu{f:.2f}_pii0.05"]["cross_dom"]) for f in eu_fracs]
multireg = [mean(e9[f"eu{f:.2f}_pii0.05"]["multi_reg"]) for f in eu_fracs]
multireg_sd = [sd(e9[f"eu{f:.2f}_pii0.05"]["multi_reg"]) for f in eu_fracs]
eu_pct = np.array(eu_fracs) * 100

fig, ax = plt.subplots(figsize=(3.5, 2.5))
ax.errorbar(eu_pct, xdom, yerr=xdom_sd, label="Cross-domain conflicts", ms=5,
            capsize=2, **line("trkg_xdom"))
ax.errorbar(eu_pct, multireg, yerr=multireg_sd,
            label="Records with $\\geq$ 2 regulations", ms=5, capsize=2,
            **line("trkg"))
ax.set_xlabel("EU jurisdictional fraction (%)")
ax.set_ylabel("Count")
ax.set_title("Robustness: smooth scaling with EU fraction")
ax.legend(loc="center right")
save(fig, "fig7_robustness_sweep")
report["fig7_robustness_sweep"] = dict(
    eu_pct=list(eu_pct), xdom=xdom, multireg=multireg)

# ======================================================= TIMING / PROPAGATION
# Published values (machine-timing / propagation) — unchanged, re-exported.

# ---- Figure 4: scalability (throughput + detection latency) ----------------
build_thr = np.array([71580, 66428, 61355, 54721, 50744, 48425])
conflict_ms = np.array([3.2, 16.1, 32.7, 84.8, 161, 319])
fig, ax1 = plt.subplots(figsize=(3.5, 2.6))
ax1.plot(scales, build_thr / 1000, marker="o", linestyle="-", ms=4,
         color="#1f4e79", label="Build throughput")
ax1.set_xlabel("Dataset size (records)")
ax1.set_xscale("log")
ax1.set_ylabel("Build throughput (K records / s)", color="#1f4e79")
ax1.tick_params(axis="y", labelcolor="#1f4e79")
ax1.set_ylim(0, 80)
ax2 = ax1.twinx()
ax2.plot(scales, conflict_ms, marker="s", linestyle="--", ms=4,
         color="#a02828", label="Conflict detection")
ax2.set_ylabel("Conflict detection (ms)", color="#a02828")
ax2.tick_params(axis="y", labelcolor="#a02828")
ax2.set_yscale("log")
ax2.grid(False)
ax1.set_title("Scalability: throughput and detection latency")
save(fig, "fig4_scalability")

# ---- Figure 6: propagation latency vs seed set (tab:largeseed) --------------
# Canonical source: results.json e8_large_seed_propagation (100K corpus, depth 5).
# tab:largeseed reports the seed-42 latency and the 10-seed-mean hold-set size;
# both are reproduced live here so the figure matches the table exactly.
e8 = R["e8_large_seed_propagation"]
seeds_n = np.array([50, 500, 5000])
latency = np.array([e8[str(s)]["latency_ms"][0] for s in seeds_n])          # seed 42 == tab:largeseed
hold = np.array([mean(e8[str(s)]["hold_size"]) for s in seeds_n])
fig, ax = plt.subplots(figsize=(3.5, 2.5))
ax.plot(seeds_n, latency, ms=5, **line("trkg"))
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Seed records")
ax.set_ylabel("Propagation latency (ms)")
ax.set_title("Propagation latency vs. seed set size (100K corpus)")
slope = np.polyfit(np.log10(seeds_n), np.log10(latency), 1)[0]
ax.text(0.05, 0.92, f"Empirical scaling exponent: {slope:.2f}",
        transform=ax.transAxes, fontsize=8, va="top")
for x, y, h in zip(seeds_n, latency, hold):
    ax.annotate(f"{h:,.0f} held", (x, y), textcoords="offset points",
                xytext=(7, -9), fontsize=7)
save(fig, "fig6_propagation_vs_seeds")
report["fig6"] = {"seeds": seeds_n.tolist(),
                  "latency_ms": [round(float(v), 2) for v in latency],
                  "hold": [round(float(h)) for h in hold],
                  "exponent": round(float(slope), 2)}

# ---- Figure 8: propagation policies (tab:propagation) -----------------------
# Canonical source: results.json e2_propagation (10K, 50 seeds, depth 10).
e2 = R["e2_propagation"]
e2_keys = ["None (Siloed)", "Attachment", "Thread", "Att + Thread",
           "+ Derivation", "All types"]
configs = ["Siloed", "Att", "Thread", "Att+Thread", "+Deriv", "All"]
base = mean(e2["None (Siloed)"]["final_counts"])
final = [round(mean(e2[k]["final_counts"])) for k in e2_keys]
final_sd = [round(sd(e2[k]["final_counts"])) for k in e2_keys]
ratios = [mean(e2[k]["final_counts"]) / base for k in e2_keys]
fig, ax = plt.subplots(figsize=(3.5, 2.6))
bars = ax.bar(configs, final, yerr=final_sd, capsize=3,
              color=STYLE["trkg"]["color"], hatch=STYLE["trkg"]["hatch"],
              edgecolor="black", linewidth=0.5)
for b, r in zip(bars, ratios):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 6,
            f"{r:.2f}x", ha="center", fontsize=7.5)
ax.set_ylabel("Hold set size")
ax.set_title("Propagation expansion by relationship policy")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
save(fig, "fig8_propagation_policies")
report["fig8"] = {"configs": configs, "final": final, "final_sd": final_sd,
                  "ratios": [round(r, 2) for r in ratios]}

# ---- Figure 9: performance vs baselines ------------------------------------
ops = ["Type query", "Hold propagation", "Temporal query"]
trkg_p = [3.1, 0.11, 1.0]
flat_p = [0.91, 13.5, 0.85]
sql_p = [1.6, 46.3, 2.0]
x = np.arange(len(ops))
w = 0.27
fig, ax = plt.subplots(figsize=(3.5, 2.6))
ax.bar(x - w, trkg_p, w, label="T-RKG", color="#1f4e79", hatch="",
       edgecolor="black", linewidth=0.5)
ax.bar(x, flat_p, w, label="Flat list", color="#c4641c", hatch="//",
       edgecolor="black", linewidth=0.5)
ax.bar(x + w, sql_p, w, label="SQLite", color="#a02828", hatch="xx",
       edgecolor="black", linewidth=0.5)
ax.set_xticks(x)
ax.set_xticklabels(ops)
ax.set_yscale("log")
ax.set_ylabel("Latency (ms, log)")
ax.set_title("Performance vs. flat / relational baselines (10K records)")
ax.legend(loc="upper right")
save(fig, "fig9_perf_baselines")

# ---------------------------------------------------------------- value report
print("=" * 70)
print("PLOTTED VALUES (data-driven figures) — for MANIFEST value-match")
print("=" * 70)
for name, vals in report.items():
    print(f"\n## {name}")
    for k, v in vals.items():
        if isinstance(v, list) and v and isinstance(v[0], float):
            print(f"  {k}: {[round(x, 3) for x in v]}")
        else:
            print(f"  {k}: {v}")

print("\nAll figures saved to", OUT)
