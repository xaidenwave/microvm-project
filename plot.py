#!/usr/bin/env python3
"""Generate presentation charts for the microVM project.

Run from ~/microvm-project:   python3 plot.py
Reads:  logs/b1_main.json, logs/b1_console.json, logs/b2_guest_init.csv, logs/b1_t1.txt
Writes: charts/*.png
"""
import csv
import json
import re
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# B3 / B4 values, entered by hand from logs/b3_vmm_overhead.txt and logs/b4_*.txt
# Check these against your own logs before presenting.
# ---------------------------------------------------------------------------
RSS_MB = {                       # host RSS of one running instance (ps rss / 1024)
    "T1 Traditional VM\n(1024 MB guest)": 506404 / 1024,
    "T2 QEMU microvm\n(128 MB guest)": 116488 / 1024,
    "T3 Firecracker\n(128 MB guest)": 48488 / 1024,
    "T4 Container\n(sleep + conmon)": (249.9 + 2252) / 1024,
}
N_VMS = 20
B4 = {  # free -m "used" values in MB, and KSM general_profit in bytes
    "T2": {"baseline": 3346, "running": 4746, "profit_bytes": 540152576},
    "T3": {"baseline": 3375, "running": 4272, "profit_bytes": 0},
}

# ---------------------------------------------------------------------------
LOGS, OUT = Path("logs"), Path("charts")
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "figure.figsize": (11, 6), "figure.dpi": 100, "savefig.dpi": 200,
    "font.size": 15, "axes.titlesize": 19, "axes.titleweight": "bold",
    "axes.labelsize": 15, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "axes.axisbelow": True,
})
C = {"T1": "#9e9e9e", "T2": "#1f77b4", "T3d": "#f4a261", "T3": "#e76f51",
     "T4": "#2a9d8f", "a": "#264653", "b": "#e9c46a", "c": "#8ab17d", "d": "#bc4749"}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT / name)


def label_bars(ax, bars, fmt, errs=None):
    errs = errs or [0] * len(bars)
    for b, e in zip(bars, errs):
        ax.annotate(fmt(b.get_height()), (b.get_x() + b.get_width() / 2, b.get_height() + e),
                    ha="center", va="bottom", fontsize=13, xytext=(0, 4),
                    textcoords="offset points")


# --- load data --------------------------------------------------------------
def hyperfine(path):
    return {r["command"]: r for r in json.load(open(path))["results"]}

b1 = hyperfine(LOGS / "b1_main.json")
b1c = hyperfine(LOGS / "b1_console.json")

guest = {}
with open(LOGS / "b2_guest_init.csv") as f:
    for row in csv.DictReader(f):
        guest.setdefault(row["tier"], []).append(float(row["guest_init_s"]))

t1 = {"booted": [], "total": [], "kernel": [], "initrd": [], "userspace": [], "systemd": []}
for line in open(LOGS / "b1_t1.txt"):
    if m := re.search(r"booted_after=([\d.]+)s", line):
        t1["booted"].append(float(m[1]))
    if m := re.search(r"total=([\d.]+)s", line):
        t1["total"].append(float(m[1]))
    if m := re.search(r"in ([\d.]+)s \(kernel\) \+ ([\d.]+)s \(initrd\) \+ "
                      r"([\d.]+)s \(userspace\) = ([\d.]+)s", line):
        for k, v in zip(["kernel", "initrd", "userspace", "systemd"], m.groups()):
            t1[k].append(float(v))
mean = {k: st.mean(v) for k, v in t1.items()}
sd_booted = st.stdev(t1["booted"]) if len(t1["booted"]) > 1 else 0

# --- 1. boot latency, all tiers (log scale) ---------------------------------
names = ["T1 Traditional\nVM", "T2 QEMU\nmicrovm", "T3 Firecracker\ndefault",
         "T3 Firecracker\ntuned", "T4 Podman\ncontainer"]
keys = [None, "T2 QEMU microvm", "T3 Firecracker default", "T3 Firecracker tuned",
        "T4 Podman container"]
