# État de l'art : QUBO et méthodes quantiques pour la conception de réseaux (QOBLIB 08)

> Revue réalisée le 2026-11 pour le problème **08 · Network design** du hackathon.
> Les hypothèses à expérimenter qui en découlent sont dans [`hypothesis.md`](hypothesis.md).

**Méthode.** Recherche sur arXiv, OpenAlex, Crossref et Europe PMC. Chaque DOI, auteur, mois et année a
été vérifié dans les métadonnées. Pour les prépublications arXiv, le DOI donné est celui d'arXiv
(`10.48550/arXiv.xxxx`). Les résultats viennent des résumés, sauf mention contraire (texte intégral lu
pour Dixit et al. et pour l'article QOBLIB).

**Limite importante.** Aucun papier ne traite cette instance (Bienstock–Günlük, 2 liens entrants et 2
sortants, min-max de la congestion) avec du quantique. Presque tous les résultats viennent de problèmes
voisins : TSP, coloration de graphes, conception de réseaux de transport, flots multi-produits, MaxCut.
Leurs gains ne se transposent pas automatiquement.

## Rappel du problème

On choisit un graphe orienté à n nœuds où chaque nœud a exactement 2 arcs sortants et 2 entrants, soit
n(n−1) variables binaires `x_ij`. On route ensuite toute la demande `t_ij` (multi-flots fractionnaires) en
minimisant la charge maximale d'un arc. Le score officiel vaut ⌈z_LP⌉ en unités de 1/1000.

- **Topologie → score.** Le score se calcule exactement par un LP (`qt.route_min_congestion`, quelques ms).
- **Score → QUBO.** Ce n'est pas un QUBO : le kit fournit un **substitut** (`qt.build_network_qubo`) qui
  vaut `−Σ t_ij x_ij`, plus des pénalités de degré.
- **Structure exploitable.** Une topologie valide est l'union de deux permutations sans point fixe qui ne
  coïncident jamais. L'échange de 2 arcs `(a→b),(c→d) ⇒ (a→d),(c→b)` préserve tous les degrés.

## 0. Références sur le problème lui-même

| Référence | Contenu et résultats |
|---|---|
| **Bienstock et al.**, *Computational experience with a difficult mixed-integer multicommodity flow problem*, Mathematical Programming, janv. 1995. DOI [10.1007/BF01585766](https://doi.org/10.1007/BF01585766) | Problème d'origine (n=24, p=2, demandes dans {0,…,100}). Approche par plans coupants polyédraux. L'instance à 24 nœuds n'est toujours pas prouvée optimale. |
| **Koch et al.**, *The Quantum Optimization Benchmarking Library*, Nature Computational Science, juin 2026. DOI [10.1038/s43588-026-00991-1](https://doi.org/10.1038/s43588-026-00991-1). Prépublication *The Intractable Decathlon*, avr. 2025, DOI [10.48550/arXiv.2504.03832](https://doi.org/10.48550/arXiv.2504.03832) | Formulation MIP officielle (§4.8). Gurobi 11 avec 2 h de limite ne prouve l'optimum que **jusqu'à n=9**. Les relaxations LP des formulations multi-flots sont **faibles**. Approches classiques citées : Benders (Magnanti et al. 1986), plans coupants, génération de colonnes. |
| **Gupta**, soumission QOBLIB `08-network/submissions/20260818_ParallelTempering_Gupta` (pas de papier ni de DOI). Code : <https://github.com/mnn31/qoblib-solvers/tree/main/network> | **Détient les meilleurs connus** pour network11 et network13 à network23. Le LP sert d'énergie. 8 répliques, températures géométriques de 6 % à 0,2 % de l'incumbent. Mouvements : 2-exchanges et 3-exchanges qui préservent les degrés, donc toujours faisables. Échange de répliques tous les 40 coups. 5 runs de 40 min sur un seul cœur, seeds 0 à 4, départ aléatoire. **C'est la barre classique à battre.** |

## A. Essais des pistes suggérées par le notebook de référence

### A1. Meilleurs substituts : apprendre le QUBO à partir de l'oracle LP

| Référence | Résultats |
|---|---|
| **Kitai et al.**, *Designing metamaterials with quantum annealing and factorization machines*, Phys. Rev. Research 2, 013319, mars 2020. DOI [10.1103/PhysRevResearch.2.013319](https://doi.org/10.1103/PhysRevResearch.2.013319) | Méthode **FMQA**. Une factorization machine (FM) apprend un QUBO qui imite une fonction boîte noire coûteuse (une simulation électromagnétique). Ce QUBO est optimisé par recuit quantique, le candidat trouvé est évalué puis ajouté aux données. Résultat : de meilleures structures de radiateurs sélectifs que les designs de référence, avec peu d'évaluations. |
| **Nüßlein et al.**, *Black Box Optimization Using QUBO and the Cross Entropy Method* (BOX-QUBO), LNCS (ICCS 2023), juin 2023. DOI [10.1007/978-3-031-36030-5_4](https://doi.org/10.1007/978-3-031-36030-5_4) | Le QUBO substitut est appris surtout par **classification** (bonnes contre mauvaises solutions, entropie croisée) plutôt que par régression, ce qui convient mieux à la faible capacité d'un QUBO. Meilleur que l'état de l'art (dont FMQA et BOCS) sur les 4 domaines testés. |
| **Tamura et al.**, *Black-box optimization using factorization and Ising machines* (revue), Applied Physics Reviews 13, 021307. Prépublication juil. 2025. DOI [10.1063/5.0275450](https://doi.org/10.1063/5.0275450) | Revue de FMQA avec les paquets Python disponibles. Applications à des variables binaires et entières, et à des graphes et réseaux (via un VAE binaire). |
| **Hama et al.**, *Subsampling Factorization Machine Annealing*, Phys. Rev. Research 8, 013187. Prépublication août 2025. DOI [10.1103/qgpq-6dmr](https://doi.org/10.1103/qgpq-6dmr) | La FM est entraînée sur des sous-échantillons des données, ce qui améliore l'équilibre exploration/exploitation. Plus rapide et plus précis que FMQA sur leurs benchmarks. |
| **Baptista et al.**, *Bayesian Optimization of Combinatorial Structures* (BOCS), ICML, juin 2018. DOI [10.48550/arXiv.1806.08838](https://doi.org/10.48550/arXiv.1806.08838) | Modèle bayésien de second ordre (donc un QUBO) appris sur des évaluations coûteuses. La fonction d'acquisition est optimisée par SDP. Meilleur que les méthodes combinatoires et bayésiennes de référence. |

**Ce qu'on peut transposer.** L'oracle (le LP) ne coûte que quelques millisecondes, donc on peut générer
des dizaines de milliers de couples (topologie, score) depuis SA ou PT. Il suffit ensuite d'apprendre un
QUBO de 552 variables pour network24.

### A2. Rétroaction du LP, façon Benders

| Référence | Résultats |
|---|---|
| **Zhao et al.**, *Hybrid Quantum Benders' Decomposition For Mixed-integer Linear Programming*, IEEE WCNC, avr. 2022. DOI [10.1109/WCNC51071.2022.9771632](https://doi.org/10.1109/WCNC51071.2022.9771632) | Le problème maître de Benders (avec les coupes) est réécrit en QUBO et résolu sur D-Wave, les sous-problèmes LP restent classiques. Faisabilité démontrée sur de petits MILP, avec une garantie sur la qualité de la solution. |
| **Joliot et al.**, *Enhancing the Performance of Quantum Neutral-Atom-Assisted Benders Decomposition*, IEEE CoDIT, juil. 2025. DOI [10.1109/CoDIT66093.2025.11321887](https://doi.org/10.1109/CoDIT66093.2025.11321887) | Améliorations : bornes resserrées, encodage exponentiel sans variables d'écart, coupes de faisabilité de type L-shaped, **réglage constructif de la pénalité**, plusieurs coupes par itération. Faisabilité de 68 % à **100 %**, optimalité de 52 % à **86 %**. |
| **Dixit et al.**, *Quantum computing for transport network design problems*, Scientific Reports 13, juil. 2023. DOI [10.1038/s41598-023-38787-2](https://doi.org/10.1038/s41598-023-38787-2) | **Architecture la plus proche de la nôtre.** Problème en deux niveaux : le choix des liens en QUBO (D-Wave), la congestion (équilibre des usagers) calculée classiquement. Sur Sioux Falls (24 nœuds, 76 liens), le recuit quantique pur égale la recherche tabou (écart de 0 à 0,08 %) en 0,20 à 0,22 s au lieu de 0,30 à 0,40 s. Le solveur hybride D-Wave passe jusqu'à environ 900 liens (Anaheim, Winnipeg), et prend l'avantage en temps au-delà d'environ 500 liens. |
| **Gambella et al.**, *Multiblock ADMM Heuristics for Mixed-Binary Optimization on Classical and Quantum Computers*, IEEE TQE, 2020 (mois non vérifié). DOI [10.1109/TQE.2020.3033139](https://doi.org/10.1109/TQE.2020.3033139) | ADMM découpe un problème mixte en une partie binaire (QUBO, résolue par QAOA ou VQE) et une partie continue convexe résolue classiquement. Validé en simulation Qiskit. |

**Mise en garde.** QOBLIB indique que la relaxation LP est faible sur ce problème, donc les coupes de
Benders classiques seront peu serrées. Il vaut mieux se servir des **variables duales du LP** (charge et
prix des arcs saturés) comme **signal de repondération** du QUBO.

### A3. Encodages valides par construction et mixers qui respectent les contraintes

| Référence | Résultats |
|---|---|
| **Hadfield et al.**, *From the Quantum Approximate Optimization Algorithm to a Quantum Alternating Operator Ansatz*, Algorithms 12(2):34, févr. 2019. DOI [10.3390/a12020034](https://doi.org/10.3390/a12020034) | Papier fondateur et théorique : des mixers restreints au sous-espace faisable (one-hot, permutations, ordonnancement). |
| **Wang et al.**, *XY mixers: Analytical and numerical results for the quantum alternating operator ansatz*, Phys. Rev. A 101, 012320, janv. 2020. DOI [10.1103/PhysRevA.101.012320](https://doi.org/10.1103/PhysRevA.101.012320) | Sur la coloration de graphes, les mixers XY font **nettement mieux** que le mixer X. Un état W initial fait mieux qu'un état initial classique. Implémentation exacte en profondeur O(κ). |
| **Bärtschi et al.**, *Grover Mixers for QAOA: Shifting Complexity from Mixer Design to State Preparation*, IEEE QCE, oct. 2020. DOI [10.1109/QCE49297.2020.00020](https://doi.org/10.1109/QCE49297.2020.00020) | GM-QAOA fonctionne dès qu'on sait préparer la superposition uniforme des solutions faisables, et les permutations se préparent sur O(n²) qubits. Bat les QAOA existants sur le k-vertex-cover et le rééquilibrage de portefeuille. |
| **Bärtschi et al.**, *Deterministic Preparation of Dicke States*, LNCS (FCT 2019), juil. 2019. DOI [10.1007/978-3-030-25027-0_9](https://doi.org/10.1007/978-3-030-25027-0_9) | Circuit déterministe pour préparer \|D^n_k⟩, la superposition uniforme des chaînes de poids k, en profondeur O(n). C'est la brique qui permet de satisfaire « exactement 2 arcs sortants » dès l'état initial. |
| **Choi et al.**, *Locally acting Grover mixers for constraint-preserving QAOA*, Quantum Sci. Technol., nov. 2026. DOI [10.1088/2058-9565/aebe5e](https://doi.org/10.1088/2058-9565/aebe5e) | On encode **une partie des contraintes** dans un état initial produit sur des sous-systèmes disjoints, avec un mixer de Grover local par bloc. Sur le TSP et l'exact cover, les probabilités de succès sont comparables au GM-QAOA global, avec moins de portes. Comparé aux mixers XY-ring partitionnés. |
| **Onah et al.**, *Fundamental Limitations of QAOA on Constrained Problems and a Route to Exponential Enhancement*, nov. 2025. DOI [10.48550/arXiv.2511.17259](https://doi.org/10.48550/arXiv.2511.17259) | Preuve que le QAOA générique garde une probabilité de faisabilité **exponentiellement faible** sur les problèmes de permutations. CE-QAOA (départ one-hot avec un mixer XY par bloc) garantit une faisabilité d'au moins n!/nⁿ, soit un gain exp(Ω(n²)). |

**Ce que Divi 0.16.2 fournit déjà.** `divi.hamiltonians.xy_mixer`, `build_block_xy_mixer_edges`,
`divi.qprog.initial_states.WState` (et une classe de base `InitialState` qu'on peut dériver), un
`QAOA.mixer_hamiltonian` réassignable, et un CE-QAOA pour le TSP dans `divi/qprog/problems/_routing.py`.
Il n'y a **pas d'état de Dicke**. Pour l'ajouter, il faut dériver `InitialState` (circuit de Bärtschi et al.).

### A4. Propositions quantiques dans une recherche locale

| Référence | Résultats |
|---|---|
| **Shaydulin et al.**, *Network Community Detection on Small Quantum Computers*, Advanced Quantum Technologies, juin 2019. DOI [10.1002/qute.201900029](https://doi.org/10.1002/qute.201900029) | **Quantum Local Search (QLS)** : un petit sous-problème autour de la solution courante est résolu sur 16 qubits (IBM) ou sur D-Wave 2000Q. Graphes **jusqu'à 410 nœuds**, avec une qualité comparable aux meilleurs solveurs, optimale dans certains cas. |
| **Podobrii et al.**, *Qubit-efficient quantum local search for combinatorial optimization*, févr. 2025. DOI [10.48550/arXiv.2502.02245](https://doi.org/10.48550/arXiv.2502.02245) | Un voisinage de l coups est exploré avec seulement ⌈log₂ l⌉ qubits, en variationnel. Ajouter des qubits élargit le voisinage. Résolution, en simulation, de la plus grosse instance de coloration de graphes jamais attaquée par une méthode quantique. |
| **Liu et al.**, *Reinforcement Learning Quantum Local Search*, avr. 2023. DOI [10.48550/arXiv.2304.06473](https://doi.org/10.48550/arXiv.2304.06473) | Un agent d'apprentissage par renforcement choisit quel sous-problème confier au quantique. Meilleur ratio d'approximation moyen que le tirage au hasard, sur des modèles d'Ising aléatoires complets. |
| **Liu et al.**, *Parallel Quantum Local Search via Evolutionary Mechanism*, juin 2024. DOI [10.48550/arXiv.2406.06445](https://doi.org/10.48550/arXiv.2406.06445) | Plusieurs QLS tournent en parallèle, et on repart du meilleur résultat à chaque génération. Convergence accélérée sur des problèmes d'Ising. Un bon cadre pour les batchs cloud. |
| **Layden et al.**, *Quantum-enhanced Markov chain Monte Carlo*, Nature 619, 282–287, juil. 2023. DOI [10.1038/s41586-023-06095-4](https://doi.org/10.1038/s41586-023-06095-4) | Le processeur quantique **propose** les mouvements de la chaîne, l'ordinateur classique les **accepte ou les refuse** (Metropolis), ce qui préserve la loi de Boltzmann. Converge en **moins d'itérations** que les propositions classiques locales ou uniformes, en simulation et sur processeur supraconducteur IBM. |
| **Orfi et al.**, *Bounding speedup of quantum-enhanced Markov chain Monte Carlo*, mars 2024. DOI [10.48550/arXiv.2403.03087](https://doi.org/10.48550/arXiv.2403.03087) | Résultat contre : **aucune accélération** n'est possible dans le pire cas non structuré, pour toute proposition quantique unitale. Tout gain doit venir de la structure du problème. |

**Ce qu'on peut transposer.** Sur network24 il y a 48 arcs, donc au plus C(48,2) = 1128 échanges 2-opt
candidats, soit environ **11 qubits** avec l'encodage de Podobrii et al. Les propositions quantiques
peuvent alimenter le parallel tempering de Gupta.

### A5. Pénalités, réglage de λ et characterization

| Référence | Résultats |
|---|---|
| **Alessandroni et al.**, *Alleviating the quantum Big-M problem*, npj Quantum Information, juil. 2025. DOI [10.1038/s41534-025-01067-0](https://doi.org/10.1038/s41534-025-01067-0) | Trouver le M (λ) optimal est **NP-difficile**. Les auteurs proposent une traduction fondée sur une relaxation SDP, qui donne des gaps spectraux plus grands de plusieurs ordres de grandeur. Sur 6 qubits IonQ, meilleur temps de résolution et meilleure qualité. |
| **Ayodele**, *Penalty Weights in QUBO Formulations: Permutation Problems*, LNCS (EvoCOP), avr. 2022. DOI [10.1007/978-3-031-04148-8_11](https://doi.org/10.1007/978-3-031-04148-8_11) | Nouvelles règles **statiques** pour fixer λ sur les problèmes de permutations, plus efficaces que les règles existantes avec des solveurs qui retournent un bit à la fois. |
| **Montañez-Barrera et al.**, *Unbalanced penalization: a new approach to encode inequality constraints of combinatorial problems for quantum optimization algorithms*, Quantum Sci. Technol. 9, 025022, avr. 2024. DOI [10.1088/2058-9565/ad35e4](https://doi.org/10.1088/2058-9565/ad35e4) | Encode des inégalités **sans variables d'écart** grâce à une pénalité asymétrique. Sur le bin packing, la méthode atteint 29 objets avec D-Wave, plus que la version avec variables d'écart. Utile pour mettre `charge(arc) ≤ z` dans le QUBO. |
| **Broesamle et al.**, *Quantum Optimization in Loc(Q)ation Science: QUBO Formulations, Benchmark Problems, and a Computational Study*, févr. 2026. DOI [10.48550/arXiv.2602.10951](https://doi.org/10.48550/arXiv.2602.10951) | QUBO pour la localisation et la conception de réseau. **Borne serrée sur λ** qui garantit l'équivalence avec le programme en nombres entiers. Deux stratégies de warm start de QAOA **à partir de la relaxation LP**, efficaces sur le p-médian et la localisation à coût fixe. |
| **Rezk et al.**, *GNN-Guided Graph Coarsening and Adaptive QUBO Penalties for the CVRPTW on a Quantum Annealer*, sept. 2026. DOI [10.48550/arXiv.2609.04593](https://doi.org/10.48550/arXiv.2609.04593) | Augmenter λ uniformément a peu d'effet. Ce qui compte, c'est l'**écart entre les coefficients** : en normalisant les contraintes actives et en retirant les autres, les violations brutes passent de 33,0 à 0,06 à budget égal. |

## B. Méthodes hors pistes suggérées

### B1. Compression du nombre de qubits

| Référence | Résultats |
|---|---|
| **Sciorilli et al.**, *Towards large-scale quantum optimization solvers with few qubits* (PCE), Nature Communications 16, 476, janv. 2025. DOI [10.1038/s41467-024-55346-z](https://doi.org/10.1038/s41467-024-55346-z) | m = O(nᵏ) variables tiennent sur n qubits, et les plateaux stériles sont atténués. En simulation, 7000 variables donnent des résultats compétitifs avec les solveurs classiques. Sur matériel, 2000 variables sur **17 qubits** à ions piégés, avec un ratio MaxCut au-dessus de 0,941. |
| **Lizzio Bosco et al.**, *Efficiently Simulable Pauli Correlation Encoding*, juil. 2026. DOI [10.48550/arXiv.2607.20409](https://doi.org/10.48550/arXiv.2607.20409) | Variantes « déquantisées » de PCE (circuits matchgate ou IQP) simulables classiquement, avec de bonnes solutions jusqu'à des milliers de variables (MaxCut, MIS, sac à dos, Max3SAT). **C'est la baseline classique à opposer à tout résultat PCE.** |
| **Tan et al.**, *Qubit-efficient encoding schemes for binary optimisation problems*, Quantum 5, 454, mai 2021. DOI [10.22331/q-2021-05-04-454](https://doi.org/10.22331/q-2021-05-04-454) | Encodage en O(log n) qubits : 64 variables sur 7 qubits, et un MaxCut de 42 variables sur 8 qubits. |
| **Glos et al.**, *Space-efficient binary optimization for variational quantum computing*, npj Quantum Information, avr. 2022. DOI [10.1038/s41534-022-00546-y](https://doi.org/10.1038/s41534-022-00546-y) | Le TSP passe de n² qubits à **O(n log n)** grâce à l'encodage binaire des permutations, au prix de circuits plus profonds. Les auteurs proposent aussi des encodages intermédiaires. |
| **Chancellor**, *Domain wall encoding of discrete variables for quantum annealing and QAOA*, Quantum Sci. Technol. 4, 045004, août 2019. DOI [10.1088/2058-9565/ab33c2](https://doi.org/10.1088/2058-9565/ab33c2) | Une variable discrète à k valeurs coûte k−1 qubits, avec des termes à deux corps seulement et des mixers qui restent dans l'espace valide. Performances égales ou meilleures que le one-hot (ordonnancement et coloration sur Chimera et Pegasus). |
| **Friedl et al.**, *Succinct QUBO formulations for permutation problems by sorting networks*, mars 2026. DOI [10.48550/arXiv.2603.07579](https://doi.org/10.48550/arXiv.2603.07579) | Permutations encodées en **O(n log² n)** variables via des réseaux de comparaison-échange. Chaque permutation correspond à une affectation unique, et on peut ajouter une contrainte d'**absence de point fixe**. |

### B2. Décomposition à grande échelle

| Référence | Résultats |
|---|---|
| **Zhou et al.**, *QAOA-in-QAOA: Solving Large-Scale MaxCut Problems on Small Quantum Machines*, Phys. Rev. Applied 19, 024027, févr. 2023. DOI [10.1103/PhysRevApplied.19.024027](https://doi.org/10.1103/PhysRevApplied.19.024027) | Les sous-graphes sont résolus en parallèle, puis la fusion est elle-même un MaxCut résolu par QAOA. Compétitif ou meilleur que le classique vers **2000 nœuds**. |
| **Kandora et al.**, *From Cables to Qubits: A Decomposed Variational Quantum Optimization Pipeline*, oct. 2025. DOI [10.48550/arXiv.2510.21901](https://doi.org/10.48550/arXiv.2510.21901) | Flots multi-produits découpés en sous-problèmes à un seul produit. Le **PUBO** (termes d'ordre supérieur, sans qubits auxiliaires) reste faisable sur toutes les seeds, contrairement au QUBO global, mais demande des circuits plus profonds. |

### B3. Agrégation des mesures et warm start

| Référence | Résultats |
|---|---|
| **Barkoutsos et al.**, *Improving Variational Quantum Optimization using CVaR*, Quantum 4, 256, avr. 2020. DOI [10.22331/q-2020-04-20-256](https://doi.org/10.22331/q-2020-04-20-256) | On optimise la queue α de la distribution d'énergie (CVaR) plutôt que la moyenne. Convergence plus rapide et meilleures solutions sur tous les problèmes testés, en simulation comme sur matériel. |
| **Egger et al.**, *Warm-starting quantum optimization*, Quantum 5, 479, juin 2021. DOI [10.22331/q-2021-06-17-479](https://doi.org/10.22331/q-2021-06-17-479) | QAOA part de l'état correspondant à une relaxation continue. Le gain est net surtout à faible profondeur (portefeuille, et RQAOA sur MaxCut avec arrondi Goemans-Williamson). |
| **Bravyi et al.**, *Obstacles to Variational Quantum Optimization from Symmetry Protection*, Phys. Rev. Lett. 125, 260505, déc. 2020. DOI [10.1103/PhysRevLett.125.260505](https://doi.org/10.1103/PhysRevLett.125.260505) | Montre les limites du QAOA local et propose **RQAOA**, qui fixe les variables une à une à partir des corrélations mesurées. Bien meilleur que QAOA sur les modèles d'Ising frustrés. |

## Synthèse des pistes

| Piste | Références clés | Hypothèse |
|---|---|---|
| Substitut appris à partir du LP (FMQA, BOX-QUBO) | Kitai 2020, Nüßlein 2023, Tamura 2025, Hama 2025, Baptista 2018 | H1 |
| Substitut analytique enrichi et réglage de λ | Alessandroni 2025, Ayodele 2022, Broesamle 2026, Rezk 2026, Montañez-Barrera 2024 | H2 |
| Repondération par les duales du LP (Benders) | Zhao 2022, Joliot 2025, Dixit 2023, Gambella 2020 | H3 |
| Dicke par ligne, mixer XY ou Grover local | Hadfield 2019, Wang 2020, Bärtschi 2019 et 2020, Choi 2026, Onah 2025 | H4 |
| Encodage compact des deux permutations | Glos 2022, Chancellor 2019, Friedl 2026 | H5 |
| PCE à l'échelle de network24, avec CVaR et baseline déquantisée | Sciorilli 2025, Lizzio Bosco 2026, Tan 2021, Barkoutsos 2020 | H6 |
| Quantum Local Search sur les 2-exchanges | Shaydulin 2019, Podobrii 2025, Liu 2023 et 2024 | H7 |
| Propositions quantiques dans le parallel tempering | Layden 2023, Orfi 2024, Gupta (QOBLIB) | H8 |
| Partitionnement guidé par la structure, warm start depuis le LP | Zhou 2023, Kandora 2025, Egger 2021, Bravyi 2020, Broesamle 2026 | H9 |
