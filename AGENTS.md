# AGENTS.md: Qoro × PushQuantum Hackathon 2026

Contexte et règles pour toute personne ou tout agent IA qui travaille sur ce repo. À lire avant de
toucher au code.

## 1. Le hackathon

**Mission :** prendre un problème du benchmark [QOBLIB](https://github.com/ZIB-AOPT/QOBLIB), le résoudre
sur **la plus grosse instance possible**, au plus près du **meilleur résultat publié** (ou mieux). L'outil
central est le **partitionnement** avec [Divi](https://github.com/QoroQuantum/divi) (Qoro Quantum,
[docs](https://divi.readthedocs.io)) : on découpe un QUBO trop gros pour un seul circuit en petits
programmes QAOA/PCE qui tournent en parallèle sur le cloud Qoro, puis on recolle les morceaux.

### Les deux problèmes

Les deux sont explorés **en parallèle, sur des branches séparées** (voir §4).

| | 06 · Optimisation de portefeuille | 08 · Network design |
|---|---|---|
| Notebook de référence | `references/01_portfolio_optimisation.ipynb` | `references/02_network_design.ipynb` |
| Taille | 3 à 400 actifs, 2 à 15 jours : 58 à environ 36 000 variables binaires | `network05` à `network24` : 20 à 552 variables |
| Contraintes | 0 à 3 unités par actif et par sens ; limites de capital et de budget à chaque période | Chaque nœud a exactement 2 liens sortants et 2 entrants ; les flots livrent toute la demande via les liens choisis |
| Score (plus bas = mieux) | Objectif officiel : risque − rendement + coûts de transaction, de vente à découvert et de liquidation − intérêts sur le cash | Flot maximal sur un lien, en unités de 1/1000 |
| Référence | `po_a010_t10_orig`, B=4, λ=1e-4 : 710 variables, meilleur connu **−69 482** | `network12` : 132 variables, meilleur connu **276 474** ; `network24` : 552 variables, **663 688** |
| Ce qui est publié | Meilleurs connus jusqu'à 50 actifs, **rien à 200 et 400 actifs** (terrain vierge) | Optima prouvés jusqu'à `network10` ; au-delà, meilleurs connus obtenus par parallel tempering (durs à battre) |
| Pipeline | Modèle → QUBO (pénalités λ) → baseline classique → PCE ou QAOA partitionné → repair → `.sol` | QUBO de topologie (`LinearConstraint`) → échantillonnage → LP de routage exact → `.sol` |

Tables des meilleurs connus :
[portefeuille](https://github.com/ZIB-AOPT/QOBLIB/blob/main/06-portfolio/solutions/README.md),
[network](https://github.com/ZIB-AOPT/QOBLIB/blob/main/08-network/solutions/README.md).

### Désignation du gagnant

- **Échelle :** taille de l'instance résolue (variables binaires) et **qubits du plus gros programme quantique**.
- **Qualité :** `gap = (score − best_known) / |best_known|`. 0 % = égalité, négatif = record battu
  (`hackathon.utils.gap`).
- **À rendre, pour chaque résultat :**
  1. le fichier `.sol` au format QOBLIB, validé par l'arbitre ;
  2. l'instance, sa taille (variables, qubits max) et son score à côté du meilleur connu ;
  3. la méthode et les paramètres (seed compris) pour qu'on puisse reproduire le résultat.

  Les modalités exactes de remise sont annoncées par Qoro sur place.

### Les outils Divi à connaître (voir `references/00_main_qubo_101.ipynb`)

- **Backends :** `MaestroSimulator` (local, gratuit) ou `QoroService` (cloud, **consomme des crédits**).
  `hackathon.utils.make_backend(use_cloud=...)` choisit entre les deux.
- **Characterization Service** (`characterize_and_validate`, cloud uniquement) : analyse un QUBO, renvoie
  une baseline classique, les variables qu'on peut fixer, la structure des partitions, des angles QAOA pour
  un warm start et un λ recommandé. Le coût augmente avec la taille du QUBO. Un rapport déjà calculé se
  récupère gratuitement avec `get_characterization_result(job_id, service=...)`.
- **QAOA :** à traiter comme un échantillonneur, en le jugeant sur ses meilleurs bitstrings. Il peut
  démarrer à froid ou à partir des angles du service (warm start).
- **PCE (Pauli Correlation Encoding) :** encode N variables sur bien moins de qubits (`DenseEncoding` :
  log₂N ; `PolyEncoding` : environ √2N). Trier ses sorties par énergie, pas par probabilité.
- **`PartitioningProgramEnsemble`** : décomposition (`CommunityDecomposer` ou les décomposeurs `hybrid`
  de D-Wave), puis un sous-programme par partition, puis recollage par beam search, puis recherche locale
  sur le QUBO complet.
- **`MonteCarloOptimizer`** : envoie une population de circuits en un seul batch par itération, bien
  mieux adapté au cloud que COBYLA. Le nombre de crédits suit le nombre de circuits.

### Règles d'or

1. **`references/` est en lecture seule.** C'est le kit original de Qoro. `references/qoblib_tools.py` est
   **l'arbitre** (portage des checkers officiels de QOBLIB) : on ne le modifie jamais. On l'importe via
   `from hackathon.referee import qt`.
2. **Toujours comparer à une baseline classique** (SA, repair, recherche locale) avant d'attribuer un gain
   au quantique. Le kit insiste : le classique fait l'essentiel du travail.
3. **Un résultat non reproductible ne compte pas.** Chaque run passe par `hackathon.utils.save_run`, qui
   enregistre le `.sol` et ses métadonnées.
4. **Les crédits cloud sont limités.** On met au point en local (`use_cloud=False`) et on ne passe au cloud
   qu'une fois le pipeline validé.
5. **Pas de secrets dans git.** La clé `QORO_API_KEY` vit dans `.env` (ignoré par git, modèle dans
   `.env.example`). Ne jamais commiter de notebook qui contient une clé.

## 2. Structure du repo

```
pushquantum-hackathon-2026/
├── references/              # Kit original Qoro, NE PAS MODIFIER
│   ├── 00_main_qubo_101.ipynb       # Tutoriel Divi : QUBO, characterization, QAOA, PCE, partitionnement
│   ├── 01_portfolio_optimisation.ipynb
│   ├── 02_network_design.ipynb
│   ├── qoblib_tools.py              # L'ARBITRE : chargeurs, scoreurs officiels, QUBO builders, écriture .sol
│   └── README.md                    # Règles du hackathon (scoring, formats .sol)
├── docs/                    # Documentation de travail (humains + agents)
│   └── network/                     # state-of-the-art.md, hypothesis.md (H0, H1 + backlog), metrics.md, workflow.md
│       └── hypothesis/<id>/             # process.md + result.md par hypothèse (modèles dans _template/)
├── src/network-experiments/ # Expériences network, un paquet par hypothèse (h0/, h1/…), hors paquet installé :
│                            #   PYTHONPATH=src/network-experiments (voir docs/network/workflow.md)
├── src/hackathon/           # Notre code réutilisable, installé en mode éditable par `uv sync`
│   ├── referee.py                   # `from hackathon.referee import qt` : importe l'arbitre sans le copier
│   ├── utils.py                     # .env, make_backend(), gap(), save_run(), git_hash()
│   └── solvers/                     # Un module par problème : portfolio.py (branches portfolio/*),
│                                    #   network.py (branches network/*). Code partagé dans utils.py.
├── notebooks/               # Explorations (marimo de préférence, jupyter accepté)
│                            #   Les copies des notebooks de référence y sont ignorées par git
│                            #   network/<id>/ : notebooks d'une hypothèse network
├── scripts/                 # Runs reproductibles en CLI, par ex.
│                            #   `uv run scripts/run_portfolio.py --instance po_a010_t10_orig --seed 0`
├── results/                 # Sorties des runs, COMMITÉES
│   ├── portfolio/                   # <timestamp>_<nom officiel>.sol + .json de métadonnées
│   └── network/
├── tests/                   # pytest : l'arbitre reproduit les références, nos .sol sont valides
├── .env.example             # Modèle pour .env (QORO_API_KEY)
├── pyproject.toml / uv.lock # Dépendances (uv), Python 3.12
└── README.md                # Setup rapide + tableau des meilleurs résultats
```

### Où mettre quoi

- **On explore, on visualise :** `notebooks/`. Un notebook importe depuis `hackathon.*` et ne contient
  pas de logique qui doive être réutilisée ailleurs.
- **Ça marche et ça resservira :** on le déplace dans `src/hackathon/solvers/<problème>.py` (ou dans
  `utils.py` si ça sert aux deux problèmes).
- **Un run qu'on veut pouvoir rendre :** un script dans `scripts/` qui appelle les solveurs et termine par
  `save_run(...)`.
- **Les données QOBLIB** sont téléchargées par l'arbitre à la première utilisation, dans
  `references/qoblib_data/` (ignoré par git).
- **Expériences network (H0, H1, puis backlog) :** conventions spécifiques, décrites dans
  `docs/network/workflow.md` (code dans `src/network-experiments/<id>/`, notebooks dans
  `notebooks/network/<id>/`, runs dans `results/network/bench/<id>/`).

### Format des résultats

`save_run(problem, sol_name, sol_text, metadata)` écrit `results/<problem>/<timestamp>_<sol_name>` et un
`.json` à côté. Les clés attendues dans `metadata` sont `instance`, `n_vars`, `max_qubits`, `score`,
`best_known`, `method`, `params` et `seed`. La fonction ajoute `gap`, `git` (hash, avec `-dirty` si
l'arbre n'est pas propre), `timestamp` et `sol_file`.

Le nom officiel du `.sol` doit être conservé, car l'arbitre en déduit l'instance :
- portefeuille : `<instance>_b<budget>_l<lambda>.sol` (par ex. `po_a010_t10_orig_b004_l1e-4.sol`) ; garder
  les lignes d'en-tête `instance`, `budget`, `lambda` ;
- network : `network<NN>.sol` (par ex. `network12.sol`).

Vérifier un fichier avant de le rendre : voir la section *Scoring* de `references/README.md`.

## 3. Environnement et commandes

- **Python 3.12** (fixé par `.python-version`). Divi est figé à **`qoro-divi==0.16.2`** : les noms changent
  d'une version mineure à l'autre, **ne pas le mettre à jour**.
- Gestion des dépendances : **uv uniquement** (`uv add <pkg>`, `uv add --dev <pkg>`), jamais `pip install`.

```bash
uv sync                          # installe tout (dev compris) + le paquet `hackathon` en éditable
uv run pytest                    # smoke tests (téléchargent des données QOBLIB la première fois)
uv run ruff check src tests scripts && uv run ruff format src tests scripts
uv run ty check src              # vérification de types
uv run marimo edit notebooks/    # notebooks marimo
uv run jupyter lab               # ou jupyter
```

Les `SyntaxWarning` levés à l'import par des dépendances D-Wave (`plucky`, `homebase`…) sont sans
conséquence.

### Lire des PDF (papiers, docs)

Pour lire un PDF (article arXiv, documentation…), **préférer `markitdown`** (dépendance de dev
`markitdown[pdf]`) à une lecture directe du PDF : le Markdown produit coûte bien moins de tokens.

```bash
uv run markitdown papier.pdf -o /tmp/papier.md   # puis lire /tmp/papier.md (par morceaux si long)
curl -sL https://arxiv.org/pdf/2401.09421 -o /tmp/p.pdf && uv run markitdown /tmp/p.pdf > /tmp/p.md
```

Ne pas commiter les PDF ni leurs conversions (les garder dans `/tmp`).

## 4. Git

### Branches

- `main` : base commune stable (setup, `utils.py`, `referee.py`, tests). Rien d'expérimental.
- **Portefeuille :** branches `portfolio/<sujet>` (par ex. `portfolio/pce-baseline`,
  `portfolio/a200-partitioning`).
- **Network :** branches `network/<sujet>` (par ex. `network/sa-baseline`, `network/n24-qaoa`).
- Le code partagé (utils, conventions) passe par `main`, puis chaque groupe de branches rebase dessus.
  On ne mélange pas portefeuille et network dans une même branche.

### Commits

- Messages au format **Conventional Commits** : `type(scope): description`, par ex.
  `feat(portfolio): add PCE pipeline`, `chore(uv): pin python 3.12`, `fix(network): repair degree constraint`.
- **Ne pas signer les commits :** pas de trailer `Co-Authored-By:`, pas de mention « Generated with … »
  ni d'autre attribution IA dans les messages de commit ou les descriptions de PR, et pas de signature
  GPG (`-S`). Le commit est écrit au nom de l'auteur git configuré, sans rien ajouter.
- Commiter les `.sol` et `.json` de `results/` qui méritent d'être gardés, en particulier ceux qu'on
  compte rendre.

## 5. Network (problème 08)

> Section à mettre à jour à la fusion des branches, au fil des résultats. Profil **hackathon** : peu
> d'hypothèses, peu de seeds, des budgets courts.

### Mission

Rendre un `network<NN>.sol` valide (`qt.check_network_solution`, `save_run`) sur la **plus grosse instance
possible** (cible `network24` : 552 variables, meilleur connu **663 688**), **au plus près du meilleur
connu**. Si un programme quantique est utilisé, il faut le plus de qubits possible et une ablation classique
qui montre son apport.

### Ce qu'il faut savoir

- **Topologie et routage sont deux problèmes séparés.**
  - Le choix de la topologie est combinatoire : un QUBO à n(n−1) variables.
  - Le routage est un LP exact, résolu en quelques ms (12 ms sur network12, 65 ms sur network24) : c'est
    l'arbitre.
  - Le QUBO du kit (`qt.build_network_qubo`) n'est qu'un **substitut** (`−Σ t_ij x_ij`).
- **Repère B1** (SA sur ce substitut, puis repair, puis LP, mesuré sur 100 lectures) :
  - network05 : optimum ;
  - network12 : +12,0 % de gap ;
  - network24 : +15,8 % de gap.

  En quelques secondes. Toute méthode doit faire mieux.
- Les meilleurs connus de network11 à network23 viennent d'un **parallel tempering** classique (voir
  `docs/network/state-of-the-art.md` §0). On ne le relance pas : le gap au meilleur connu sert de mesure.

### Documents de travail

- `docs/network/hypothesis.md` contient :
  - le profil hackathon et l'ordre de travail ;
  - **H0** (baseline minimale) et **H1** (substitut QUBO appris) ;
  - le backlog des autres pistes, dont le détail est au commit `29d82b9`.
- `docs/network/metrics.md` : les métriques (définition, clé JSON), les budgets par instance, le schéma
  JSON et la règle de gain sur 3 seeds.
- `docs/network/workflow.md` : l'id `h0`/`h1`, le worktree, `src/network-experiments/<id>/`, l'exécution
  locale puis cloud, les livrables et la checklist.
- `docs/network/state-of-the-art.md` : la revue de littérature. **Ne pas refaire la recherche.**
- `docs/network/hypothesis/<id>/` : `process.md` (au début) et `result.md` (à la fin). Les modèles sont
  dans `_template/`.

### Ordre de travail

1. **H0** : B0 et B1 sur `network05` et `network12`, en réutilisant le pipeline du kit et en recalculant le
   minimum.
2. **H1**, par étapes :
   1. `network05` avec la seed 0, pour vérifier ;
   2. `network12` avec la seed 0, pour régler ;
   3. `network12` avec les seeds 0, 1 et 2, pour évaluer face à B0 et B1 ;
   4. **consolidation** sur `network24` (sinon `network20`, puis `network16` : liste et budgets dans `metrics.md` §5) avec les seeds 0, 1 et 2. C'est le
      seul moment où l'on lance la grosse instance.
3. En local d'abord (Maestro) : **aucun circuit de plus de 24 qubits en local**. Le cloud seulement en consolidation, si
   nécessaire.
4. Selon les résultats, on choisit la prochaine hypothèse dans le backlog.

### État des hypothèses

| Hypothèse | Statut | Meilleur résultat |
|---|---|---|
| H0 baseline minimale (B0, B1) | À faire | — |
| H1 substitut appris (FMQA / BOX-QUBO) | À faire | — |
| Backlog H2 à H9 | Reporté | — |
