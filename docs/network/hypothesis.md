# Hypothèses à expérimenter : network design (QOBLIB 08)

> Feuille de route pour les agents et les humains qui travaillent sur le problème network. Elle s'appuie
> sur [`state-of-the-art.md`](state-of-the-art.md), dont elle reprend les références (auteur, année, DOI).
> **Chaque hypothèse H1 à H9 peut être traitée indépendamment**, dans sa propre branche et sa propre
> session, une fois le socle commun H0 disponible.

## Comment utiliser ce document

1. Choisir une hypothèse dont le statut est `À faire`. Les priorités sont dans le tableau en fin de
   document.
2. Suivre le **workflow commun** de [`workflow.md`](workflow.md) :
   - un worktree et une branche `network/<id>-<slug>` par hypothèse, où `<id>` vaut `h0` à `h9` ;
   - le code dans `src/network-experiments/<id>/` et les notebooks dans `notebooks/network/<id>/` ;
   - la phase 1 en local, avec des circuits de 20 qubits au plus ;
   - `docs/network/hypothesis/<id>/process.md` au début, et `result.md` à la fin.

   Si H0 n'existe pas encore, commencer par H0.
3. Appliquer le **protocole commun** ci-dessous, mesurer les métriques définies dans
   [`metrics.md`](metrics.md) et finir chaque run rendable par `save_run(...)`.
4. À la fin, mettre à jour **la ligne `Statut`** de l'hypothèse dans ce fichier (statut et lien vers
   `hypothesis/<id>/result.md`). Le détail des résultats va dans `result.md`, pas ici.
5. Lire les PDF des papiers avec `uv run markitdown <fichier.pdf>` (voir AGENTS.md).

## Protocole commun (à respecter pour que les hypothèses soient comparables)

### Instances

| Rôle | Instance | Variables | Référence |
|---|---|---:|---|
| Vérité terrain exhaustive | `network05` | 20 | optimum 65 500, toutes les topologies énumérables |
| Optimum prouvé | `network08`, `network10` | 56, 90 | 170 231, 210 800 |
| Référence du kit | `network12` | 132 | 276 474 |
| Montée en charge | `network16`, `network20` | 240, 380 | 397 908, 528 528 |
| Cible finale | `network24` | 552 | 663 688 |

