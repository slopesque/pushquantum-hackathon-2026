# Métriques d'évaluation des hypothèses : network design (QOBLIB 08)

> Référentiel **obligatoire** pour évaluer toute hypothèse de [`hypothesis.md`](hypothesis.md). Chaque
> métrique a un identifiant (par ex. `Q2`), une définition exacte, une façon de la calculer, une unité et
> une clé JSON. Deux runs ne sont comparables que s'ils utilisent ces définitions **et** le même budget
> (§2).

## 1. Unité de mesure : le *run*

Un **run** est l'exécution d'une méthode sur un triplet (instance, seed, budget). On rapporte toujours
**5 seeds (0, 1, 2, 3, 4)** par couple (méthode, instance). Toutes les sources d'aléa sont initialisées
depuis la seed : `numpy.random.default_rng(seed)`, `seed=` des samplers dimod, `seed=` des programmes
Divi.

Chaque run écrit **une ligne JSON** dans `results/network/bench/<id>/<méthode>.jsonl` (`<id>` = `h0`…`h9`,
voir [`workflow.md`](workflow.md)), avec les clés de la §6.
Un run qui produit un résultat rendable appelle aussi `save_run(...)` (`.sol` et `.json`).

## 2. Budgets standard (comparaison à budget égal)

Le budget principal est le **nombre d'appels au LP** (métrique `C1`), qui ne dépend pas de la machine.
On fixe aussi un **plafond de temps** (`C2`) pour éviter les runs interminables. Le run s'arrête dès que
l'un des deux est atteint.

| Instance | n | Variables | Budget LP (`C1`) | Plafond temps | Temps d'un LP (mesuré) |
|---|---:|---:|---:|---:|---:|
| `network05` | 5 | 20 | 2 000 | 2 min | < 5 ms |
| `network08`, `network10` | 8, 10 | 56, 90 | 10 000 | 10 min | ~ 10 ms |
| `network12` | 12 | 132 | 20 000 | 15 min | 12 ms |
| `network16` | 16 | 240 | 20 000 | 20 min | 19 ms |
| `network20` | 20 | 380 | 30 000 | 40 min | ~ 40 ms |
| `network24` | 24 | 552 | 30 000 | 40 min | 65 ms |

Temps mesurés en 2026-11 sur la machine de dev, médiane de 5 topologies aléatoires
(`qt.route_min_congestion`). 30 000 LP sur network24 prennent environ 33 min, soit l'ordre de grandeur du
run de 40 min de Gupta.

**Règles :**
- On ne compare deux méthodes **qu'à budget LP égal**, sinon on doit le signaler explicitement.
- Les appels au quantique ont leur propre budget (`C3`, `C4`), toujours rapporté à part, jamais converti
  en appels LP.
- Le budget LP compte **tout** ce qui appelle le LP, y compris le post-traitement (recherche locale,
  repair puis score).

## 3. Catalogue des métriques

### Q. Qualité de la solution

| Id | Clé JSON | Définition exacte | Calcul | Unité |
|---|---|---|---|---|
| Q1 | `score` | Meilleur score officiel parmi toutes les topologies **valides** évaluées pendant le run | `min qt.route_min_congestion(demand, arcs).objective` sur les arcs qui vérifient `qt.is_valid_topology`. Pour un `.sol` rendu : `qt.check_network_solution(...)[1]`, qui **doit être égal** à Q1 | entier, 1/1000 d'unité de flot |
| Q2 | `gap` | Écart relatif au meilleur connu | `hackathon.utils.gap(score, best_known)` = (Q1 − best_known)/\|best_known\|. Rapporter en % avec 3 décimales | % (négatif = record battu) |
| Q3 | `best_known` | Meilleur connu QOBLIB de l'instance | Table QOBLIB 08 (voir §7) | entier |
| Q4 | `hit_target` | Le run a-t-il atteint le seuil ? | `score <= best_known * (1 + eps)` pour eps ∈ {0, 0.001, 0.01}. Stocker un dict `{"0": bool, "0.001": bool, "0.01": bool}` | booléens |
| Q5 | `best_arcs` | Topologie qui donne Q1 | Liste triée de paires `[i, j]`, indexées à partir de 0 | — |

