# PushQuantum × Qoro Hackathon 2026

Optimisation de QUBO partitionnés avec [Divi](https://github.com/QoroQuantum/divi) sur deux problèmes
du benchmark [QOBLIB](https://github.com/ZIB-AOPT/QOBLIB) : optimisation de portefeuille (06) et
network design (08).

## Setup

```bash
uv sync                    # Python 3.12 + dépendances (dev incluses)
cp .env.example .env       # puis y mettre sa QORO_API_KEY (https://dash.qoroquantum.net)
uv run pytest              # tests : notre modèle face à l'arbitre, évaluateur, banc d'essai
uv run marimo edit notebooks/   # ou : uv run jupyter lab
```

Sans clé API, tout tourne sur le simulateur local (Maestro).

Contexte du hackathon, structure du repo, conventions : voir [`AGENTS.md`](AGENTS.md).
Kit original de Qoro (notebooks + arbitre) : [`references/`](references/README.md).

## Portefeuille : mesurer une méthode

Toutes les méthodes se comparent avec le même banc d'essai, qui produit tableaux et graphes.

```bash
# Lancer : méthodes × jeu de cas × seeds, avec une limite de temps par exécution
uv run scripts/bench_portfolio.py --set dev --methods empty ls --seeds 3 --time 10 --label essai

# Garder les meilleures solutions : validées par l'arbitre officiel puis enregistrées dans results/portfolio/
uv run scripts/bench_portfolio.py --set a400 --methods ls --save-sol

# Retracer un run, ou en superposer plusieurs dans les mêmes graphes
uv run scripts/plot_portfolio_bench.py results/portfolio/bench/<run>
uv run scripts/plot_portfolio_bench.py results/portfolio/bench/<run1> results/portfolio/bench/<run2> \
    --out results/portfolio/bench/compare --label "run1 vs run2"
```

| Option | Rôle | Défaut |
|---|---|---|
| `--set` | Jeu de cas : `dev` (12), `a010`, `a050`, `known` (128, avec meilleur connu), `large` (128, a200 + a400), `a400` (8), `full` (256) | `dev` |
| `--methods` | Une ou plusieurs méthodes enregistrées (voir ci-dessous) | `empty` |
| `--seeds` | Nombre de seeds par cas (0, 1, …) | 3 |
| `--time` | Limite de temps par exécution, en secondes | 10 |
| `--label` | Nom du run (dossier, titres des graphes) | méthodes + jeu |
| `--save-sol` | Valide la meilleure solution de chaque cas avec l'arbitre et l'enregistre | non |
| `--no-plot` | Pas de graphes | non |

**Sorties**, dans `results/portfolio/bench/<date>_<label>/` :

| Fichier | Contenu |
|---|---|
| `runs.csv` | Une ligne par exécution : cas, méthode, seed, score, faisabilité, meilleur connu, gap, temps |
| `summary.md` | Par cas et par méthode : meilleur score, médiane, gaps, exécutions faisables, temps moyen |
| `meta.json` | Arguments, commit git, durée totale |
| `gap_by_case.png` | Gap de chaque méthode, cas par cas (meilleure seed) |
| `gap_vs_lambda.png` | Gap en fonction de λ, un panneau par instance |
| `time_by_case.png` | Temps moyen par exécution (échelle log) |
| `size_vs_time.png` | **Taille de l'instance en fonction du temps** : un point par exécution, symbole = méthode, couleur = λ |
| `size_vs_gap.png` | **Taille de l'instance en fonction du gap** : un point par exécution, symbole = méthode, couleur = λ |

**Voir l'effet de chaque optimisation : tous les runs sur un seul graphe.** Chaque méthode est une
configuration d'optimisations (`ls-single` → `ls-block` → `ls-pair` → `ls-full`…) et garde sa couleur et son
symbole ; la couleur donne λ, du bleu clair (λ = 0) au bleu foncé (λ = 1e-2). Chaque point est une
exécution : on voit le nuage d'une méthode se déplacer quand on ajoute une optimisation, et pour quels λ :

```bash
uv run scripts/plot_portfolio_bench.py --all    # → results/portfolio/bench/all/size_vs_{time,gap}.png
```

`--all` réunit tous les runs de `results/portfolio/bench/` ; si un même cas a été exécuté plusieurs fois
(même instance, λ, méthode et seed), seule l'exécution la plus récente compte. Sur le graphe de gap, un cas
sans meilleur connu n'apparaît que si au moins deux méthodes y ont tourné.

Au-delà de 48 cas, les autres graphes sont découpés par taille d'instance (`gap_by_case_a050_t10.png`…). Les
PNG ne sont pas commités : ils se régénèrent depuis `runs.csv`.

**Le gap** vaut `(score − meilleur connu) / |meilleur connu|` : 0 = égalité, négatif = record battu. Les
meilleurs connus viennent de la table QOBLIB (a010 et a050). Pour a200 et a400, où rien n'est publié, les
graphes se rapportent au meilleur score trouvé par les méthodes comparées (cas marqués †).

**Méthodes disponibles** (`src/hackathon/solvers/portfolio/methods.py`) :

| Méthode | Principe |
|---|---|
| `empty` | Ne rien détenir : repère plancher (score −100 × jours) |
| `ls-single` | Recherche locale, mouvements ±1 sur une case : l'équivalent de celle du kit |
| `ls-block` | + changements sur des blocs de jours consécutifs |
| `ls-pair` | + paires couvertes (actions corrélées ou anti-corrélées) sur des blocs de jours |
| `ls-full` | + échanges d'une unité entre deux actions (budget saturé) : la meilleure à ce jour sur a010/a050 |
| `ls-full-b20` | `ls-full` en appliquant 20 mouvements par passe : bien plus rapide, meilleure sur a400 |

**Ajouter une méthode** : une fonction `(problème, rng, limite de temps) → solution` enregistrée par un
décorateur dans `methods.py`. Elle devient aussitôt utilisable avec `--methods`.

```python
from hackathon.solvers.portfolio.benchmark import register

@register("ma-methode")
def ma_methode(problem, rng, time_limit):
    v = ...  # tableau (T, n) d'entiers dans {-3..3}, faisable
    return v
```

Détails (fonctionnement, conventions) : `AGENTS.md`, section *Benchmarks*, et
`formalisations/portfolio/pistes.typ`, piste P3.

## Résultats

Meilleures solutions rendues, validées par l'arbitre officiel. « — » : aucun meilleur connu publié (nous sommes
les premiers sur ces instances). Méthodes classiques pour l'instant : 0 qubit.

| Problème | Instance | λ | Variables (QUBO / entières) | Qubits max | Score | Meilleur connu | Gap | Méthode | Fichier |
|---|---|---|---|---|---:|---|---|---|---|
| Portefeuille | `po_a400_t15_orig` (B = 100) | 0 | 36 165 / 6 000 | 0 | −4 194 749 | — | — | `ls-full-b20` | [`20261121T165941Z_…`](results/portfolio/20261121T165941Z_po_a400_t15_orig_b100_l0.sol) |
| Portefeuille | `po_a400_t15_orig` (B = 100) | 1e-6 | 36 165 / 6 000 | 0 | −4 147 927 | — | — | `ls-full-b20` | [`20261121T165958Z_…`](results/portfolio/20261121T165958Z_po_a400_t15_orig_b100_l1e-6.sol) |
| Portefeuille | `po_a400_t15_orig` (B = 100) | 1e-5 | 36 165 / 6 000 | 0 | −3 898 367 | — | — | `ls-full-b20` | [`20261121T170016Z_…`](results/portfolio/20261121T170016Z_po_a400_t15_orig_b100_l1e-5.sol) |
| Portefeuille | `po_a400_t15_orig` (B = 100) | 5e-5 | 36 165 / 6 000 | 0 | −3 553 299 | — | — | `ls-full-b20` | [`20261121T170033Z_…`](results/portfolio/20261121T170033Z_po_a400_t15_orig_b100_l5e-5.sol) |
| Portefeuille | `po_a400_t15_orig` (B = 100) | 1e-4 | 36 165 / 6 000 | 0 | −3 406 114 | — | — | `ls-full-b20` | [`20261121T170050Z_…`](results/portfolio/20261121T170050Z_po_a400_t15_orig_b100_l1e-4.sol) |
| Portefeuille | `po_a400_t15_orig` (B = 100) | 5e-4 | 36 165 / 6 000 | 0 | −3 049 528 | — | — | `ls-full-b20` | [`20261121T170107Z_…`](results/portfolio/20261121T170107Z_po_a400_t15_orig_b100_l5e-4.sol) |
| Portefeuille | `po_a400_t15_orig` (B = 100) | 1e-3 | 36 165 / 6 000 | 0 | −2 797 435 | — | — | `ls-full-b20` | [`20261121T170124Z_…`](results/portfolio/20261121T170124Z_po_a400_t15_orig_b100_l1e-3.sol) |
| Portefeuille | `po_a400_t15_orig` (B = 100) | 1e-2 | 36 165 / 6 000 | 0 | −374 851 | — | — | `ls-full-b20` | [`20261121T170141Z_…`](results/portfolio/20261121T170141Z_po_a400_t15_orig_b100_l1e-2.sol) |

Chaque `.sol` a un `.json` à côté (méthode, paramètres, seed, commit git) ; le benchmark qui l'a produit est
dans `results/portfolio/bench/20261121T165825Z_p4-a400/`. Sur les instances avec meilleur connu (a010, a050), la
recherche locale `ls-full` égale le meilleur connu sur 63 des 128 cas et s'en approche à moins de 1 % sur 95
(`results/portfolio/bench/20261121T165623Z_p4-known/summary.md`).
