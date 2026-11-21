# <ID> · <Titre> : résultats

> À copier dans `docs/network/hypothesis/<id>/result.md` **à la fin**. Chaque chiffre provient de
> `results/network/bench/<id>/*.jsonl` (définitions dans [`metrics.md`](../../metrics.md)).

- **Branche @ commit des runs :** `network/<id>-<slug>` @ `<hash>`
- **Date :** YYYY-MM-DD
- **Conclusion :** **Validée** / **Invalidée** / **Non concluante**. <Une phrase.>

## 1. Résumé

<3 lignes : ce qui a été testé, le chiffre principal, ce qu'on en retient.>

## 2. Résultats

Budget : `metrics.md` §2 <ou écart>. Seeds 0, 1, 2.

| Instance | Méthode | min (gap) | médiane (gap) | max | lp_calls | wall_time_s | max_qubits | backend |
|---|---|---|---|---|---|---|---|---|
| network12 | b0_random | | | | | | 0 | none |
| network12 | b1_sa_kit | | | | | | 0 | none |
| network12 | <méthode> | | | | | | | |
| network24 | … | | | | | | | |

Métriques spécifiques (E1, E5, E6, F1, F2…) : <tableau ou liste>.

## 3. Critères de succès

| Critère | Valeur mesurée | Atteint ? |
|---|---|---|
| <…> | <…> | ✅ / ❌ / ⏳ non testé |

## 4. Solution rendue

| Instance | Score | Gap | Qubits max | `.sol` | Méthode et seed |
|---|---|---|---|---|---|

## 5. Analyse et suite

<Interprétation, limites, prochaine étape ou hypothèse du backlog à lancer.>
