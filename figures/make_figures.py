"""Render the paper figures (PNG @300 DPI + PDF) from the experiment outputs."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))

# IEEE single-column width: ~3.5 in.
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"{name}.png"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(OUT, f"{name}.pdf"), bbox_inches="tight")
    plt.close(fig)


# Figure 2: conflict detection vs. dataset scale.
scales = np.array([1000, 5000, 10000, 25000, 50000, 100000])
trkg_total = np.array([55, 249, 468, 1087, 2296, 4672])
trkg_total_sd = np.array([8, 47, 36, 169, 267, 254])
trkg_xdom  = np.array([4, 60, 99, 195, 425, 831])
trkg_xdom_sd = np.array([8, 21, 33, 38, 37, 42])
siloed_total = np.array([52, 180, 344, 868, 1803, 3693])
siloed_xdom = np.zeros_like(scales)
noont_total = np.array([150, 750, 1500, 3750, 7500, 15000])
noont_xdom = np.zeros_like(scales)

fig, ax = plt.subplots(figsize=(3.5, 2.6))
ax.errorbar(scales, trkg_total, yerr=trkg_total_sd, marker="o", lw=1.2, ms=4,
            label="T-RKG total", color="#1f4e79")
ax.errorbar(scales, trkg_xdom, yerr=trkg_xdom_sd, marker="s", lw=1.2, ms=4,
            label="T-RKG cross-domain", color="#2e7d32")
ax.plot(scales, siloed_total, marker="^", lw=1.2, ms=4,
        label="Siloed total", color="#c4641c", linestyle="--")
ax.plot(scales, noont_total, marker="d", lw=1.2, ms=4,
        label="No-Ontology total", color="#a02828", linestyle=":")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Dataset size (records)")
ax.set_ylabel("Conflicts detected (log)")
ax.set_title("Conflict detection across scales (5 seeds, mean $\\pm$ $\\sigma$)")
ax.legend(loc="lower right", framealpha=0.85)
save(fig, "fig2_conflicts_vs_scale")

# Figure 3: cross-domain conflicts only.
fig, ax = plt.subplots(figsize=(3.5, 2.4))
x = np.arange(len(scales))
w = 0.27
ax.bar(x - w, trkg_xdom, w, yerr=trkg_xdom_sd, label="T-RKG", color="#1f4e79", capsize=2)
ax.bar(x,     siloed_xdom, w, label="Siloed", color="#c4641c")
ax.bar(x + w, noont_xdom, w, label="No-Ontology", color="#a02828")
ax.set_xticks(x)
ax.set_xticklabels([f"{s//1000}K" for s in scales], rotation=0)
ax.set_xlabel("Dataset size")
ax.set_ylabel("Cross-domain conflicts detected")
ax.set_title("Cross-domain conflicts: only T-RKG sees them")
ax.legend(loc="upper left")
save(fig, "fig3_cross_domain_bars")

# Figure 4: build throughput and conflict-detection latency vs. scale.
build_thr = np.array([71580, 66428, 61355, 54721, 50744, 48425])
conflict_ms = np.array([3.2, 16.1, 32.7, 84.8, 161, 319])

fig, ax1 = plt.subplots(figsize=(3.5, 2.5))
ax1.plot(scales, build_thr / 1000, marker="o", lw=1.2, ms=4, color="#1f4e79", label="Build throughput")
ax1.set_xlabel("Dataset size (records)")
ax1.set_xscale("log")
ax1.set_ylabel("Build throughput (K records / s)", color="#1f4e79")
ax1.tick_params(axis="y", labelcolor="#1f4e79")
ax1.set_ylim(0, 80)
ax2 = ax1.twinx()
ax2.plot(scales, conflict_ms, marker="s", lw=1.2, ms=4, color="#a02828", label="Conflict detection")
ax2.set_ylabel("Conflict detection (ms)", color="#a02828")
ax2.tick_params(axis="y", labelcolor="#a02828")
ax2.set_yscale("log")
ax2.grid(False)
ax1.set_title("Scalability: throughput and detection latency")
save(fig, "fig4_scalability")

# Figure 5: per-record applicability F1, clean vs noised.
systems = ["T-RKG", "Siloed", "No-Ontology"]
clean   = [1.000, 0.581, 0.113]
noised  = [0.823, 0.542, 0.113]
clean_sd = [0.000, 0.050, 0.009]
noised_sd = [0.011, 0.046, 0.009]

x = np.arange(len(systems))
w = 0.35
fig, ax = plt.subplots(figsize=(3.5, 2.5))
ax.bar(x - w/2, clean,  w, yerr=clean_sd,  capsize=3, label="Clean regime",   color="#1f4e79")
ax.bar(x + w/2, noised, w, yerr=noised_sd, capsize=3, label="10% noise regime", color="#a02828")
ax.set_xticks(x); ax.set_xticklabels(systems)
ax.set_ylabel("Per-record applicability F1")
ax.set_ylim(0, 1.1)
ax.set_title("Applicability F1: baseline gap and T-RKG robustness")
ax.legend(loc="upper right")
save(fig, "fig5_f1_clean_vs_noise")

# Figure 6: propagation latency vs. seed-set size.
seeds_n = np.array([50, 500, 5000])
latency = np.array([0.77, 2.6, 13.7])
latency_sd = np.array([0.43, 0.6, 0.6])

fig, ax = plt.subplots(figsize=(3.5, 2.4))
ax.errorbar(seeds_n, latency, yerr=latency_sd, marker="o", lw=1.2, ms=5, color="#1f4e79")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Seed records")
ax.set_ylabel("Propagation latency (ms)")
ax.set_title("Propagation latency vs. seed set size (100K corpus)")
log_seeds = np.log10(seeds_n); log_lat = np.log10(latency)
slope = np.polyfit(log_seeds, log_lat, 1)[0]
ax.text(0.05, 0.92, f"Empirical scaling exponent: {slope:.2f}",
        transform=ax.transAxes, fontsize=8, va="top")
save(fig, "fig6_propagation_vs_seeds")

# Figure 7: cross-domain conflicts vs. EU jurisdictional fraction.
eu_frac = np.array([5, 15, 30, 40])
xdom    = np.array([38, 83, 111, 135])
xdom_sd = np.array([35, 19, 35, 45])
multireg = np.array([232, 265, 275, 296])

fig, ax = plt.subplots(figsize=(3.5, 2.4))
ax.errorbar(eu_frac, xdom, yerr=xdom_sd, marker="o", lw=1.2, ms=5,
            color="#2e7d32", label="Cross-domain conflicts")
ax.plot(eu_frac, multireg, marker="s", lw=1.2, ms=5,
        color="#1f4e79", label="Records with $\\geq$ 2 regulations")
ax.set_xlabel("EU jurisdictional fraction (%)")
ax.set_ylabel("Count")
ax.set_title("Robustness: smooth scaling with EU fraction")
ax.legend(loc="lower right")
save(fig, "fig7_robustness_sweep")

# Figure 8: hold propagation by relationship configuration.
configs = ["Siloed", "Att", "Thread", "Att+Thread", "+Deriv", "All"]
final = [50, 97, 71, 168, 183, 213]
final_sd = [0, 14, 5, 36, 39, 54]
ratios = [1.00, 1.94, 1.42, 3.36, 3.65, 4.26]

fig, ax = plt.subplots(figsize=(3.5, 2.5))
bars = ax.bar(configs, final, yerr=final_sd, capsize=3, color="#1f4e79")
for b, r in zip(bars, ratios):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 6,
            f"{r:.2f}x", ha="center", fontsize=7.5)
ax.set_ylabel("Hold set size")
ax.set_title("Propagation expansion by relationship policy")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
save(fig, "fig8_propagation_policies")

# Figure 9: T-RKG vs. flat/relational baselines.
ops = ["Type query", "Hold propagation", "Temporal query"]
trkg_p   = [3.1, 0.11, 1.0]
flat_p   = [0.91, 13.5, 0.85]
sql_p    = [1.6, 46.3, 2.0]

x = np.arange(len(ops)); w = 0.27
fig, ax = plt.subplots(figsize=(3.5, 2.5))
ax.bar(x - w, trkg_p, w, label="T-RKG",   color="#1f4e79")
ax.bar(x,     flat_p, w, label="Flat list", color="#c4641c")
ax.bar(x + w, sql_p,  w, label="SQLite",  color="#a02828")
ax.set_xticks(x); ax.set_xticklabels(ops)
ax.set_yscale("log")
ax.set_ylabel("Latency (ms, log)")
ax.set_title("Performance vs. flat / relational baselines (10K records)")
ax.legend(loc="upper right")
save(fig, "fig9_perf_baselines")

print("All figures saved to", OUT)
print("Files:")
for f in sorted(os.listdir(OUT)):
    if f.startswith("fig"):
        print(" ", f)
