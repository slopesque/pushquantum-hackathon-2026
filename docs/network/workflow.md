# Workflow des agents « network » (profil hackathon)

> Process commun à tout agent qui travaille sur une hypothèse de [`hypothesis.md`](hypothesis.md). Le
> *quoi* est dans `hypothesis.md`, le *comment mesurer* dans [`metrics.md`](metrics.md). Ici : le *où*
> et le *comment*. Pour l'instant, seules **H0** (baseline) puis **H1** sont au programme.

## 1. Identifiant et emplacements

L'**id** d'une hypothèse est son nom en minuscules (`h0`, `h1`…).

| Élément | Convention | H0 | H1 |
|---|---|---|---|
| Branche | `network/<id>-<slug>` | `network/h0-baseline` | `network/h1-learned-surrogate` |
| Worktree | `../pushquantum-hackathon-2026-<id>` | `…-h0` | `…-h1` |
| Code | `src/network-experiments/<id>/` | `h0/` | `h1/` |
| Notebooks | `notebooks/network/<id>/` | | |
| Documentation | `docs/network/hypothesis/<id>/process.md` et `result.md` | | |
| Runs | `results/network/bench/<id>/<méthode>.jsonl` | | |
| Solutions rendables | `results/network/<timestamp>_networkNN.sol` et `.json`, via `save_run` | | |

## 2. Mise en place (worktree)

Branches de base :
- pour `h0`, la branche qui porte cette documentation ;
- pour `h1`, `network/h0-baseline`.

```bash
git worktree add ../pushquantum-hackathon-2026-<id> -b network/<id>-<slug> <branche-de-base>
cd ../pushquantum-hackathon-2026-<id>
uv sync
ln -s ../../pushquantum-hackathon-2026/references/qoblib_data references/qoblib_data  # cache QOBLIB (facultatif)
cp ../pushquantum-hackathon-2026/.env .                                               # seulement si cloud
```

## 3. Code

`src/network-experiments/` n'est pas un paquet installé : son nom contient un tiret, donc il n'est pas
importable directement. Chaque `<id>/` est un paquet (avec un `__init__.py`), qu'on importe en ajoutant
`src/network-experiments` au `PYTHONPATH`.

```bash
export PYTHONPATH=src/network-experiments
uv run python -m <id>.run --instance network12 --seed 0 --method <m>
uv run pytest src/network-experiments/<id>/tests
uv run ruff check src/network-experiments/<id> && uv run ruff format src/network-experiments/<id>
```

**Règles :**
- On importe l'arbitre avec `from hackathon.referee import qt`, et `gap` et `save_run` depuis
  `hackathon.utils`.
- H1 réutilise H0 (`from h0… import …`) sans le modifier. Si H0 a besoin d'un changement, on le note dans
  `result.md`.
- Les notebooks servent à explorer. La logique réutilisable va dans `src/network-experiments/<id>/`.

## 4. Ordre de travail et exécution

On suit l'ordre de `hypothesis.md` :

| Étape | Instance | Seeds |
|---|---|---|
| 1 · Vérification | `network05` | 0 |
| 2 · Réglage | `network12` | 0 |
| 3 · Évaluation | `network12` | 0, 1, 2 |
| 4 · Consolidation | `network24` (sinon `network20`, puis `network16` : `metrics.md` §5) | 0, 1, 2 |

**`network24` n'est lancé qu'à la consolidation.**

- **Local d'abord.** Maestro (`make_backend(use_cloud=False)`), et **aucun circuit de plus de 24 qubits en local**.
  Les parties classiques (LP, SA, apprentissage) n'ont pas d'autre limite que le budget (`metrics.md` §2).
- **Cloud seulement en consolidation**, et seulement si un circuit dépasse ce que le local permet (par
  exemple PCE à environ 33 qubits sur `network24`). Noter les crédits consommés.
- **Accélérer en local avec les 8 cœurs.** Lancer les 3 seeds dans 3 processus en parallèle. Le GPU local
  n'aide pas : le Maestro installé n'a pas de support GPU.

## 5. Livrables

| Quand | Livrable | Modèle |
|---|---|---|
| Au début | `docs/network/hypothesis/<id>/process.md` : objectif, implémentation, plan d'évaluation | [`hypothesis/_template/process.md`](hypothesis/_template/process.md) |
| Pendant | Code, runs JSONL, `.sol` via `save_run` | `metrics.md` §4 |
| À la fin | `docs/network/hypothesis/<id>/result.md`, et la ligne `Statut` dans `hypothesis.md` | [`hypothesis/_template/result.md`](hypothesis/_template/result.md) |

## 6. Checklist de fin

- [ ] Les tests passent et `ruff` est propre sur `src/network-experiments/<id>`.
- [ ] Chaque chiffre de `result.md` vient d'une ligne JSONL : même budget, seeds 0, 1 et 2.
- [ ] Chaque affirmation de gain quantique a son ablation (même méthode avec du SA à la place).
- [ ] Le `.sol` rendu est validé par `qt.check_network_solution` et enregistré par `save_run`.
- [ ] La ligne `Statut` est à jour dans `hypothesis.md`. Ne pas toucher au tableau d'état d'`AGENTS.md`,
      qui est mis à jour à la fusion.
- [ ] Le travail est commité sur la branche (Conventional Commits, sans signature). Pas de `.env`, pas de
      PDF.