### C. Coût et budget

| Id | Clé JSON | Définition exacte | Calcul | Unité |
|---|---|---|---|---|
| C1 | `lp_calls` | Nombre de **résolutions LP effectives** : appels qui exécutent réellement `linprog`, donc sans les hits de cache | Compteur du scorer de H0, incrémenté à chaque défaut de cache | entier |
| C1b | `lp_queries` | Nombre total de demandes de score, hits de cache compris | Compteur du scorer | entier |
| C2 | `wall_time_s` | Temps écoulé du début de la méthode à la fin du run (chargement des données exclu, post-traitement inclus) | `time.perf_counter()` | secondes, 1 décimale |
| C3 | `n_circuits` | Nombre total de circuits exécutés par tous les programmes quantiques du run | Somme de `program.total_circuit_count` (QAOA, PCE) ou `ensemble.total_circuit_count`. Vaut 0 sans quantique | entier |
| C3b | `shots_total` | Nombre total de shots | Σ (circuits × shots par circuit) | entier |
| C4 | `credits_used` | Crédits cloud consommés | Solde avant moins solde après (`QoroService().get_credit_balance()`). Vaut 0 en local | crédits |
| C5 | `backend` | Où ont tourné les circuits | `"none"`, `"maestro_local"` ou `"qoro_cloud"` | chaîne |
| C6 | `lp_calls_to_target` | Appels LP effectifs au moment où le seuil eps est atteint **pour la première fois** | Dict `{eps: int ou null}` pour eps ∈ {0, 0.001, 0.01}, calculé depuis `trajectory` | entier ou `null` |
| C7 | `time_to_target_s` | Même chose que C6, en temps | Dict `{eps: float ou null}` | secondes |
| C8 | `trajectory` | Courbe d'amélioration | Liste de `[lp_calls, wall_time_s, score]`, avec un point **à chaque amélioration de Q1** et un point final | — |

### S. Échelle

| Id | Clé JSON | Définition exacte | Calcul | Unité |
|---|---|---|---|---|
| S1 | `n_vars` | Taille officielle de l'instance | n(n−1). Ne change pas avec l'encodage choisi | entier |
| S2 | `n_vars_model` | Variables binaires du modèle réellement optimisé | `len(bqm.variables)`, ou nombre de variables du HUBO. Diffère de S1 pour H5 et pour les sous-problèmes | entier |
| S3 | `max_qubits` | Qubits du **plus gros** programme quantique exécuté | `max(p.n_qubits)` sur tous les programmes. Pour un ensemble : `max(p.n_qubits for p in ensemble.programs.values())`. Vaut 0 sans quantique | entier |
| S4 | `n_programs` | Nombre de programmes quantiques distincts exécutés | Compteur | entier |
| S5 | `max_depth` | Profondeur du plus gros circuit, après transpilation sur `["cx", "rz", "sx", "x"]` | `qiskit.transpile(circ, basis_gates=[...]).depth()` sur un circuit représentatif | entier |

### E. Qualité de l'échantillonnage (méthodes qui produisent des échantillons)

Ces métriques ne s'appliquent qu'aux méthodes qui génèrent des bitstrings : SA, QAOA, PCE, ensembles.

| Id | Clé JSON | Définition exacte | Calcul | Unité |
|---|---|---|---|---|
| E1 | `feasible_mass` | Probabilité qu'un échantillon brut soit **valide avant repair** | QAOA/PCE : Σ des probabilités des bitstrings valides (`qt.is_valid_topology(n, qt.decode_topology(b, arcs))`). SA : fraction des lectures valides | [0, 1] |
| E2 | `feasible_unique_rate` | Fraction des bitstrings **distincts** qui sont valides | nb distincts valides / nb distincts | [0, 1] |
| E3 | `n_distinct_valid` | Topologies valides distinctes **après repair** | `len({frozenset(qt.repair_topology(n, decode(b), demand))})` | entier |
| E4 | `repair_hamming_mean` | Ampleur moyenne de la réparation | Moyenne sur les échantillons bruts de \|arcs bruts Δ arcs réparés\| (différence symétrique) | arcs |
| E5 | `score_raw` | Meilleur score **sans recherche locale** : échantillons → repair → LP | Comme Q1, en ignorant toute passe de 2-exchanges ou toute recherche locale classique postérieure | entier |
| E6 | `score_after_ls` | Meilleur score **après** la recherche locale classique, si elle est utilisée | Q1 du run complet | entier |
| E7 | `p_opt` | (`network05` à `network10` seulement) Probabilité d'échantillonner une topologie optimale | Σ des probabilités des bitstrings dont la topologie, après repair, a un score égal à `best_known` | [0, 1] |
| E8 | `rank_best` | (`network05` seulement) Rang de la meilleure topologie trouvée parmi **toutes** les topologies valides | 1 + nombre de topologies valides de score strictement inférieur. L'énumération est celle du notebook de référence §1 | entier, 1 = optimum |

