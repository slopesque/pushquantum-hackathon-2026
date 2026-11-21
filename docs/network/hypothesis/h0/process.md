# H0 · Baseline minimale : process

> Copié depuis le modèle [`../_template/process.md`](../_template/process.md) **avant de coder**. Process
> commun : [`../../workflow.md`](../../workflow.md).

- **Hypothèse :** h0 ([`hypothesis.md`](../../hypothesis.md))
- **Branche @ commit de base :** `network/h0-baseline` @ `caf9153`
- **Date :** 2026-11-21

## 1. Objectif

Enregistrer B0 (`b0_random`) et B1 (`b1_sa_kit`) sur network05 (seed 0) et network12 (seeds 0, 1, 2), au
budget de `metrics.md` §2. Figer le jeu de test de network12 (`metrics.md` §3).

## 2. Implémentation

| Composant | Fichier (`src/network-experiments/h0/…`) | Rôle |
|---|---|---|
| Instances | `instances.py` | Meilleurs connus et budgets par tranche (`metrics.md` §2 et §5) |
| Scorer | `scorer.py` | LP mémoïsé sur `frozenset(arcs)`, compteur `lp_calls`, budget LP et plafond de temps, exception `BudgetExhausted` |
| Harnais | `harness.py` | `run_method` : une ligne JSONL (`metrics.md` §4) avec `best_arcs` et `git`. `save_solution` : `qt.route_integral`, `qt.write_network_solution`, `qt.check_network_solution`, puis `save_run` |
| Baselines | `baselines.py` | `b0_random`, `b1_sa_kit`, `b1_topologies` (générateur de topologies B1, réutilisé par le jeu de test) |
| CLI | `run.py` | Lance une méthode sur une instance et une liste de seeds |
| Rapport | `report.py` | Agrégats Markdown (médiane, min, max, gap) depuis les JSONL |
| Sauvegarde | `save_best.py` | Prend le record de score minimal (clé `best_arcs` du JSONL) et l'enregistre via `harness.save_solution`, sans relancer de run |
| Jeu de test | `testset.py` | Écrit `results/network/testsets/network12.json` |
| Tests | `tests/test_h0.py` | B1 retrouve 65 500 sur network05 |

Choix et paramètres principaux : B1 reprend le pipeline du kit (notebook §1.3). Il utilise
`qt.build_network_qubo`, une pénalité de poids 1, `SimulatedAnnealingSampler` par lots de 100 lectures,
puis `repair_topology`, puis le scorer. B0 tire des `qt.random_topology`. Les deux s'arrêtent au budget LP.
Papiers suivis : aucun (pipeline du kit).

## 3. Évaluation

| Étape | Instance | Seeds | Méthodes lancées |
|---|---|---|---|
| Vérification | network05 | 0 | `b0_random`, `b1_sa_kit` |
| Réglage | network12 | 0 | aucune : pas de paramètre à régler (pénalité 1, 100 lectures, comme le kit) |
| Évaluation | network12 | 0, 1, 2 | `b0_random`, `b1_sa_kit` |
| Consolidation | network24 (sinon network20, puis network16) | 0, 1, 2 | `b0_random`, `b1_sa_kit`, lancés pendant la consolidation de H1 |

- **Budgets :** `metrics.md` §2.
- **Critères de succès :** B0 et B1 sur network05 et network12 (seeds 0, 1, 2) sont enregistrés et
  résumés dans `docs/network/hypothesis/h0/result.md`. B0 et B1 sur network24 ne sont lancés qu'à la
  consolidation de H1.
- **Commande :** `PYTHONPATH=src/network-experiments uv run python -m h0.run --instance network12 --seed 0 1 2 --method b1_sa_kit`

## 4. Écarts au plan

- **2026-11-21 · Graine des lots SA.** Graine du lot = seed·1 000 003 + b, au lieu de seed + b. Sinon les
  seeds 0, 1 et 2 partagent leurs lots.
- **2026-11-21 · B0 sur network05.** network05 n'a que 216 topologies valides. B0 s'arrête donc avant
  500 LP : une garde anti-boucle coupe le run quand les tirages ne donnent plus que des hits de cache.
- **2026-11-21 · Plafond de temps.** Le scorer lève `BudgetExhausted` dès que le plafond de temps est
  atteint, même sur un hit de cache.
- **2026-11-21 · Temps d'un LP.** Le LP mesuré sur network12 prend environ 6 ms, et non 12 ms
  (`metrics.md` §2).
- **2026-11-21 · Repair des lectures valides.** Une lecture SA déjà valide n'est pas envoyée au MILP de
  `repair_topology` (elle est son propre repair) ; les autres repairs sont mémoïsés. Même résultat, 16× plus rapide.
- **2026-11-21 · Arrêt de B1.** B1 s'arrête aussi après 20 lots consécutifs sans topologie nouvelle
  (cas de network05, environ 150 LP).
