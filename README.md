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

Au-delà de 48 cas, les graphes sont découpés par taille d'instance (`gap_by_case_a050_t10.png`…). Les
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

| Problème | Instance | Variables | Qubits max | Score | Best known | Gap | Run |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