Les meilleurs connus à jour sont dans la [table QOBLIB](https://github.com/ZIB-AOPT/QOBLIB/blob/main/08-network/solutions/README.md).

### Métriques et budgets

Les définitions exactes (formule, calcul, unité, clé JSON), les budgets standard, le schéma JSON et les
règles de décision sont dans **[`metrics.md`](metrics.md)**. Ce document est la référence. Résumé :

| Famille | Métriques | Toujours obligatoire ? |
|---|---|---|
| Qualité | Q1 `score`, Q2 `gap`, Q4 `hit_target` | Oui |
| Coût | C1 `lp_calls`, C2 `wall_time_s`, C3 `n_circuits`, C4 `credits_used`, C6 `lp_calls_to_target`, C8 `trajectory` | Oui |
| Échelle | S1 `n_vars`, S2 `n_vars_model`, S3 `max_qubits` | Oui |
| Échantillonnage | E1 `feasible_mass`, E3 `n_distinct_valid`, E5 `score_raw`, E6 `score_after_ls`, E7 `p_opt`, E8 `rank_best` | Si la méthode échantillonne |
| Substitut | F1 `spearman_rho`, F2 `top10_precision`, F3 `ref_percentile` (sur le jeu de test figé) | Si la méthode introduit un QUBO |
| Attribution | A1 `ablation_method`, A2 `delta_median_vs_ablation`, A3 `p_value_vs_ablation`, A4 vs B2 | Si la méthode est quantique |

**Règles clés :**
- 5 seeds (0 à 4).
- Comparaisons **à budget LP égal** (`metrics.md` §2).
- La statistique principale est la **médiane** de Q1.
- Un gain quantique n'est retenu que si A2 < 0 **et** A3 < 0,05.
- Le gain d'un échantillonneur se lit sur E5 (avant recherche locale), pas sur E6.

### Baselines obligatoires (fournies par H0)

| Id | Baseline | Rôle |
|---|---|---|
| B0 | Topologies aléatoires valides (`qt.random_topology`), même budget d'appels au LP | Plancher |
| B1 | SA sur le substitut du kit, puis `repair_topology`, puis le LP (pipeline du notebook §1.3) | Référence du kit |
| B2 | Recherche locale ou parallel tempering sur les topologies, avec des 2-exchanges et le LP comme énergie (réimplémentation de Gupta) | **La barre à battre** : elle détient les records |
| B3 | QAOA partitionné et PCE du notebook §1.3, en local avec Maestro | Point de départ quantique |

### Règles

- On met au point en local (`make_backend(use_cloud=False)`). On ne passe au cloud qu'une fois le
  pipeline validé sur `network05` et `network12`, et on note les crédits consommés.
- `references/qoblib_tools.py` ne se modifie jamais. Si on a besoin des duales du LP ou d'un cache, on
  écrit un wrapper dans `src/network-experiments/h0/` (on peut réutiliser `qt._routing_lp`).
- Un résultat rendable passe par `qt.route_integral`, `qt.write_network_solution`,
  `qt.check_network_solution`, puis `save_run`.

---

## H0 · Socle commun (prérequis)

**Statut : À faire**. Branche : `network/h0-baseline`. Code : `src/network-experiments/h0/`.

Ce n'est pas une hypothèse : c'est l'outillage dont toutes les autres ont besoin.

**À livrer :**
1. **Scorer avec cache.** `score(arcs)` mémoïsé sur `frozenset(arcs)`, avec un compteur d'appels.
2. **Scorer avec duales.** `score_with_duals(arcs)` renvoie le score, la charge de chaque arc et les
   multiplicateurs des contraintes de capacité (`linprog(method="highs")`, `res.ineqlin.marginals`, sur
   le modèle de `qt._routing_lp`). Ce scorer sert à H3, et aussi à H1 et H2.
3. **Représentations et mouvements.**
   - Conversions entre la liste d'arcs, le vecteur binaire (ordre de `qt.all_arcs`) et les deux
     permutations (σ₁, σ₂).
   - Énumération des **2-exchanges valides** `(a→b),(c→d) ⇒ (a→d),(c→b)` (pas de boucle, pas de
     doublon), et des 3-exchanges.
4. **Baselines B0 à B3**, plus un **parallel tempering B2** fidèle à la description de Gupta (dans
   `state-of-the-art.md` §0).
5. **Harnais de benchmark réutilisable.** `python -m h0.run_bench --method <m> --instance networkNN --seed s`
   (avec `PYTHONPATH=src/network-experiments`) applique les budgets standard de `metrics.md` §2 et écrit
   **une ligne JSON par run** dans `results/network/bench/<id>/<méthode>.jsonl`, au schéma de
   `metrics.md` §6. Les autres hypothèses doivent pouvoir y brancher leurs propres méthodes.
6. **Instrumentation des métriques** (`src/network-experiments/h0/metrics.py`) :
   - compteurs C1 et C1b du scorer, chronomètre C2, enregistrement de la trajectoire C8 à chaque
     amélioration, avec C6 et C7 calculés à partir d'elle ;
   - fonctions E1 à E8 (à partir d'une liste de bitstrings et de probabilités) et F1 à F3 ;
   - génération et sauvegarde des **jeux de test figés** `results/network/testsets/networkNN.json`
     (`metrics.md` §3.F) pour `network05`, `network12`, `network16` et `network24` ;
   - agrégation sur les seeds (`metrics.md` §4) et tests A2 à A4 : un script
     `python -m h0.report <id>/<méthode> [--vs <id>/<ablation>]` qui imprime les tableaux Markdown du
     modèle `result.md`.
7. **Tests pytest :**
   - le cache rend le même score que `qt.route_min_congestion` ;
   - un 2-exchange préserve `qt.is_valid_topology` ;
   - B2 retrouve l'optimum de `network05` (65 500) ;
   - le JSON produit contient toutes les clés de `metrics.md` §6.

**Métriques principales :** toutes celles de `metrics.md`, puisque H0 les implémente.

**Critère de fin :**
- les runs B0 à B3 (5 seeds, budgets standard) existent pour `network05`, `network12`, `network16` et
  `network24`, avec Q1, Q2, C1, C2 et C8 ;
- B2 atteint `hit_target["0"]` sur `network05` sur 5/5 seeds ;
- les tableaux agrégés (`metrics.md` §4) sont recopiés dans `docs/network/hypothesis/h0/result.md`.

---

## H1 · Substitut QUBO appris à partir de l'oracle LP (FMQA / BOX-QUBO)

**Statut : À faire**. Branche : `network/h1-learned-surrogate`. Priorité : **haute**.

**Idée.** Le substitut du kit (`−Σ t_ij x_ij`) ignore le routage multi-sauts. Le LP coûte quelques ms, ce
qui permet de produire des dizaines de milliers de couples (topologie, score) et d'**apprendre** un QUBO
qui approche le score. On l'échantillonne ensuite (QAOA, PCE, SA), on note les candidats avec le LP, on
les ajoute aux données, et on recommence (optimisation boîte noire).

**Hypothèse.** Un QUBO appris (factorization machine, ou classification BOX-QUBO) classe les topologies
nettement mieux que le substitut du kit. Résultat attendu : B1 avec ce QUBO à la place du substitut fait
mieux que B1 avec le substitut d'origine, à budget LP égal.

**Protocole.**
1. **Données.** Topologies aléatoires, plus les trajectoires de B2 (qui couvrent les bonnes régions),
   avec leur score LP.
2. **Modèle.** Une FM de rang k ∈ {4, 8, 16} sur les n(n−1) bits (FMQA, Kitai 2020), puis la variante
   classification « top-q % contre le reste » (BOX-QUBO, Nüßlein 2023). En option, l'entraînement sur
   sous-échantillons (Hama 2025).
3. **Contraintes.** QUBO = FM + λ·pénalités de degré, ou `LinearConstraint` de Divi.
4. **Boucle active.** Échantillonner avec SA puis avec QAOA ou PCE (Divi), réparer, noter avec le LP,
   réentraîner, sur N itérations.
5. **Diagnostics.**
   - Corrélation de rang de Spearman entre l'énergie du QUBO et le score LP, sur un jeu de test.
   - Sur `network05`, rang de l'optimum publié dans le QUBO appris (characterization avec un état de
     référence, voir H2).

**Métriques principales :** F1, F2, F3 (substitut appris contre substitut du kit, sur le même jeu de
test), Q1 et Q2 médians, C6, et A2 et A3 pour la partie quantique.

**Critères de succès.**
- F1 (`spearman_rho`) ≥ F1(kit) + 0,2 **et** F2 ≥ 0,3 sur `network12` et `network16`.
- À budget LP égal, médiane de Q1 de « B1 avec substitut appris » < médiane de Q1 de B1, avec
  p < 0,05 (Mann-Whitney sur 5 seeds) sur `network12` et `network16`.
- Bonus : un échantillonneur quantique (QAOA ou PCE) sur ce QUBO a un E5 au plus 2 % au-dessus de la
  médiane de B2.

**Références.**
- Kitai et al. 2020, [10.1103/PhysRevResearch.2.013319](https://doi.org/10.1103/PhysRevResearch.2.013319)
- Nüßlein et al. 2023, [10.1007/978-3-031-36030-5_4](https://doi.org/10.1007/978-3-031-36030-5_4)
- Tamura et al. 2025, [10.1063/5.0275450](https://doi.org/10.1063/5.0275450) (paquets Python FMQA)
- Hama et al. 2025, [10.1103/qgpq-6dmr](https://doi.org/10.1103/qgpq-6dmr)
- Baptista et al. 2018, [10.48550/arXiv.1806.08838](https://doi.org/10.48550/arXiv.1806.08838)

**Pièges.**
- Le score est un min-max, donc très plat près de l'optimum : préférer des cibles de rang ou un
  `log(score)`.
- Le modèle peut sur-apprendre sur les topologies de B2.

---

## H2 · Substitut analytique enrichi et réglage de λ guidé par la characterization

**Statut : À faire**. Branche : `network/h2-physics-surrogate`. Priorité : moyenne.

**Idée.** Sans apprentissage, enrichir le substitut avec la physique du routage, puis régler le poids
des pénalités avec méthode plutôt qu'à la main.

**Hypothèse.** Un substitut qui récompense les chemins à 2 sauts `x_ij·x_jk` pondérés par `t_ik`, et qui
pénalise les nœuds dont la demande sortante est forte, place l'optimum publié de `network05`/`network08`
plus bas dans le spectre du QUBO. Bien réglé, λ augmente le taux de faisabilité sans écraser l'objectif.

**Protocole.**
1. **Termes à ajouter.**
   - Directs : `−α Σ t_ij x_ij`.
   - Deux sauts : `−β Σ t_ik x_ij x_jk`.
   - Charge sortante : `+γ Σ_i (Σ_j t_ij)·(…)`.
   - En option, des termes d'ordre 3 (HUBO, acceptés par `BinaryOptimizationProblem`).
2. **Choix de (α, β, γ).** Grille, ou régression sur les données de H0.
3. **λ.** Comparer trois approches :
   - la règle statique d'Ayodele 2022 ;
   - la borne serrée de Broesamle 2026 ;
   - le λ recommandé par la **Characterization Service**.

   Suivre aussi l'écart entre les coefficients (Rezk 2026).
4. **Validation.** Characterization (cloud, **coûteuse : `network05` et `network08` seulement**) avec
   l'optimum publié comme `reference_states`, pour connaître son rang dans le spectre.
5. Rejouer B1 et B3 avec ce substitut.

**Métriques principales :** F1, F2, F3 (et F4 si cloud), E1 pour chaque λ testé, Q1 et Q2 médians de B1
et B3 rejoués avec le nouveau substitut.

**Critères de succès.**
- F3 (`ref_percentile`) de l'optimum publié < F3(kit) sur `network05` et `network08`, et F1 ≥ F1(kit) + 0,1.
- Avec le λ retenu, E1 (`feasible_mass`) de B1 ≥ E1 avec λ = 1 (réglage du notebook), sans dégrader
  E5.
- Médiane de Q1 de B1 et de B3 strictement meilleure qu'avec le substitut du kit sur `network12`
  (p < 0,05).

**Références.**
- Alessandroni et al. 2025, [10.1038/s41534-025-01067-0](https://doi.org/10.1038/s41534-025-01067-0)
- Ayodele 2022, [10.1007/978-3-031-04148-8_11](https://doi.org/10.1007/978-3-031-04148-8_11)
- Broesamle et al. 2026, [10.48550/arXiv.2602.10951](https://doi.org/10.48550/arXiv.2602.10951)
- Rezk et al. 2026, [10.48550/arXiv.2609.04593](https://doi.org/10.48550/arXiv.2609.04593)
- Montañez-Barrera et al. 2024, [10.1088/2058-9565/ad35e4](https://doi.org/10.1088/2058-9565/ad35e4)
  (si on encode `charge ≤ z`)

**Pièges.** Le terme à 2 sauts densifie le QUBO, ce qui réduit l'intérêt du partitionnement.

---

## H3 · Rétroaction du LP par les duales (Benders heuristique)

**Statut : À faire**. Branche : `network/h3-dual-feedback`. Priorité : moyenne.

**Idée.** Le LP de routage dit quels arcs sont saturés et combien coûte leur capacité (ses
multiplicateurs). On s'en sert pour **repondérer le QUBO** à chaque itération : pénaliser les zones
congestionnées, récompenser les arcs qui offriraient des détours. On boucle « QUBO → échantillons → LP →
duales → QUBO ».

**Hypothèse.** La boucle de repondération converge vers de meilleures topologies que B1 à budget LP
égal, et fournit au quantique un QUBO qui évolue au fil des itérations, comme le problème maître de
Benders.

**Protocole.**
1. Prendre `score_with_duals` (H0) pour les K meilleures topologies du tour.
2. **Mise à jour.** Pour chaque arc saturé (i→j) de dual μ_ij > 0 :
   - augmenter le coût linéaire de `x_ij` ;
   - pour chaque commodité qui y passe, récompenser les arcs d'un détour (termes quadratiques
     `x_ik x_kj`).

   En variante, ajouter des coupes de type Benders sous forme de pénalités (Zhao 2022), avec plusieurs
   coupes par itération (Joliot 2025).
3. Résoudre le QUBO mis à jour avec SA, puis QAOA partitionné ou PCE (Divi). Garder un archivage élitiste.
4. Comparer à B1 et B2. Mesurer la vitesse de convergence en appels LP.

**Métriques principales :** Q1 et Q2 médians, C6 (`lp_calls_to_target`), C8 (trajectoire par
itération de la boucle), A2 et A3 contre la même boucle **sans** mise à jour par les duales.

**Critères de succès.**
- Médiane de Q1 < médiane de Q1 de B1 à budget LP égal, avec p < 0,05, sur `network12` et `network16`.
- Dans l'ablation sans duales, A2 < 0 avec A3 < 0,05 : ce sont bien les duales qui apportent le gain.
- Médiane de Q1 au plus 2 % au-dessus de celle de B2 sur `network16`.

**Références.**
- Zhao et al. 2022, [10.1109/WCNC51071.2022.9771632](https://doi.org/10.1109/WCNC51071.2022.9771632)
- Joliot et al. 2025, [10.1109/CoDIT66093.2025.11321887](https://doi.org/10.1109/CoDIT66093.2025.11321887)
- Dixit et al. 2023, [10.1038/s41598-023-38787-2](https://doi.org/10.1038/s41598-023-38787-2)
  (architecture en deux niveaux)
- Gambella et al. 2020, [10.1109/TQE.2020.3033139](https://doi.org/10.1109/TQE.2020.3033139)
  (alternative ADMM)
- Bienstock et al. 1995, [10.1007/BF01585766](https://doi.org/10.1007/BF01585766)

**Pièges.**
- La relaxation LP est faible (Koch 2026), donc les vraies coupes de Benders seront lâches : rester
  heuristique.
- Le LP a souvent plusieurs solutions duales, ce qui rend le signal bruité : moyenner sur les K
  meilleures topologies.

---

## H4 · Faisable par construction : état de Dicke par ligne et mixer XY ou Grover local

**Statut : À faire**. Branche : `network/h4-dicke-xy`. Priorité : **haute** (contribution quantique nette).

**Idée.** Les variables `x_ij` d'une même ligne i forment un bloc de n−1 qubits qui doit contenir
exactement 2 uns (degré sortant 2). Si on part de ⊗_i |D₂^{(n−1)}⟩ (Dicke de poids 2) et qu'on applique
un mixer XY (anneau ou complet) **par ligne**, tous les degrés sortants restent satisfaits à toute
profondeur. Il ne reste que les degrés entrants à pénaliser, ou à traiter par un mixer de Grover local
(Choi 2026).

**Hypothèse.** Ce QAOA sous contraintes produit bien plus d'échantillons faisables que le QAOA avec
pénalités du notebook (Onah 2025 prédit un écart exponentiel), et de meilleures topologies à nombre de
circuits égal.

**Protocole.**
1. **Préparation de Dicke.** Dériver `divi.qprog.initial_states.InitialState` en `DickeRowsState`, avec
   le circuit de Bärtschi 2019. Tester par simulation qu'on obtient bien la superposition uniforme des
   lignes de poids 2.
2. **Mixer.** Construire le mixer XY par bloc (`divi.hamiltonians.xy_mixer`,
   `build_block_xy_mixer_edges`) et l'assigner à `QAOA.mixer_hamiltonian`. S'inspirer du CE-QAOA TSP de
   `divi/qprog/problems/_routing.py`.
3. **Coût.** Substitut du kit (ou de H1/H2) avec la pénalité des degrés entrants seulement.
4. **Comparaisons.**
   - Sur `network05` (20 qubits) et `network06` (30 qubits), en simulation : faisabilité brute,
     P(optimum), meilleur score, comparés au QAOA du notebook §1.2.
5. **Passage à l'échelle.** Partitionner par **groupes de lignes** : chaque sous-programme garde des
   lignes complètes, pour que le Dicke et le XY restent valides. Combiner avec H9.

**Métriques principales :** E1 (`feasible_mass`), E7 (`p_opt`), E8 (`rank_best`), E5, S3, S5
(`max_depth`), C3. Comparaison avec le QAOA à pénalités du notebook, à couches, shots et circuits égaux.

**Critères de succès.**
- E1 ≥ 10 × E1(QAOA à pénalités) sur `network05` et `network06`.
- E7 (`p_opt`) > E7(QAOA à pénalités) sur `network05`, sur 5/5 seeds.
- Avec le partitionnement par lignes : E5 médian < E5 médian de B3 sur `network12` (p < 0,05).

**Références.**
- Hadfield et al. 2019, [10.3390/a12020034](https://doi.org/10.3390/a12020034)
- Wang et al. 2020, [10.1103/PhysRevA.101.012320](https://doi.org/10.1103/PhysRevA.101.012320)
- Bärtschi et al. 2019 (Dicke), [10.1007/978-3-030-25027-0_9](https://doi.org/10.1007/978-3-030-25027-0_9)
- Bärtschi et al. 2020 (GM-QAOA), [10.1109/QCE49297.2020.00020](https://doi.org/10.1109/QCE49297.2020.00020)
- Choi et al. 2026, [10.1088/2058-9565/aebe5e](https://doi.org/10.1088/2058-9565/aebe5e)
- Onah et al. 2025, [10.48550/arXiv.2511.17259](https://doi.org/10.48550/arXiv.2511.17259)

**Pièges.**
- Les circuits sont profonds (Dicke en O(n) par ligne), donc on simule vite seulement en dessous
  d'environ 30 qubits par programme.
- Vérifier que `PartitioningProgramEnsemble` accepte un mixer et un état initial personnalisés. Sinon,
  écrire la boucle de partitionnement soi-même.

---

## H5 · Encodage compact des deux permutations (binaire ou domain-wall)

**Statut : À faire**. Branche : `network/h5-compact-encoding`. Priorité : basse (exploratoire).

**Idée.** Une topologie valide est (σ₁, σ₂), deux dérangements qui ne coïncident jamais. On encode
chaque σ(i) en binaire (⌈log₂ n⌉ qubits) ou en domain-wall (n−2 qubits) au lieu du one-hot.
- **Encodage binaire :** network24 passe de 552 à 2·24·5 = **240 qubits**.
- **Variante :** encoder directement la paire non ordonnée de successeurs de chaque nœud, soit
  ⌈log₂ C(n−1,2)⌉ = 8 bits par nœud, donc 192 qubits.

**Hypothèse.** L'encodage compact réduit le nombre de qubits d'un facteur 2 à 3 sans dégrader la qualité.
L'objectif et les contraintes restantes deviennent d'ordre supérieur (HUBO, supporté par
`BinaryOptimizationProblem`).

**Protocole.**
1. Écrire l'encodeur et le décodeur, avec un décodage tolérant : un code invalide est réparé par
   `repair_topology`.
2. Construire le HUBO : substitut et contraintes de bijectivité et de non-coïncidence. Pour les
   permutations, s'inspirer des réseaux de tri de Friedl 2026.
3. Comparer au one-hot : qubits, profondeur, faisabilité, meilleur score, sur `network05` à `network10`.

**Métriques principales :** S2 (`n_vars_model`), S3 (`max_qubits`), S5 (`max_depth`), E1, E5, Q1 et Q2
médians, comparés à l'encodage one-hot à budget égal.

**Critères de succès.**
- S3 ≤ 0,5 × S3(one-hot) sur la même instance.
- Médiane de E5 au plus 1 % au-dessus de celle du one-hot sur `network05` à `network10` (pas de
  différence significative : p ≥ 0,05 dans le sens défavorable).
- S5 ≤ 3 × S5(one-hot).

**Références.**
- Glos et al. 2022, [10.1038/s41534-022-00546-y](https://doi.org/10.1038/s41534-022-00546-y)
- Chancellor 2019, [10.1088/2058-9565/ab33c2](https://doi.org/10.1088/2058-9565/ab33c2)
- Friedl et al. 2026, [10.48550/arXiv.2603.07579](https://doi.org/10.48550/arXiv.2603.07579)
- Kandora et al. 2025 (compromis entre PUBO et QUBO), [10.48550/arXiv.2510.21901](https://doi.org/10.48550/arXiv.2510.21901)

**Pièges.**
- La symétrie σ₁ ↔ σ₂ (2ⁿ représentations par topologie) dilue l'amplitude : envisager d'imposer un ordre
  (σ₁(i) < σ₂(i)).
- La densité du HUBO peut exploser.

---

## H6 · PCE à l'échelle de network24, avec CVaR et baseline déquantisée

**Statut : À faire**. Branche : `network/h6-pce-scale`. Priorité : **haute** (argument d'échelle).

**Idée.** PCE encode les 552 variables de network24 sur environ √(2·552) ≈ 33 qubits avec
`PolyEncoding`, sans partitionner. C'est le levier le plus direct pour mettre en avant « l'instance la
plus grosse ».

**Hypothèse.** PCE sur le QUBO entier de network24 (substitut du kit, puis H1 ou H2), suivi de
`repair_topology` et du LP, fait mieux que B1. Agréger par CVaR et trier par énergie améliore la
meilleure solution. Une variante **déquantisée** de PCE doit être battue, ou au moins égalée, pour que le
résultat compte.

**Protocole.**
1. Rejouer la cellule PCE du notebook (§1.3) sur `network12`, puis `network16`, `network20` et
   `network24`, avec `PolyEncoding` et `DenseEncoding`.
2. Balayer : `SoftObjective(alpha)`, nombre de couches, population et itérations de `MonteCarloOptimizer`.
3. Ajouter une agrégation CVaR (Barkoutsos 2020) si Divi le permet, sinon l'écrire.
4. **Baseline déquantisée** (Lizzio Bosco 2026) : même encodage, circuit simulable classiquement (IQP
   ou matchgate). En plus simple : optimiser directement les signes des corrélateurs, sans circuit.
5. Post-traitement : top-k par énergie, puis repair, puis LP, puis une passe de 2-exchanges (H0).
   **Rapporter les scores avant et après la recherche locale.**
6. Passer au cloud seulement pour le meilleur réglage, et noter les crédits.

**Métriques principales :** E5 (`score_raw`) **et** E6 (`score_after_ls`), Q2, S3 (`max_qubits`), C3,
C4, A1 à A3 contre la variante déquantisée, E1, E3.

**Critères de succès.**
- Sur `network24` : médiane de E5 < médiane de Q1 de B1, avec p < 0,05.
- A2 < 0 et A3 < 0,05 contre la variante déquantisée (A1 = `pce_dequantized`), comparés sur E5.
- S3 ≥ 30 qubits sur `network24` (argument d'échelle).

**Références.**
- Sciorilli et al. 2025, [10.1038/s41467-024-55346-z](https://doi.org/10.1038/s41467-024-55346-z)
- Lizzio Bosco et al. 2026, [10.48550/arXiv.2607.20409](https://doi.org/10.48550/arXiv.2607.20409)
- Tan et al. 2021, [10.22331/q-2021-05-04-454](https://doi.org/10.22331/q-2021-05-04-454)
- Barkoutsos et al. 2020, [10.22331/q-2020-04-20-256](https://doi.org/10.22331/q-2020-04-20-256)

**Pièges.** Ne pas confondre le gain du PCE et celui de la recherche locale finale : l'ablation est
obligatoire.

---

## H7 · Quantum Local Search sur le voisinage des 2-exchanges

**Statut : À faire**. Branche : `network/h7-qls-2exchange`. Priorité : **haute** (s'appuie sur la méthode
qui détient les records).

**Idée.** Les records viennent d'une recherche par 2-exchanges (B2). On garde ce cadre, mais on confie au
quantique le **choix du meilleur mouvement, ou d'une combinaison de mouvements**, dans un grand
voisinage.
- **Variante A, qubit-efficient** (Podobrii 2025) : indexer les l ≤ C(2n,2) 2-exchanges valides sur
  ⌈log₂ l⌉ qubits, soit environ 11 qubits pour network24. Le circuit variationnel concentre l'amplitude
  sur les coups qui améliorent le score.
- **Variante B, QLS classique** (Shaydulin 2019) : libérer un sous-ensemble de k nœuds (leurs lignes et
  colonnes), fixer le reste, puis résoudre le sous-QUBO restreint avec QAOA (Divi) ou H4.

**Hypothèse.** À nombre d'appels LP égal, QLS atteint de meilleures topologies que la recherche locale
gloutonne avec des coups tirés au hasard, et s'approche de B2.

**Protocole.**
1. **Énergie des coups.** Le LP est trop cher pour noter tout le voisinage à chaque pas. On utilise un
   substitut local, Δ(substitut) ou un modèle appris (H1), et on ne passe au LP que les top-k candidats.
2. **Variante A.** Encoder la table des coups. La fonction de coût du circuit est l'espérance de Δ sur
   les coups mesurés.
3. **Variante B.** Choisir le sous-ensemble de nœuds au hasard, guidé par la congestion (duales de H0),
   ou par apprentissage par renforcement (Liu 2023). Lancer plusieurs QLS en parallèle (Liu 2024),
   adapté aux batchs cloud.
4. Comparer à B2 et à une ablation où le quantique est remplacé par un tirage uniforme ou glouton.

**Métriques principales :** Q1 et Q2 médians, C6 et C8 (courbes à budget LP égal), A1 à A4 (ablation :
même recherche locale avec un choix de coups uniforme ou glouton), S3, C3, C4.

**Critères de succès.**
- A2 < 0 et A3 < 0,05 contre l'ablation classique, sur `network16` et `network24`.
- Q2 médian ≤ (Q2 médian de B1 + Q2 médian de B2) / 2 sur `network16` à `network24` : au moins à
  mi-chemin entre B1 et B2.
- Pour la variante B : S3 rapporté, avec un objectif de S3 ≥ 20.

**Références.**
- Shaydulin et al. 2019, [10.1002/qute.201900029](https://doi.org/10.1002/qute.201900029)
- Podobrii et al. 2025, [10.48550/arXiv.2502.02245](https://doi.org/10.48550/arXiv.2502.02245)
- Liu et al. 2023, [10.48550/arXiv.2304.06473](https://doi.org/10.48550/arXiv.2304.06473)
- Liu et al. 2024, [10.48550/arXiv.2406.06445](https://doi.org/10.48550/arXiv.2406.06445)

**Pièges.** Le nombre de qubits reste petit (environ 11), ce qui fait peu pour le critère « qubits du plus
gros programme ». C'est la variante B qui porte l'argument d'échelle.

---

## H8 · Propositions quantiques dans le parallel tempering (QeMCMC)

**Statut : À faire**. Branche : `network/h8-qemcmc-pt`. Priorité : moyenne. Dépend de B2 (H0).

**Idée.** On reprend le parallel tempering de Gupta (B2) et on remplace une partie des propositions
classiques (2-exchanges ou 3-exchanges aléatoires) par des **propositions quantiques**. Un circuit
(QAOA court ou évolution hamiltonienne sur le substitut, éventuellement H4 pour rester faisable) produit
une nouvelle topologie à partir de l'état courant. L'acceptation de Metropolis reste classique, sur
l'énergie LP.

**Hypothèse.** Les propositions quantiques accélèrent la convergence du PT (moins d'appels LP pour
atteindre un score cible). Comme Orfi 2024 montre qu'il n'y a pas d'accélération dans le pire cas non
structuré, le gain éventuel devra venir de la structure du substitut.

**Protocole.**
1. Reproduire B2 sur `network12` et `network16`, et vérifier les scores de Gupta à budget réduit.
2. Mélange de propositions : une fraction p ∈ {0, 0.1, 0.3} des coups est quantique. Pour qu'une
   proposition quantique reste locale, ne laisser varier qu'un bloc de k nœuds et fixer le reste.
3. **Respecter le bilan détaillé**, ou le documenter s'il est rompu : c'est une heuristique
   d'optimisation, pas un échantillonneur exact.
4. **Mesure principale :** le temps et le nombre d'appels LP pour atteindre le meilleur connu + x %.

**Métriques principales :** C6 (`lp_calls_to_target` à eps = 0,01 et 0,001), C7, C8, Q1 et Q2 médians,
A4 contre B2 (p = 0), C3 et C4 (budget quantique, rapporté à part).

**Critères de succès.**
- Médiane de C6 à eps = 0,01 au plus 0,8 × celle de B2 avec p = 0, sur `network12` et `network16`.
- Médiane de Q1 à budget LP égal non pire que celle de B2 (A4 : p ≥ 0,05 dans le sens défavorable).
- Coût quantique (C3 et C4) rapporté et jugé soutenable pour un run sur `network24`.

**Références.**
- Layden et al. 2023, [10.1038/s41586-023-06095-4](https://doi.org/10.1038/s41586-023-06095-4)
- Orfi et al. 2024, [10.48550/arXiv.2403.03087](https://doi.org/10.48550/arXiv.2403.03087)
- Soumission QOBLIB de Gupta (`08-network/submissions/20260818_ParallelTempering_Gupta`)

**Pièges.** Le coût réel d'un circuit (cloud) est sans commune mesure avec celui d'un coup classique. Il
faut rapporter les deux budgets séparément.

---

## H9 · Partitionnement guidé par la structure et warm start depuis le LP

**Statut : À faire**. Branche : `network/h9-structured-partition`. Priorité : moyenne.

**Idée.** `CommunityDecomposer` coupe le QUBO sans tenir compte des contraintes de degré, d'où les
échantillons invalides et le recours systématique à `repair_topology`. On propose plutôt :
- un partitionnement **par blocs de nœuds** (lignes complètes, ou sous-graphes induits sur k nœuds avec
  les arcs hors bloc fixés à l'incumbent), éclairé par la section `structure` de la characterization ;
- un recollage hiérarchique (QAOA², Zhou 2023) ;
- un warm start depuis la relaxation LP de la topologie (Egger 2021, Broesamle 2026) ;
- du variable fixing de type RQAOA (Bravyi 2020).

**Hypothèse.** Un partitionnement qui respecte les blocs de degré augmente la faisabilité des recollages
et améliore le score final du QAOA partitionné, par rapport à B3.

**Protocole.**
1. **Décomposeurs.**
   - Par lignes : k lignes par partition, soit k(n−1) variables (k=1 donne n−1 qubits, compatible H4).
   - Par sous-graphes induits autour d'un incumbent : grand voisinage, de type LNS.
2. **Warm start.** Relaxation continue de la topologie (LP du multi-flot avec x ∈ [0,1]) → angles
   initiaux, ou état produit biaisé (`CustomPerQubitState`).
3. **Recollage.** Comparer la beam search de Divi et le recollage hiérarchique.
4. Comparer à B3 sur `network12`, `network16` et `network24` : faisabilité avant repair, score, nombre de
   circuits.

**Métriques principales :** E1 (`feasible_mass`), E4 (`repair_hamming_mean`), E5, Q1 et Q2 médians,
S3, S4, C3. Comparaison avec B3 (`CommunityDecomposer`) à `cluster_size` et budget de circuits égaux.

**Critères de succès.**
- E1 ≥ 2 × E1(B3) et E4 ≤ 0,5 × E4(B3) sur `network12` et `network16`.
- Médiane de E5 < médiane de E5 de B3 sur `network12`, `network16` et `network24`, avec p < 0,05.

**Références.**
- Zhou et al. 2023, [10.1103/PhysRevApplied.19.024027](https://doi.org/10.1103/PhysRevApplied.19.024027)
- Kandora et al. 2025, [10.48550/arXiv.2510.21901](https://doi.org/10.48550/arXiv.2510.21901)
- Egger et al. 2021, [10.22331/q-2021-06-17-479](https://doi.org/10.22331/q-2021-06-17-479)
- Bravyi et al. 2020, [10.1103/PhysRevLett.125.260505](https://doi.org/10.1103/PhysRevLett.125.260505)
- Broesamle et al. 2026, [10.48550/arXiv.2602.10951](https://doi.org/10.48550/arXiv.2602.10951)

---

## Priorisation suggérée

| Ordre | Hypothèse | Pourquoi |
|---|---|---|
| 0 | H0 socle | Prérequis : sans baseline B2, aucun gain n'est interprétable |
| 1 | H7 QLS 2-exchange | Se greffe sur la méthode qui détient les records, donc la meilleure chance d'approcher le meilleur connu |
| 1 | H6 PCE network24 | Argument d'échelle direct : la plus grosse instance, environ 33 qubits |
| 1 | H1 substitut appris | Corrige le défaut principal du pipeline (le substitut), et profite à H4, H6 et H7 |
| 2 | H4 Dicke + XY | Contribution quantique la plus « propre », mais limitée par la simulation |
| 2 | H3 duales LP, H2 substitut enrichi, H9 partitionnement | Améliorations incrémentales du pipeline du kit |
| 3 | H8 QeMCMC, H5 encodage compact | Plus exploratoires, gain incertain |

## Journal des résultats

Les résultats détaillés de chaque hypothèse vont dans `docs/network/hypothesis/<id>/result.md`, à partir
du modèle [`hypothesis/_template/result.md`](hypothesis/_template/result.md). Le procédé suivi va dans
`process.md` (modèle [`hypothesis/_template/process.md`](hypothesis/_template/process.md)). Ici, on ne met
à jour que la ligne `Statut` de l'hypothèse :

```markdown
**Statut : Validée (phase 1) — [résultats](hypothesis/h7/result.md)**. Branche : `network/h7-qls-2exchange`. …
```

Statuts possibles : `À faire`, `En cours`, `Validée`, `Invalidée`, `Non concluante` (règles de
`metrics.md` §5), suivis de `(phase 1)` ou `(phase 2)`.