means = [mean["booted"] * 1000] + [b1[k]["mean"] * 1000 for k in keys[1:]]
errs = [sd_booted * 1000] + [b1[k]["stddev"] * 1000 for k in keys[1:]]
fig, ax = plt.subplots()
bars = ax.bar(names, means, yerr=errs, capsize=6,
              color=[C["T1"], C["T2"], C["T3d"], C["T3"], C["T4"]])
ax.set_yscale("log")
ax.set_ylabel("Time to boot (ms, log scale)")
ax.set_title("Boot latency: traditional VM vs microVMs vs container")
label_bars(ax, bars, lambda v: f"{v/1000:.2f} s" if v >= 1000 else f"{v:.0f} ms", errs)
ax.set_ylim(50, max(means) * 3)
ax.text(0.99, 0.97, "T1: 5 runs, time to BOOTED\nOthers: 30 runs, full boot + shutdown",
        transform=ax.transAxes, ha="right", va="top", fontsize=11, color="#555")
save(fig, "chart_boot.png")

# --- 2. microVM breakdown: guest kernel vs everything else ------------------
rows = [("T2 QEMU microvm", "T2", "T2 QEMU microvm"),
        ("T3 Firecracker tuned", "T3_tuned", "T3 Firecracker tuned")]
g = [st.mean(guest[k]) * 1000 for _, k, _ in rows]
tot = [b1[k]["mean"] * 1000 for _, _, k in rows]
rest = [t - x for t, x in zip(tot, g)]
fig, ax = plt.subplots(figsize=(11, 4.5))
lbl = [r[0] for r in rows]
ax.barh(lbl, g, color=C["c"], label="Guest kernel boot (to /init)")
ax.barh(lbl, rest, left=g, color=C["a"], label="VMM start, kernel load, init, shutdown")
for i, (x, r, t) in enumerate(zip(g, rest, tot)):
    ax.text(x / 2, i, f"{x:.1f}", ha="center", va="center", color="black", fontsize=13)
    ax.text(x + r / 2, i, f"{r:.1f}", ha="center", va="center", color="white", fontsize=13)
    ax.text(t + 2, i, f"{t:.1f} ms", va="center", fontsize=13)
ax.invert_yaxis()
ax.set_xlabel("Milliseconds")
ax.set_xlim(0, max(tot) * 1.18)
ax.set_title("Where microVM boot time goes (same kernel, same rootfs)")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=12, frameon=False)
ax.grid(axis="y", visible=False)
save(fig, "chart_breakdown_microvm.png")

# --- 3. T1 breakdown ---------------------------------------------------------
pre = mean["booted"] - mean["systemd"]
parts = [("QEMU + SeaBIOS + GRUB", pre, C["d"]), ("Kernel", mean["kernel"], C["a"]),
         ("initrd", mean["initrd"], C["b"]), ("Userspace (systemd)", mean["userspace"], C["c"])]
fig, ax = plt.subplots(figsize=(11, 4.6))
left = 0
for name, v, col in parts:
    ax.barh(["T1 Traditional VM"], [v], left=left, color=col, label=f"{name}: {v:.2f} s")
    ax.text(left + v / 2, 0, f"{v:.1f}s", ha="center", va="center", fontsize=13,
            color="white" if col in (C["a"], C["d"]) else "black")
    left += v
ax.set_xlabel("Seconds")
ax.set_title(f"Traditional VM boot breakdown (mean of {len(t1['booted'])} runs, "
             f"total {mean['booted']:.2f} s)")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=2, fontsize=12, frameon=False)
ax.grid(axis="y", visible=False)
save(fig, "chart_breakdown_t1.png")

# --- 4. serial console cost --------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))
x = [0, 1]
w = 0.36
verb = [b1c["T2 verbose"]["mean"] * 1000, b1c["T3 tuned verbose"]["mean"] * 1000]
quiet = [b1c["T2 quiet"]["mean"] * 1000, b1c["T3 tuned quiet"]["mean"] * 1000]
b_v = ax.bar([i - w / 2 for i in x], verb, w, color=C["d"], label="Verbose console",
             yerr=[b1c["T2 verbose"]["stddev"] * 1000, b1c["T3 tuned verbose"]["stddev"] * 1000],
             capsize=5)
