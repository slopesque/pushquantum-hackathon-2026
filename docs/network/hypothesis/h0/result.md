# H0 · Baseline minimale : résultats

> Chaque chiffre provient de `results/network/bench/h0/*.jsonl` (définitions dans
> [`metrics.md`](../../metrics.md)). Process suivi : [`process.md`](process.md).

- **Branche @ commit des runs :** `network/h0-baseline` @ `778ca20`
- **Date :** 2026-11-21
- **Conclusion :** **Validée**. B0 et B1 sont mesurés au budget standard sur network05 (seed 0) et
  network12 (seeds 0, 1, 2), et le jeu de test figé de network12 existe.

## 1. Résumé

B0 (topologies aléatoires) et B1 (SA sur le substitut du kit, puis repair, puis LP) tournent au budget de
`metrics.md` §2. Sur network12, à 5 000 LP, **B1 a une médiane de 302 316 (+9,35 %)** et B0 de 317 215
(+14,74 %). Avec le budget complet, B1 fait nettement mieux que le repère à 100 lectures (+12,0 %) : c'est
cette médiane que H1 doit battre.

## 2. Résultats

Budget : `metrics.md` §2 (network05 : 500 LP / 2 min ; network12 : 5 000 LP / 10 min).

| Instance | Méthode | min (gap) | médiane (gap) | max | lp_calls | wall_time_s | max_qubits | backend |
|---|---|---|---|---|---|---|---|---|
| network05 | b0_random (seed 0) | 65 500 (+0,00 %) | — | — | 216 | 4,0 | 0 | none |
| network05 | b1_sa_kit (seed 0) | 65 500 (+0,00 %) | — | — | 151 | 20,0 | 0 | none |
| network12 | b0_random | 316 858 (+14,61 %) | 317 215 (+14,74 %) | 320 480 | 5 000 | 76,4 | 0 | none |
| network12 | b1_sa_kit | 298 858 (+8,10 %) | **302 316 (+9,35 %)** | 304 556 | 5 000 | 99,6 | 0 | none |

Par seed sur network12 (score) : B0 = 316 858 / 320 480 / 317 215 ; B1 = 298 858 / 302 316 / 304 556
(seeds 0 / 1 / 2).

Métriques spécifiques :
- **E1 `feasible_mass` de B1 :** 0,9994 / 0,9992 / 0,9994 sur network12, 1,0 sur network05. Avec une
  pénalité de poids 1, presque toutes les lectures SA sont déjà valides : le repair ne sert presque pas.
- **Jeu de test figé :** `results/network/testsets/network12.json`, 1 000 topologies (500 aléatoires avec
  `default_rng(12345)`, 500 B1 avec la seed 12345), aucune topologie non routable.
- Agrégats reproduits par `PYTHONPATH=src/network-experiments uv run python -m h0.report --hypothesis h0 --instance network12`.

## 3. Critères de succès

| Critère | Valeur mesurée | Atteint ? |
|---|---|---|
| B1 retrouve l'optimum de network05 (test pytest) | 65 500 | ✅ |
| B0 et B1 enregistrés sur network05 et network12 (seeds 0, 1, 2) | 2 + 6 lignes JSONL | ✅ |
| Jeu de test figé network12 | 1 000 topologies | ✅ |
| B0 et B1 sur network24 | lancés pendant la consolidation de H1 | ⏳ non testé |

## 4. Solution rendue

| Instance | Score | Gap | Qubits max | `.sol` | Méthode et seed |
|---|---|---|---|---|---|
| network05 | 65 500 | 0,00 % | 0 | `results/network/20261121T215730Z_network05.sol` | b0_random, seed 0 |
| network12 | 298 858 | +8,10 % | 0 | `results/network/20261121T215731Z_network12.sol` | b1_sa_kit, seed 0 (sa_reads 100, pénalité 1) |

Les deux fichiers sont validés par `qt.check_network_solution` (score égal à Q1) avant `save_run`.

## 5. Analyse et suite

- B1 bat B0 nettement (règle de gain : médiane plus basse et 3 seeds sur 3 sous la médiane de B0). Le
  substitut du kit oriente donc bien la recherche, même s'il ignore le routage sur plusieurs sauts.
- B1 n'utilise que ≈ 51 lots SA de 100 lectures pour 5 000 LP : presque chaque lecture donne une
  topologie nouvelle. Le budget LP est donc le facteur limitant, pas le SA.
- Durée : environ 100 s par run B1 sur network12 (LP ≈ 6 ms, plus le SA).
- Suite : H1 (substitut appris) doit battre la médiane B1 de **302 316** sur network12.
