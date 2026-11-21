# <ID> · <Titre> : process

> À copier dans `docs/network/hypothesis/<id>/process.md` **avant de coder**. Process commun :
> [`../../workflow.md`](../../workflow.md).

- **Hypothèse :** <id> ([`hypothesis.md`](../../hypothesis.md))
- **Branche @ commit de base :** `network/<id>-<slug>` @ `<hash>`
- **Date :** YYYY-MM-DD

## 1. Objectif

<Une phrase testable, par ex. « À budget LP égal, `h1_sa_fm` obtient une médiane de Q1 inférieure à B1 sur
network12 (seeds 0, 1, 2) ».>

## 2. Implémentation

| Composant | Fichier (`src/network-experiments/<id>/…`) | Rôle |
|---|---|---|
| <…> | <…> | <…> |

Choix et paramètres principaux : <…>. Papiers suivis : <…>.

## 3. Évaluation

| Étape | Instance | Seeds | Méthodes lancées |
|---|---|---|---|
| Vérification | network05 | 0 | <…> |
| Réglage | network12 | 0 | <…> |
| Évaluation | network12 | 0, 1, 2 | <…> + baselines |
| Consolidation | network24 (sinon network20, puis network16) | 0, 1, 2 | <…> + baselines |

- **Budgets :** `metrics.md` §2.
- **Critères de succès :** <repris de `hypothesis.md`>.
- **Commande :** `PYTHONPATH=src/network-experiments uv run python -m <id>.run --instance … --seed … --method …`

## 4. Écarts au plan

<Date, écart, raison.>
