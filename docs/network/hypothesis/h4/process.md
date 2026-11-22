# H4 · Faisable par construction (Dicke par ligne + mixer XY) : process

> Process commun : [`../../workflow.md`](../../workflow.md).

- **Hypothèse :** h4 ([`hypothesis.md`](../../hypothesis.md), section H4)
- **Branche @ commit de base :** `network/h4-dicke-xy` @ `ef81b23`
- **Date :** 2026-11-22

## 1. Objectif

À couches, shots et nombre de circuits égaux, le QAOA Dicke-XY (`h4_qaoa_dicke`) donne une masse
d'échantillons valides (E1, avant repair) au moins 10 fois celle du QAOA à pénalités du notebook
(`h4_qaoa_penalty`) sur network05 (et network06), et une plus grande probabilité des topologies
optimales (`p_opt`) sur network05, seeds 0, 1, 2.

## 2. Implémentation

| Composant | Fichier (`src/network-experiments/h4/…`) | Rôle |
|---|---|---|
| `DickeRowsState` | `circuits.py` | ⊗ \|D₂^{(m)}⟩ sur des blocs de qubits contigus (`DickeState` de Divi, Bärtschi 2019, composé par bloc) |
| `row_blocks`, `row_xy_mixer` | `circuits.py` | Blocs de lignes (ligne i = qubits `i(n−1) … i(n−1)+n−2`) et mixer XY intra-ligne (`build_block_xy_mixer_edges` + `xy_mixer`) |
| `DickeRowsProblem` | `circuits.py` | `BinaryOptimizationProblem` avec mixer XY par ligne et état initial `DickeRowsState` (modèle : portefeuille de Divi) |
| `in_degree_penalty`, `out_degree_penalty` | `circuits.py` | `Σ (deg − 2)²` entrants / sortants |
| `qaoa_dicke`, `qaoa_dicke_bqm`, `qaoa_penalty` | `sampling.py` | QAOA (MonteCarloOptimizer), toute la distribution (`get_top_solutions(n=0)`) → `QAOABatch` |
| `feasibility_metrics`, `all_valid_scores` | `metrics.py` | E1, `outdeg_mass`, `p_opt`, `rank_best`, `n_distinct` ; cache des 216 topologies de network05 (`results/network/testsets/network05_all.json`) |
| `h4_qaoa_dicke`, `h4_qaoa_penalty`, `h4_rows_q`, `h4_rows_sa` | `methods.py` | Méthodes au format du harnais h0 |
| CLI | `run.py` | `python -m h4.run …` via `h0.harness.run_method("h4", …)` |
| Tests | `tests/test_h4.py` | Uniformité Dicke, conservation du poids par XY, ordre des bits, network05, boucle SA |

Choix et paramètres principaux :
- **Mixer en anneau** (`connectivity="ring"`) : O(m) arêtes par ligne au lieu de O(m²) (11 contre 55 sur
  network12), circuits moins profonds ; même choix que le portefeuille de Divi et que le service de
  caractérisation. Chaque arête applique `exp(−iβ(XX+YY)/2)` (XX et YY commutent sur une paire), donc la
  trotterisation conserve exactement le poids de chaque ligne (vérifié par test).
- Coût Dicke = objectif du kit (`qt.build_network_qubo`) + λ·pénalité des degrés entrants ; coût pénalités
  = objectif + λ·(entrants + sortants), mixer X, superposition. Les deux BQM sont normalisés (max |coeff|
  = 1) avant QAOA. λ = 1, p = 2, population 20, 10 itérations, 10 000 shots par défaut.
- Méthodes à un appel : top-K = 100 échantillons par probabilité → `qt.repair_topology` → LP.
- Boucle par blocs (`h4_rows_*`) : r = 2 lignes par bloc, solution courante aléatoire valide
  (`rng(seed)`), BQM conditionné (autres lignes fixées), top-K blocs → assemblage → repair → LP, la
  meilleure topologie devient courante ; balayages jusqu'au budget. SA : `dwave` 100 lectures sur le même
  BQM + λ·pénalité des degrés sortants.

Papiers suivis : Hadfield 2019, Wang 2020 (mixers XY), Bärtschi 2019 (Dicke), Onah 2025.

## 3. Évaluation

| Étape | Instance | Seeds | Méthodes lancées |
|---|---|---|---|
| Vérification | network05 | 0 | `h4_qaoa_dicke`, `h4_qaoa_penalty` (p = 1, 2) |
| Évaluation faisabilité | network05 | 0, 1, 2 | `h4_qaoa_dicke`, `h4_qaoa_penalty` (p = 1, 2) |
| Évaluation faisabilité | network06 (30 qubits, **cloud**) | 0, 1, 2 | idem |
| Passage à l'échelle | network12 | 0, 1, 2 | `h4_rows_q` (blocs de 22 qubits), `h4_rows_sa` (ablation) |

- **Budgets :** `metrics.md` §2 (network12 : 5 000 LP / 10 min).
- **Critères de succès :**

  | Critère | Mesure |
  |---|---|
  | **Faisabilité** | médiane E1(`h4_qaoa_dicke`) ≥ 10 × médiane E1(`h4_qaoa_penalty`) sur network05 et network06 |
  | Qualité de l'échantillonnage | `p_opt`(Dicke) > `p_opt`(pénalités) sur network05, 3 seeds sur 3 |
  | Passage à l'échelle | médiane Q1(`h4_rows_q`) < médiane Q1(`h4_rows_sa`) sur network12 (règle de gain) |

- **Décision :** si le critère de faisabilité échoue sur network05, on s'arrête (ni network06 ni network12).
- **Commande :** `PYTHONPATH=src/network-experiments uv run python -m h4.run --instance network05 --seed 0 1 2 --method h4_qaoa_dicke`

## 4. Écarts au plan

- 2026-11-22 : les blocs de network12 (`h4_rows_q`, 22 qubits) peuvent tourner sur le cloud (`--cloud`)
  pour décharger le CPU local, déjà occupé par d'autres runs ; les blocs de 3 lignes (33 qubits) exigent
  le cloud (`--cloud --mps-bond-dim 32`). Le passage au cloud n'est jamais automatique : en local, un bloc
  de plus de 24 qubits lève une erreur.
- 2026-11-22 : les BQM de coût sont normalisés avant QAOA (comme le PCE de H1), pour que les angles du
  MonteCarloOptimizer aient la même échelle dans les deux méthodes.
