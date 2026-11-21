# Métriques : network design (QOBLIB 08), profil hackathon

> Métriques à mesurer pour évaluer H0 et H1 (et les hypothèses ajoutées plus tard). Elles sont
> volontairement peu nombreuses : chacune a une définition exacte et une clé JSON. Deux runs ne sont
> comparables que s'ils utilisent **la même instance, le même budget et les mêmes seeds**.

## 1. Run, seeds et agrégation

- Un **run** exécute une méthode sur une instance avec une seed et un budget.
- Toutes les sources d'aléa sont initialisées depuis la seed : `numpy.random.default_rng(seed)`, `seed=`
  des samplers et des programmes Divi.
- **Seeds :** **0** pour explorer ; **0, 1, 2** pour évaluer et consolider.
- **Agrégation sur les 3 seeds :** médiane, min et max de Q1, avec leur gap.
  - **On compare les méthodes sur la médiane.**
  - **On rend le meilleur** `.sol` (le min).
- **Règle de gain :** la méthode A bat la méthode B si la médiane de A est inférieure à celle de B
  **et** si au moins 2 seeds de A sur 3 sont sous la médiane de B. Il n'y a pas de test statistique : avec
  3 seeds, aucun test ne peut descendre sous p = 0,05.

## 2. Budgets

Le budget principal est le **nombre de résolutions LP** (C1), car il ne dépend pas de la machine. Un
plafond de temps évite les runs interminables. On s'arrête au premier des deux atteint.

Le budget dépend de la taille de l'instance (n nœuds, n(n−1) variables) :

| Tranche | Instances | Budget LP | Plafond de temps | Temps d'un LP (mesuré) |
|---|---|---:|---:|---:|
| A | `network05` à `network08` | 500 | 2 min | < 5 ms |
| B | `network09` à `network12` | 5 000 | 10 min | 12 ms (network12) |
| C | `network13` à `network18` | 8 000 | 20 min | 19 ms (network16) |
| D | `network19` à `network24` | 10 000 | 30 min | 65 ms (network24) |

Le budget de chaque instance est dans la table du §5.

**Instance de consolidation.** La cible est `network24`. Si elle est hors de portée (temps, mémoire,
qubits), on prend **la plus grosse instance qui passe**, en descendant dans cet ordre :
`network24` → `network20` → `network16`. On peut aussi viser n'importe quelle instance de la table du
§5, avec le budget de sa tranche. On indique l'instance retenue et la raison dans `result.md`.

**Le budget LP compte tout :** les données d'entraînement, les candidats de la boucle et la recherche
locale éventuelle. Les circuits quantiques ont leur propre compteur (C3), rapporté à part.

## 3. Catalogue

| Id | Clé JSON | Définition | Calcul | Quand |
|---|---|---|---|---|
| **Q1** | `score` | Meilleur score officiel parmi les topologies **valides** évaluées | min de `qt.route_min_congestion(demand, arcs).objective`. Pour un `.sol` rendu, `qt.check_network_solution(...)[1]` doit être égal à Q1 | Toujours |
| **Q2** | `gap` | Écart relatif au meilleur connu | `hackathon.utils.gap(score, best_known)`, en % avec 2 décimales | Toujours |
| Q3 | `best_known` | Meilleur connu QOBLIB | Table du §5 | Toujours |
| **C1** | `lp_calls` | Résolutions LP effectives, sans les hits de cache | Compteur du scorer de H0 | Toujours |
| C2 | `wall_time_s` | Temps du run, sans le chargement des données | `time.perf_counter()` | Toujours |
| C3 | `n_circuits` | Circuits quantiques exécutés | Somme de `program.total_circuit_count` (0 sans quantique) | Si quantique |
| C4 | `backend` | Où ont tourné les circuits | `"none"`, `"maestro_local"` ou `"qoro_cloud"` (avec les crédits consommés dans `params`) | Toujours |
| S1 | `n_vars` | Taille de l'instance | n(n−1) | Toujours |
| **S2** | `max_qubits` | Qubits du plus gros programme quantique | `max(p.n_qubits)` sur les programmes exécutés (0 sans quantique) | Toujours |
| E1 | `feasible_mass` | Part des échantillons bruts **valides avant repair** | Fraction des lectures (SA) ou somme des probabilités (PCE, QAOA) vérifiant `qt.is_valid_topology` | Si échantillonneur |
| **E5** | `score_raw` | Meilleur score **sans recherche locale** : échantillons, repair, LP | Comme Q1, en ignorant la passe de 2-exchanges | Si recherche locale |
| E6 | `score_after_ls` | Meilleur score **après** la recherche locale | Q1 du run complet | Si recherche locale |
| **F1** | `spearman_rho` | Corrélation de rang entre l'énergie du QUBO (pénalités exclues) et le score LP, sur le jeu de test | `scipy.stats.spearmanr(energies, scores).statistic` | Si nouveau QUBO (H1) |
| F2 | `top10_precision` | Part des 10 % meilleures topologies selon le QUBO qui sont aussi dans les 10 % meilleures selon le LP | Intersection divisée par la taille du top 10 % (hasard ≈ 0,10) | Si nouveau QUBO (H1) |

