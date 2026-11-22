"""Network figure: gap to best known (median, min-max over 3 seeds), template colours of the slides.

Scores recopiés de docs/network/hypothesis/{h0,h1,h2}/result.md (branche network/main).
Lancer : uv run python formalisations/network/figures/make_figures.py
"""

from pathlib import Path

import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "DejaVu Sans"
import numpy as np

BEST = {"network12": 276_474, "network24": 663_688}
SCORES = {  # méthode -> instance -> scores des seeds 0, 1, 2
    "B0 random": {"network12": [316_858, 320_480, 317_215], "network24": [781_448, 793_534, 788_125]},
    "B1 kit QUBO + SA": {"network12": [298_858, 302_316, 304_556], "network24": [735_228, 744_980, 749_821]},
    "H1 learned": {"network12": [285_625, 283_900, 284_313], "network24": [731_261, 740_667, 737_450]},
    "H2 2-hop": {"network12": [295_273, 290_750, 291_800], "network24": [732_674, 739_182, 733_286]},
    "H1 + H2": {"network12": [282_625, 282_556, 279_667], "network24": [722_459, 737_685, 733_638]},
}
COLORS = ["#CBD5E1", "#94A3B8", "#16A34A", "#0F766E", "#14532D"]

fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=False)
for ax, inst in zip(axes, ("network12", "network24")):
    names = list(SCORES)
    gaps = [100 * (np.array(SCORES[m][inst]) - BEST[inst]) / BEST[inst] for m in names]
    med = [np.median(g) for g in gaps]
    err = [[m - g.min() for m, g in zip(med, gaps)], [g.max() - m for m, g in zip(med, gaps)]]
    x = np.arange(len(names))
    ax.bar(x, med, color=COLORS, yerr=err, capsize=3, ecolor="#333333")
    for xi, m, g in zip(x, med, gaps):
        label = f"{m:.2f} %"
        ax.text(xi, g.max() + 0.3, label, ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x, names, rotation=20, ha="right", fontsize=8)
    lp = "5,000" if inst == "network12" else "10,000"
    ax.set_title(f"{inst} ({lp} LP)", fontsize=10)
    ax.set_ylabel("gap to best known (%)", fontsize=8)
    ax.set_ylim(0, max(np.max(g) for g in gaps) * 1.18)
    ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
out = Path(__file__).with_name("gap_medians.png")
fig.savefig(out, dpi=200)
print(out)