**Règle :** pour toute méthode qui utilise une recherche locale classique, **rapporter E5 et E6**. Le
gain attribuable à l'échantillonneur se lit sur E5, pas sur E6.

### F. Qualité d'un substitut (H1, H2, et tout nouveau QUBO)

On mesure ces métriques sur un **jeu de test figé** par instance : 1 000 topologies uniformes
(`qt.random_topology`, `rng = default_rng(12345)`) et 1 000 topologies tirées des trajectoires de B2
(seed 12345, un point toutes les k améliorations), avec leur score LP. Le jeu est sauvegardé une fois
dans `results/network/testsets/networkNN.json` (clés `arcs` et `score`) puis **réutilisé tel quel**. Le
jeu de test ne doit jamais servir à l'entraînement.

| Id | Clé JSON | Définition exacte | Calcul | Unité |
|---|---|---|---|---|
| F1 | `spearman_rho` | Corrélation de rang entre l'énergie du substitut (pénalités exclues, topologies valides) et le score LP | `scipy.stats.spearmanr(energies, scores).statistic` | [−1, 1], plus haut = mieux |
| F2 | `top10_precision` | Fraction des 10 % meilleures topologies selon le substitut qui sont aussi dans les 10 % meilleures selon le LP | \|top10%(substitut) ∩ top10%(LP)\| / taille du top 10 % | [0, 1] (hasard ≈ 0,10) |
| F3 | `ref_percentile` | Position de la meilleure topologie connue (ou optimale) dans la distribution d'énergie du jeu de test | % des topologies du jeu qui ont une énergie **strictement inférieure** à celle de la référence | %, 0 = la référence est la plus basse |
| F4 | `char_ref_rank` | (Optionnel, cloud) Rang de la topologie de référence dans le spectre du QUBO selon la Characterization Service | Champ `references[0]` du rapport `characterize_and_validate` | selon le rapport |

### A. Attribution et significativité

| Id | Clé JSON | Définition exacte | Calcul |
|---|---|---|---|
| A1 | `ablation_method` | Nom de la variante classique **identique en tout sauf le composant quantique** (remplacé par SA, par un tirage uniforme ou par la variante déquantisée) | Chaîne. Obligatoire pour toute méthode quantique |
| A2 | `delta_median_vs_ablation` | Médiane(Q1 méthode) − Médiane(Q1 ablation), sur 5 seeds, à budget LP égal | Négatif = le quantique aide |
| A3 | `p_value_vs_ablation` | Test de Mann-Whitney unilatéral sur les 5 + 5 valeurs de Q1 (H₁ : la méthode est meilleure) | `scipy.stats.mannwhitneyu(m, abl, alternative="less").pvalue`. Avec 5 contre 5, p minimal ≈ 0,004 |
| A4 | `delta_median_vs_B2`, `p_value_vs_B2` | Même chose contre la baseline B2 (parallel tempering) | Comme A2 et A3 |

## 4. Agrégation sur les seeds

Pour chaque couple (méthode, instance), on rapporte dans `docs/network/hypothesis/<id>/result.md` :

