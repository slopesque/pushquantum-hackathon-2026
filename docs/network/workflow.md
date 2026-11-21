# Workflow commun des agents « network »

> Process commun à **tous** les agents qui expérimentent une hypothèse de [`hypothesis.md`](hypothesis.md).
> Le *quoi* (idée, protocole, critères de succès) est dans `hypothesis.md`. Le *comment mesurer* est dans
> [`metrics.md`](metrics.md). Ce document décrit le *où* et le *comment travailler*.

## 1. Identifiant de l'hypothèse

L'**id** d'une hypothèse est son nom en minuscules : `h0`, `h1`, …, `h9`. Il sert partout :

| Élément | Convention | Exemple (H7) |
|---|---|---|
| Branche | `network/<id>-<slug>`, avec le slug donné dans `hypothesis.md` | `network/h7-qls-2exchange` |
| Worktree | `../pushquantum-hackathon-2026-<id>` | `../pushquantum-hackathon-2026-h7` |
| Code | `src/network-experiments/<id>/` | `src/network-experiments/h7/` |
| Notebooks | `notebooks/network/<id>/` | `notebooks/network/h7/` |
| Documentation | `docs/network/hypothesis/<id>/process.md` et `result.md` | `docs/network/hypothesis/h7/` |
| Runs de benchmark | `results/network/bench/<id>/<méthode>.jsonl` | `results/network/bench/h7/qls_a.jsonl` |
| Solutions rendables | `results/network/<timestamp>_networkNN.sol` et `.json` (via `save_run`) | — |

Le socle H0 utilise la branche `network/h0-baseline`.

## 2. Mise en place : un worktree Git par hypothèse

Chaque agent travaille dans **son propre worktree**. Les agents peuvent ainsi tourner en parallèle sans
se gêner.

**Branche de base :**
- pour `h0`, la branche qui porte la documentation network (`network/hypothesis`, ou `main` une fois
  qu'elle y est fusionnée) ;
- pour `h1` à `h9`, la branche de H0 (`network/h0-baseline`) dès qu'elle existe, pour disposer des
  baselines et de l'instrumentation des métriques.

```bash
# depuis le dépôt principal
git worktree add ../pushquantum-hackathon-2026-<id> -b network/<id>-<slug> <branche-de-base>
cd ../pushquantum-hackathon-2026-<id>
uv sync                                    # .venv propre au worktree (paquet hackathon en éditable)
cp ../pushquantum-hackathon-2026/.env .    # facultatif : seulement pour la characterization ou le cloud (phase 2)
ln -s ../../pushquantum-hackathon-2026/references/qoblib_data references/qoblib_data  # cache QOBLIB partagé (facultatif)
```

Les fichiers ignorés par git (`.env`, `.venv/`, `references/qoblib_data/`) **ne sont pas copiés** dans un
worktree. Sans le lien symbolique, l'arbitre retélécharge les données au premier usage.

## 3. Organisation du code

`src/network-experiments/` n'est **pas** un paquet installé. Son nom contient un tiret, donc il n'est pas
importable directement. Chaque `<id>/` est en revanche un paquet Python (avec un `__init__.py`), qu'on
importe en ajoutant `src/network-experiments` au `PYTHONPATH`.

```
src/network-experiments/
├── h0/                 # socle commun : scorer avec cache et duales, mouvements, baselines B0–B3, métriques
│   ├── __init__.py
│   └── …
└── <id>/
    ├── __init__.py
    ├── …               # composants et utilitaires de l'hypothèse
    ├── run_*.py        # points d'entrée reproductibles (CLI, avec --instance, --seed, --method)
    └── tests/          # tests pytest de l'hypothèse
```

```bash
export PYTHONPATH=src/network-experiments
uv run python -m <id>.run_bench --instance network12 --seed 0 --method <m>
uv run pytest src/network-experiments/<id>/tests
uv run ruff check src/network-experiments/<id> && uv run ruff format src/network-experiments/<id>
```

**Règles :**
- On importe l'arbitre avec `from hackathon.referee import qt` et les utilitaires avec
  `from hackathon.utils import gap, make_backend, save_run`. Le socle H0 s'importe avec `from h0… import …`.
- **On ne modifie pas le code d'une autre hypothèse.** Si on a besoin de changer H0 (bug, ajout d'un
  utilitaire commun), on le décrit dans `result.md` (§ « Demandes de changement sur H0 ») au lieu de
  modifier `h0/` dans sa branche.
