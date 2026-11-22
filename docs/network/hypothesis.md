# Hypothèses à expérimenter : network design (QOBLIB 08), profil hackathon

> Feuille de route **simplifiée** pour quelques heures de hackathon. On ne lance que deux chantiers :
> **H0**, une baseline minimale, puis **H1**, un substitut appris. Les autres pistes sont au
> [backlog](#backlog-hypothèses-reportées) et seront ajoutées selon l'avancée du benchmark.
> Les références viennent de [`state-of-the-art.md`](state-of-the-art.md). Les mesures et les budgets sont
> dans [`metrics.md`](metrics.md), le process dans [`workflow.md`](workflow.md).

## Profil hackathon en bref

| Élément | Choix |
|---|---|
| Instances | `network05` pour vérifier que le code est correct, `network12` pour régler et évaluer, `network24` (sinon `network20`, puis `network16`) **seulement en consolidation**. Les 20 instances et leurs budgets sont listées dans `metrics.md` §5 |
| Seeds | **0** pour explorer ; **0, 1, 2** pour évaluer et consolider |
| Baselines | **B0** (topologies aléatoires) et **B1** (SA sur le substitut du kit). Le parallel tempering n'est **pas** relancé : le **gap au meilleur connu** joue ce rôle |
| Ablation | Pour toute partie quantique : la même méthode avec le quantique remplacé par du SA |
| Statistiques | Médiane, min et max sur 3 seeds. Pas de test statistique |
| Exécution | Local d'abord (Maestro) : **aucun circuit de plus de 24 qubits en local**. Le cloud seulement en consolidation, si nécessaire |

## Ordre de travail

| Étape | Instance | Seeds | But | Durée visée |
|---|---|---|---|---|
| 1 · Vérification | `network05` | 0 | Le code tourne et trouve l'optimum (65 500) | secondes |
| 2 · Réglage | `network12` | 0 | Faire fonctionner et régler la méthode | quelques minutes par essai |
| 3 · Évaluation | `network12` | 0, 1, 2 | Comparer la méthode aux baselines, à budget égal | ~ 10 min |
| 4 · Consolidation | `network24` (sinon `network20`, puis `network16`) | 0, 1, 2 | Résultat à rendre : `.sol` + ablation | ~ 30 à 60 min |

On ne passe à l'étape suivante que si la précédente est concluante. Si H1 ne bat pas B1 à l'étape 3, on
s'arrête et on choisit une hypothèse du backlog.

---

## H0 · Baseline minimale

**Statut : Validée — [résultats](hypothesis/h0/result.md)**. Branche : `network/h0-baseline`. Code : `src/network-experiments/h0/`.

L'objectif est de **recalculer le moins possible**. On ne refait que ce qui sert de point de comparaison à
H1, et tout tourne en quelques secondes.

**À livrer :**
1. **Scorer avec cache et compteur.** `score(arcs)` est mémoïsé sur `frozenset(arcs)` et appelle
   `qt.route_min_congestion`. Il compte les résolutions LP effectives (`lp_calls`).
2. **B0, topologies aléatoires.** Des `qt.random_topology(n, rng)` notées par le scorer, jusqu'au budget
   LP (`metrics.md` §2).
3. **B1, SA sur le substitut du kit.** C'est le pipeline du notebook §1.3 : `qt.build_network_qubo`, pénalité
   de poids 1, `SimulatedAnnealingSampler` par lots de 100 lectures (seed du lot = seed du run + numéro du
   lot), puis `repair_topology`, puis le scorer. On s'arrête au budget LP.
4. **Écriture des résultats.**
   - Une ligne JSON par run dans `results/network/bench/h0/<méthode>.jsonl` (schéma de `metrics.md` §4).
   - `save_run` pour le meilleur `.sol`, qui passe par `qt.route_integral`, `qt.write_network_solution`
     et `qt.check_network_solution`.
5. **Jeu de test figé pour `network12`** (utilisé par H1) : `results/network/testsets/network12.json`
   (`metrics.md` §3).
6. **Un test pytest** : B1 retrouve 65 500 sur `network05`.

**Ordre de grandeur attendu**, d'après une mesure du pipeline B1 avec 100 lectures et la seed 1 :
65 500 sur network05 (optimum), 309 750 sur network12 (+12,0 %), 768 778 sur network24 (+15,8 %). Avec le
budget complet, B1 devrait faire au moins aussi bien.

**Critère de fin :** B0 et B1 sur `network05` et `network12` (seeds 0, 1, 2) sont enregistrés et résumés
dans `docs/network/hypothesis/h0/result.md`. B0 et B1 sur `network24` ne sont lancés qu'à la consolidation
de H1.

---

## H1 · Substitut QUBO appris à partir de l'oracle LP (FMQA / BOX-QUBO)

**Statut : À faire**. Branche : `network/h1-learned-surrogate`. Code : `src/network-experiments/h1/`.
Dépend de H0.

**Idée.** Le substitut du kit (`−Σ t_ij x_ij`) ignore le routage sur plusieurs sauts. Le LP coûte
quelques millisecondes, donc on peut **apprendre** un QUBO qui approche le score LP à partir de couples
(topologie, score). La boucle :
1. apprendre le QUBO ;
2. l'échantillonner ;
3. réparer les échantillons et les noter avec le LP ;
4. ajouter ces nouveaux points aux données, puis recommencer.

C'est de l'optimisation boîte noire à substitut quadratique.

**Hypothèse.** À budget LP égal, SA sur le QUBO appris trouve de meilleures topologies que SA sur le
substitut du kit (B1), et que la recherche aléatoire (B0).

### Méthodes comparées : la grille 2 × 2 réduite

| | QUBO du kit | QUBO appris |
|---|---|---|
| **SA** | **B1** `b1_sa_kit` (H0, réutilisé) | **`h1_sa_fm`**, la méthode principale |
| **Quantique (PCE)** | non lancé (gain de temps) | **`h1_pce_fm`**, optionnel |

On y ajoute **B0** `b0_random` (H0, réutilisé).

| Comparaison | Ce qu'elle mesure |
|---|---|
| `h1_sa_fm` contre B1 | **L'effet du substitut appris** : c'est le critère principal |
| `h1_sa_fm` contre B0 | L'apprentissage sert-il à autre chose qu'à évaluer beaucoup de topologies ? |
| `h1_pce_fm` contre `h1_sa_fm` | **L'effet du quantique** (ablation) |

### Protocole

1. **Données initiales.** N₀ topologies aléatoires notées par le LP, avec N₀ ≈ 20 % du budget.
   **Ces appels LP comptent dans le budget.**
2. **Modèle.**
   - Une factorization machine de rang k ∈ {4, 8} sur les n(n−1) bits (FMQA, Kitai 2020). Une
     implémentation numpy (descente de gradient) suffit, pas besoin de PyTorch.
   - La cible est un score normalisé ou un rang, car le min-max est très plat près de l'optimum.
   - Variante si on a le temps : la classification BOX-QUBO (Nüßlein 2023).
3. **QUBO appris.** On convertit la FM en BQM (dimod), puis on ajoute λ·pénalités de degré (le second terme
   renvoyé par `qt.build_network_qubo`, avec λ réglé sur `network12`).
4. **Boucle active.** À chaque tour : SA (100 lectures) sur le QUBO appris, puis repair, puis LP sur les
   topologies nouvelles, puis ajout aux données et réentraînement. On s'arrête au budget LP.
5. **Diagnostic du substitut** (sur le jeu de test figé de `network12`, avant la boucle et à la fin) :
   - F1, la corrélation de Spearman entre l'énergie et le score LP ;
   - F2, la précision du top-10 % ;
   - calculés pour le QUBO du kit et pour le QUBO appris.
6. **Partie quantique, optionnelle.** Dans la boucle, on remplace SA par PCE (Divi, `PolyEncoding`, 16
   qubits environ sur `network12`, en local). Sur `network24`, `PolyEncoding` demande environ 33 qubits :
   - en local, on passe à `DenseEncoding` ou on fixe un nombre de qubits de 24 au plus ;
   - en version 33 qubits, il faut le cloud en MPS, et seulement si des crédits sont disponibles.
7. **Consolidation sur `network24`** (seulement si l'étape 3 est concluante) :
   - B0, B1 et `h1_sa_fm`, plus `h1_pce_fm` si elle a été retenue, avec les seeds 0, 1 et 2 ;
   - en option, une passe de recherche locale par 2-exchanges sur la meilleure topologie, en rapportant
     E5 et E6 (`metrics.md`) ;
   - `save_run` du meilleur `.sol`.

### Critères de succès (sur `network12`, seeds 0, 1, 2, à budget égal)

| Critère | Mesure |
|---|---|
| **Principal** : le substitut appris aide | médiane de Q1(`h1_sa_fm`) < médiane de Q1(B1), **et** au moins 2 seeds sur 3 sous la médiane de B1 |
| L'apprentissage compte | médiane de Q1(`h1_sa_fm`) < médiane de Q1(B0) |
| Le substitut appris ordonne mieux les topologies | F1(appris) > F1(kit) sur le jeu de test |
| Bonus quantique | médiane de E5(`h1_pce_fm`) < médiane de E5(`h1_sa_fm`), avec la même règle des 2 seeds sur 3 |

**Résultat à rendre :** le meilleur `.sol` sur la plus grosse instance consolidée, avec son gap, ses qubits
max et la comparaison à B1 et à l'ablation.

### Références

- Kitai et al. 2020, [10.1103/PhysRevResearch.2.013319](https://doi.org/10.1103/PhysRevResearch.2.013319) (FMQA)
- Nüßlein et al. 2023, [10.1007/978-3-031-36030-5_4](https://doi.org/10.1007/978-3-031-36030-5_4) (BOX-QUBO)
- Tamura et al. 2025, [10.1063/5.0275450](https://doi.org/10.1063/5.0275450) (revue FMQA et paquets Python)
- Sciorilli et al. 2025, [10.1038/s41467-024-55346-z](https://doi.org/10.1038/s41467-024-55346-z) (PCE)

### Pièges

- **Le budget LP doit tout inclure** : les données initiales, la boucle et une éventuelle recherche locale.
- Le jeu de test **ne doit jamais** servir à l'entraînement.
- Sans repair, les échantillons du QUBO appris peuvent être invalides : suivre E1 (`feasible_mass`).

---

## Backlog : hypothèses reportées

Ces pistes sont décrites en détail (protocole, critères, références) dans la version complète de ce
fichier, au commit `29d82b9` (`git show 29d82b9:docs/network/hypothesis.md`). On les reprendra selon
l'avancée du benchmark, en les adaptant à ce profil.

| Id | Piste | Intérêt principal | Références clés (voir `state-of-the-art.md`) |
|---|---|---|---|
| H2 | Substitut analytique enrichi (chemins à 2 sauts) et réglage de λ | Variante sans apprentissage de H1 | Alessandroni 2025, Broesamle 2026 |
| H3 | Repondération du QUBO par les duales du LP (Benders heuristique) | Retour du LP vers le QUBO | Zhao 2022, Joliot 2025, Dixit 2023 |
| H4 | État de Dicke par ligne et mixer XY (faisable par construction) | Contribution quantique « propre » | Wang 2020, Bärtschi 2019, Onah 2025 |
| H5 | Encodage compact des deux permutations | Moins de qubits, seulement intéressant pour n ≥ 8 | Glos 2022, Chancellor 2019 |
| H6 | PCE sur network24 entier | Argument d'échelle (environ 33 qubits, cloud) | Sciorilli 2025, Lizzio Bosco 2026 |
| H7 | Quantum Local Search sur les 2-exchanges | Se greffe sur la méthode qui détient les records | Shaydulin 2019, Podobrii 2025 |
| H8 | Propositions quantiques dans le parallel tempering | Exploratoire | Layden 2023, Orfi 2024 |
| H9 | Partitionnement par blocs de lignes et warm start depuis le LP | Améliore le QAOA partitionné | Zhou 2023, Egger 2021 |

## Statut

Une seule ligne à mettre à jour par hypothèse, dans sa section :
`**Statut : <À faire | En cours | Validée | Invalidée | Non concluante> — [résultats](hypothesis/<id>/result.md)**`.
