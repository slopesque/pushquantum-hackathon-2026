# H2 · Substitut analytique enrichi (chemins à 2 sauts) et réglage de λ : process

> Process commun : [`../../workflow.md`](../../workflow.md).

- **Hypothèse :** h2 ([`hypothesis.md`](../../hypothesis.md#h2--substitut-analytique-enrichi-chemins-à-2-sauts-et-réglage-de-λ))
- **Branche @ commit de base :** `network/h2-physics-surrogate` @ `ef81b23`
- **Date :** 2026-11-22

## 1. Objectif

À budget LP égal, `h2_sa_phys` (SA sur le substitut H2 `−α Σ t_ij x_ij − β₂ Σ t_ik x_ij x_jk (+ γ)`)
obtient une médiane de Q1 inférieure à B1 sur network12 (seeds 0, 1, 2), et le substitut H2 ordonne
mieux les topologies que le kit (F1, F2, F3). Option : `h2_fm_phys` bat `h1_sa_fm`.

## 2. Implémentation

| Composant | Fichier (`src/network-experiments/h2/…`) | Rôle |
|---|---|---|
| Substitut H2 | `surrogate.py` | `physics_objective(demand, alpha, beta2, gamma)` (BQM normalisé à max\|coeff\| = 1, offset 0), `physics_qubo(…, lam)` (+ λ·pénalité du kit), `lambda_rule(obj, rule)` |
| Diagnostics | `diagnostics.py` | `f1_f2_testset` (F1, F2 sur `testsets/network12.json`), `enumerate_valid_topologies(n)` (216 sur network05), `f3_ref_percentile` (cache LP `testsets/network05_all.json`) |
| Méthodes | `methods.py` | `h2_sa_phys` (pipeline B1 sur H2), `h2_fm_phys` (boucle H1, a priori H2), `METHODS` |
| CLI runs | `run.py` | `python -m h2.run …` via `h0.harness.run_method("h2", …)` |
| Réglage sans LP | `tune.py` | `python -m h2.tune --grid` : (α, β₂, γ) → F1, F2, F3, λ des règles |
| Characterization | `characterize.py` | Divi Characterization Service (cloud) sur objectif H2 + contraintes de degré, λ = 1 ; ligne dans `results/network/bench/h2/characterization.jsonl` |
| Tests | `tests/test_h2.py` | kit retrouvé (β₂ = 0), normalisation, pénalité nulle sur topologie valide, 216 topologies, 65 500 sur network05, budget de `h2_fm_phys`, crochet h1 |

Choix :
- **Terme γ** (équilibrage, 0 par défaut) : `+γ Σ_j Σ_{i<i'} t_ij t_i'j x_ij x_i'j` (arcs entrants d'un
  même nœud) + même terme sur les arcs sortants ; pénalise deux arcs lourds qui se partagent un nœud.
- **Règles de λ** (`lambda_rule`) :
  - `unit` : 1 (kit, B1) ;
  - `ayodele` = **MOC** d'Ayodele 2022 (arXiv 2206.11040, éq. 19) : `max(1, max_i W_i(C)/W_i(G))`, avec
    `W_i(M) = max(−M_ii − Σ_j min(M_ij,0), M_ii + Σ_j max(M_ij,0))` (variation max en basculant x_i) ;
    aussi disponibles : `momc` (éq. 18) et `vlm` (Verma & Lewis 2020) ;
  - `broesamle` : Broesamle et al. 2026 (arXiv 2602.10951, Théorème 2) : `P > Σ|c_i|` pour un objectif
    linéaire et des pénalités entières ≥ 1 ; **étendu** au quadratique par `Σ|lin| + Σ|quad|` ;
  - λ recommandé par la Characterization Service (network05 ; network08 laissé au coordinateur).

Papiers suivis : Ayodele 2022, Broesamle 2026, Rezk 2026 (écart entre coefficients), Alessandroni 2025.

## 3. Évaluation

| Étape | Instance | Seeds | Méthodes lancées |
|---|---|---|---|
| Vérification | network05 | 0 | `h2_sa_phys` (test : 65 500) |
| Réglage | network12 | 0 | `h2.tune --grid` (sans LP), puis `h2_sa_phys` pour λ ∈ {1, ayodele, broesamle, characterization} |
| Évaluation | network12 | 0, 1, 2 | `h2_sa_phys` (5 000 LP), puis `h2_fm_phys` (rang 8, lr 0,003, l2 1e-2, β = 0,5, λ = 1) + B0, B1, `h1_sa_fm` |
| Consolidation | network24 (sinon network20, puis network16) | 0, 1, 2 | méthodes gagnantes à l'étape 3 + baselines, 10 000 LP, `--time-limit 5400` |

- **Budgets :** `metrics.md` §2.
- **Critères de succès** (network12, seeds 0, 1, 2) :
  - le substitut ordonne mieux : F1(H2) ≥ F1(kit) + 0,1 sur le jeu de test, et F3(H2) meilleur que
    F3(kit) sur network05 ;
  - **principal** : médiane Q1(`h2_sa_phys`) < médiane Q1(B1), et ≥ 2 seeds sur 3 sous la médiane de B1 ;
  - λ réglé : E1 ≥ E1 à λ = 1, sans dégrader Q1 ;
  - **option H1 + H2** : médiane Q1(`h2_fm_phys`) < médiane Q1(`h1_sa_fm`), même règle, sur network12
    puis network24.
- **Commande :** `PYTHONPATH=src/network-experiments uv run python -m h2.run --instance network12 --seed 0 1 2 --method h2_sa_phys --beta2 1.0 --lam 2`

## 4. Écarts au plan

- 2026-11-22 : **crochet h1** (seule modification hors `h2/`) : `h1.fm.learned_qubo(…, prior_bqm=None)`
  et `h1.loop.h1_fm(…, prior=None)` avec `prior = {"fn": "h2.surrogate:physics_objective", "kwargs": {…}}`
  (import dynamique, JSON-sérialisable). Par défaut (None) : objectif du kit, comportement H1 inchangé
  (tests h1 verts).
- 2026-11-22 : consolidation network24 avec `--time-limit 5400` (c'est le budget LP qui arrête le run).
- 2026-11-22 : règles λ implémentées : `unit`, `ayodele` (= MOC), `momc`, `vlm`, `broesamle` (extension
  quadratique de la borne linéaire). MOC vaut 1 (plancher `max(1, ·)`) sur nos objectifs normalisés :
  la règle d'Ayodele ne se distingue pas de λ = 1. La borne Broesamle est très grande (32 à 400 selon
  β₂, γ sur network12) : à tester, mais probablement trop plate pour SA.
- 2026-11-22 : F3(kit) = 0 % sur network05 (l'optimum est déjà l'état fondamental du kit, 1 ex aequo) :
  « F3 meilleur que le kit » ne peut être atteint qu'en supprimant l'ex aequo (β₂ ≤ 0,25).