| Statistique | Définition |
|---|---|
| `best` | min de Q1 sur les 5 seeds, avec le `gap` associé |
| `median` | médiane de Q1, avec le gap associé (**c'est la statistique de comparaison principale**) |
| `worst` | max de Q1 |
| `hit@eps` | nombre de seeds où Q4[eps] est vrai, noté par exemple « 3/5 » |
| `median_lp_calls_to_target` | médiane de C6 à eps = 0,01 (les seeds non atteintes comptent comme +∞) |
| `median_wall_time_s` | médiane de C2 |
| `max_qubits` | max de S3 |
| `credits_total` | somme de C4 |

## 5. Règles de décision (statut d'une hypothèse)

Une hypothèse passe à l'un des statuts suivants **sur la base de ces métriques uniquement** :

| Statut | Condition |
|---|---|
| **Validée** | Les critères de succès de l'hypothèse sont atteints. **En plus**, pour toute affirmation de gain quantique : A2 < 0 **et** A3 < 0,05 sur au moins une instance n ≥ 12 |
| **Invalidée** | Le critère principal n'est pas atteint et A2 ≥ 0 (pas de gain mesurable) sur toutes les instances testées |
| **Non concluante** | Gain observé mais A3 ≥ 0,05, ou budget non respecté, ou moins de 5 seeds |

On ne compare jamais deux méthodes sur une seule seed. On ne compare jamais E6 d'une méthode à E5 d'une
autre.

## 6. Schéma JSON d'un run

Une ligne par run dans `results/network/bench/<id>/<méthode>.jsonl`. Les mêmes clés vont dans le `metadata` de
`save_run` (qui ajoute `gap`, `git`, `timestamp` et `sol_file`).

```json
{
  "hypothesis": "H7",
  "method": "qls_2exchange_variantA",
  "ablation_method": "ls_2exchange_uniform",
  "instance": "network16",
  "seed": 0,
  "params": {"n_layers": 2, "mc_population": 50, "mc_iterations": 10, "shots": 10000},
  "budget": {"lp_calls": 20000, "time_s": 1200},
  "n_vars": 240, "n_vars_model": 240, "max_qubits": 11, "n_programs": 400, "max_depth": 87,
  "score": 401234, "best_known": 397908, "gap": 0.00836,
  "hit_target": {"0": false, "0.001": false, "0.01": true},
  "best_arcs": [[0, 3], [0, 7]],
  "lp_calls": 20000, "lp_queries": 35120, "wall_time_s": 812.4,
  "n_circuits": 20000, "shots_total": 200000000, "credits_used": 0, "backend": "maestro_local",
  "lp_calls_to_target": {"0": null, "0.001": null, "0.01": 15320},
  "time_to_target_s": {"0": null, "0.001": null, "0.01": 640.2},
  "trajectory": [[1, 0.1, 520000], [15320, 640.2, 401234], [20000, 812.4, 401234]],
  "feasible_mass": null, "feasible_unique_rate": null, "n_distinct_valid": 9800,
  "repair_hamming_mean": null, "score_raw": 401234, "score_after_ls": 401234,
  "p_opt": null, "rank_best": null,
  "spearman_rho": null, "top10_precision": null, "ref_percentile": null
}
```

Une métrique non applicable vaut `null`, jamais 0. (`best_arcs` est tronqué dans l'exemple ; un vrai run
en contient 2n.)

## 7. Meilleurs connus (`best_known`, table QOBLIB au 2026-11)

| Instance | best_known | Statut |
|---|---:|---|
| network05 | 65 500 | optimal |
| network06 | 101 000 | optimal |
| network07 | 142 400 | optimal |
| network08 | 170 231 | optimal |
| network09 | 196 750 | optimal |
| network10 | 210 800 | optimal |
| network11 | 238 334 | best known |
| network12 | 276 474 | best known |
| network13 | 300 620 | best known |
| network14 | 343 091 | best known |
| network15 | 370 870 | best known |
| network16 | 397 908 | best known |
| network17 | 437 000 | best known |
| network18 | 473 375 | best known |
| network19 | 492 924 | best known |
| network20 | 528 528 | best known |
| network21 | 569 273 | best known |
| network22 | 618 135 | best known |
| network23 | 659 369 | best known |
| network24 | 663 688 | best known |

Vérifier les mises à jour sur la [table QOBLIB](https://github.com/ZIB-AOPT/QOBLIB/blob/main/08-network/solutions/README.md)
avant toute conclusion.