b_q = ax.bar([i + w / 2 for i in x], quiet, w, color=C["c"], label="quiet",
             yerr=[b1c["T2 quiet"]["stddev"] * 1000, b1c["T3 tuned quiet"]["stddev"] * 1000],
             capsize=5)
label_bars(ax, list(b_v) + list(b_q), lambda v: f"{v:.0f} ms",
           [b1c[k]["stddev"] * 1000 for k in ("T2 verbose", "T3 tuned verbose", "T2 quiet",
                                               "T3 tuned quiet")])
ax.set_xticks(x, ["T2 QEMU microvm", "T3 Firecracker tuned"])
ax.set_ylabel("Boot + shutdown (ms)")
ax.set_ylim(0, max(verb) * 1.2)
ax.set_title("Cost of printing boot messages to the serial console")
ax.legend()
save(fig, "chart_console.png")

# --- 5. host memory per instance (log scale) --------------------------------
fig, ax = plt.subplots()
bars = ax.bar(list(RSS_MB), list(RSS_MB.values()),
              color=[C["T1"], C["T2"], C["T3"], C["T4"]])
ax.set_yscale("log")
ax.set_ylabel("Host memory, RSS (MB, log scale)")
ax.set_title("Host memory used by one running instance")
label_bars(ax, bars, lambda v: f"{v:.0f} MB" if v >= 10 else f"{v:.1f} MB")
ax.set_ylim(1, max(RSS_MB.values()) * 3)
ax.text(0.99, 0.97, "Container excludes the shared host kernel",
        transform=ax.transAxes, ha="right", va="top", fontsize=11, color="#555")
save(fig, "chart_memory.png")

# --- 6. density with KSM -----------------------------------------------------
per_off = {t: (d["running"] - d["baseline"]) / N_VMS for t, d in B4.items()}
per_on = {t: per_off[t] - d["profit_bytes"] / 2**20 / N_VMS for t, d in B4.items()}
fig, ax = plt.subplots(figsize=(10, 6))
x = [0, 1]
b_off = ax.bar([i - w / 2 for i in x], [per_off["T2"], per_off["T3"]], w,
               color=C["T1"], label="KSM off")
b_on = ax.bar([i + w / 2 for i in x], [per_on["T2"], per_on["T3"]], w,
              color=C["a"], label="KSM on (60 s)")
label_bars(ax, list(b_off) + list(b_on), lambda v: f"{v:.0f} MB")
ax.set_xticks(x, ["T2 QEMU microvm", "T3 Firecracker"])
ax.set_ylabel("Host memory per VM (MB)")
ax.set_ylim(0, max(per_off.values()) * 1.25)
ax.set_title(f"Memory per VM with {N_VMS} identical VMs, before and after KSM")
ax.legend()
saved = B4["T2"]["profit_bytes"] / 2**20
ax.text(0.99, 0.80, f"T2: KSM saved {saved:.0f} MB total\nT3: 0 MB (memory not marked mergeable)",
        transform=ax.transAxes, ha="right", va="top", fontsize=12, color="#333")
save(fig, "chart_ksm.png")

# --- summary for the slides ------------------------------------------------
print("\nSummary")
print(f"  T1 time to BOOTED: {mean['booted']:.2f} s ± {sd_booted:.2f} "
      f"(pre-kernel {pre:.2f} s)")
for (lbl_, _, _), gg, tt in zip(rows, g, tot):
    print(f"  {lbl_}: guest {gg:.1f} ms, rest {tt - gg:.1f} ms, total {tt:.1f} ms")
for t in B4:
    print(f"  {t}: {per_off[t]:.1f} MB/VM without KSM, {per_on[t]:.1f} MB/VM with KSM")