**Règle E5 / E6 :** dès qu'une recherche locale classique est utilisée, on rapporte les deux. Le gain dû à
l'échantillonneur (quantique ou appris) se lit sur **E5**.

**Jeu de test figé (F1, F2).** Il est fixé une seule fois par H0 pour `network12`, puis réutilisé tel quel :
- 500 topologies `qt.random_topology` (avec `default_rng(12345)`) ;
- 500 topologies issues de B1 (seed 12345), pour couvrir les bonnes régions ;
- leur score LP.

Il est sauvegardé dans `results/network/testsets/network12.json` (clés `arcs` et `score`). Il ne sert
**jamais** à l'entraînement.

## 4. Schéma JSON d'un run

Une ligne par run dans `results/network/bench/<id>/<méthode>.jsonl`. Les mêmes clés vont dans le
`metadata` de `save_run`. Une métrique non applicable vaut `null`.

```json
{
  "hypothesis": "h1", "method": "h1_sa_fm", "instance": "network12", "seed": 0,
  "params": {"fm_rank": 8, "lambda": 2.0, "sa_reads": 100, "n0": 1000},
  "budget": {"lp_calls": 5000, "time_s": 600},
  "score": 281000, "best_known": 276474, "gap": 0.0164,
  "lp_calls": 5000, "wall_time_s": 95.3, "n_circuits": 0, "backend": "none",
  "n_vars": 132, "max_qubits": 0,
  "feasible_mass": 0.12, "score_raw": null, "score_after_ls": null,
  "spearman_rho": 0.61, "top10_precision": 0.34
}
```

## 5. Instances disponibles et meilleurs connus (table QOBLIB au 2026-11)

Les 20 instances QOBLIB 08 sont `network05` à `network24`. On les charge avec
`qt.load_network_demand(n)`, et le `.sol` se nomme `network<NN>.sol`.

| Instance | n | Variables n(n−1) | best_known | Statut | Tranche (§2) | Budget LP | Rôle |
|---|---:|---:|---:|---|---|---:|---|
| network05 | 5 | 20 | 65 500 | optimal | A | 500 | **Vérification** |
| network06 | 6 | 30 | 101 000 | optimal | A | 500 | |
| network07 | 7 | 42 | 142 400 | optimal | A | 500 | |
| network08 | 8 | 56 | 170 231 | optimal | A | 500 | |
| network09 | 9 | 72 | 196 750 | optimal | B | 5 000 | |
| network10 | 10 | 90 | 210 800 | optimal | B | 5 000 | |
| network11 | 11 | 110 | 238 334 | best known | B | 5 000 | |
| network12 | 12 | 132 | 276 474 | best known | B | 5 000 | **Réglage et évaluation** |
| network13 | 13 | 156 | 300 620 | best known | C | 8 000 | |
| network14 | 14 | 182 | 343 091 | best known | C | 8 000 | |
| network15 | 15 | 210 | 370 870 | best known | C | 8 000 | |
| network16 | 16 | 240 | 397 908 | best known | C | 8 000 | Consolidation, 2ᵉ repli |
| network17 | 17 | 272 | 437 000 | best known | C | 8 000 | |
| network18 | 18 | 306 | 473 375 | best known | C | 8 000 | |
| network19 | 19 | 342 | 492 924 | best known | D | 10 000 | |
| network20 | 20 | 380 | 528 528 | best known | D | 10 000 | Consolidation, 1ᵉʳ repli |
| network21 | 21 | 420 | 569 273 | best known | D | 10 000 | |
| network22 | 22 | 462 | 618 135 | best known | D | 10 000 | |
| network23 | 23 | 506 | 659 369 | best known | D | 10 000 | |
| network24 | 24 | 552 | 663 688 | best known | D | 10 000 | **Consolidation (cible)** |

Avant toute conclusion, vérifier les mises à jour sur la
[table QOBLIB](https://github.com/ZIB-AOPT/QOBLIB/blob/main/08-network/solutions/README.md).