- Les notebooks (`notebooks/network/<id>/`, marimo de préférence) ne servent qu'à explorer et
  visualiser : la logique réutilisable va dans `src/network-experiments/<id>/`. Dans un notebook, ajouter
  `src/network-experiments` à `sys.path`.

## 4. Phases d'expérimentation

| Phase | Où | Limites | Statut |
|---|---|---|---|
| **1 · Local** | `MaestroSimulator`, `make_backend(use_cloud=False)` | Circuits **rapides à simuler** : par défaut **≤ 20 qubits par circuit**, et jamais un circuit qui prend plus de quelques secondes. Pas de cloud, pas de crédits | **Phase en cours** |
| **2 · Cloud** | `QoroService` (`make_backend(use_cloud=True)`) | Gros circuits, plus de 20 qubits | Plus tard, sur décision humaine |

**En phase 1 :**
- On peut quand même attaquer les **grosses instances** (`network16` à `network24`) si la méthode ne
  lance que de **petits circuits** (sous-problèmes partitionnés, QLS, propositions locales). Seule la
  taille des circuits est limitée, pas celle de l'instance.
- Les parties purement classiques (LP, SA, PT, apprentissage) n'ont pas de limite, en dehors des budgets
  de `metrics.md` §2.
- Si un critère de succès de `hypothesis.md` demande plus de 20 qubits (par exemple « S3 ≥ 30 » pour H6,
  ou `network06` en H4), il est marqué **« reporté à la phase 2 »** dans `result.md`, avec la commande
  exacte qui permettra de le lancer sur le cloud.
- La characterization (cloud, coûteuse) n'est pas lancée en phase 1. On la prépare (code et états de
  référence) pour la phase 2.

**En phase 2 :** les résultats cloud **s'ajoutent** au même `result.md` (section « Phase 2 »), avec
`backend = "qoro_cloud"` et les crédits consommés (C4).

## 5. Livrables d'une session

| Quand | Livrable | Modèle |
|---|---|---|
| **Au début**, avant de coder | `docs/network/hypothesis/<id>/process.md` : objectif, procédé d'implémentation, plan d'évaluation | [`hypothesis/_template/process.md`](hypothesis/_template/process.md) |
| Pendant | Code (`src/network-experiments/<id>/`), runs JSONL (`results/network/bench/<id>/`), `.sol` via `save_run` | `metrics.md` §6 |
| **À la fin** | `docs/network/hypothesis/<id>/result.md` : résultats, conclusion, suite | [`hypothesis/_template/result.md`](hypothesis/_template/result.md) |
| À la fin | Ligne `Statut` de l'hypothèse mise à jour dans `hypothesis.md`, avec un lien vers `result.md` | — |

`process.md` est **mis à jour** si le procédé change en cours de route : on ajoute une section « Écarts
au plan », on ne réécrit pas l'historique.

## 6. Checklist de fin de session

- [ ] Les tests de l'hypothèse passent : `uv run pytest src/network-experiments/<id>/tests`.
- [ ] `ruff check` et `ruff format` sont propres sur `src/network-experiments/<id>`.
- [ ] Chaque run de `result.md` correspond à une ligne JSONL de `results/network/bench/<id>/`, conforme
      à `metrics.md` §6, sur 5 seeds et avec les budgets standard (ou un écart explicitement signalé).
- [ ] Une ablation classique est présente pour chaque affirmation de gain quantique (A1 à A3).
- [ ] Tout `.sol` mentionné est validé par `qt.check_network_solution` et enregistré par `save_run`.
- [ ] `result.md` donne une conclusion selon `metrics.md` §5 et liste les points reportés à la phase 2.
- [ ] La ligne `Statut` de l'hypothèse est à jour dans `hypothesis.md`. Ne pas toucher au tableau d'état
      d'`AGENTS.md` §5 : il est mis à jour à la fusion, ce qui évite les conflits entre branches.
- [ ] Le travail est commité sur la branche de l'hypothèse (Conventional Commits, sans signature : voir
      `AGENTS.md` §4). Pas de PDF, pas de `.env`, pas de clé.
