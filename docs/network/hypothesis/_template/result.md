# <ID> · <Titre de l'hypothèse> : résultats

> Modèle à copier dans `docs/network/hypothesis/<id>/result.md` **à la fin des expériences**. Chaque
> chiffre doit provenir d'une ligne JSONL de `results/network/bench/<id>/` (définitions dans
> [`metrics.md`](../../metrics.md)).

- **Hypothèse :** <id>. Process suivi : [`process.md`](process.md)
- **Branche / commit des runs :** `network/<id>-<slug>` @ `<hash>`
- **Date :** YYYY-MM-DD
- **Conclusion (`metrics.md` §5) :** **Validée** / **Invalidée** / **Non concluante** <une phrase>

## 1. Résumé

<3 à 5 lignes : ce qui a été testé, le résultat principal chiffré, ce qu'on en retient.>

## 2. Phase 1 : résultats en local

Backend `maestro_local`, circuits de 20 qubits au plus. Budget : standard (`metrics.md` §2) <sinon
préciser>.

| Instance | Méthode | best (gap) | median (gap) | worst | hit@0.01 | med. lp_calls_to_target | med. wall_time_s | max_qubits | n_circuits |
|---|---|---|---|---|---|---|---|---|---|
| <…> | <…> | <…> | <…> | <…> | <…/5> | <…> | <…> | <…> | <…> |

**Métriques spécifiques à l'hypothèse** (E\*, F\*, S5…) :

| Instance | Méthode | <métrique> | <métrique> |
|---|---|---|---|

**Attribution :**

| Instance | Ablation (A1) | A2 `delta_median_vs_ablation` | A3 p-value | A4 vs B2 (delta, p) |
|---|---|---|---|---|

## 3. Critères de succès

| Critère (`hypothesis.md`) | Résultat | Atteint ? |
|---|---|---|
| <…> | <valeur mesurée> | ✅ / ❌ / ⏳ reporté à la phase 2 |

## 4. Solutions rendables

| Instance | Score | Gap | Fichier `.sol` | `.json` | `check_network_solution` |
|---|---|---|---|---|---|

## 5. Analyse

<Interprétation, limites, surprises, et comparaison avec les résultats des papiers de référence.>

## 6. Reporté à la phase 2 (cloud)

| Run | Pourquoi (qubits, coût) | Commande | Crédits estimés |
|---|---|---|---|

## 7. Demandes de changement sur H0

<Bugs trouvés ou utilitaires communs à ajouter dans `src/network-experiments/h0/`, ou « aucune ».>

## 8. Suite proposée

<Prochaines expériences, nouvelles hypothèses.>

## Phase 2 : résultats cloud

<À compléter plus tard : mêmes tableaux qu'au §2, avec `backend = qoro_cloud` et les crédits (C4).>
