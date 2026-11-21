# <ID> · <Titre de l'hypothèse> : process

> Modèle à copier dans `docs/network/hypothesis/<id>/process.md` **avant de coder**. Remplacer tous les
> `<…>`. Voir [`../../workflow.md`](../../workflow.md) pour le process commun.

- **Hypothèse :** <id> (section correspondante de [`hypothesis.md`](../../hypothesis.md))
- **Branche / worktree :** `network/<id>-<slug>` / `../pushquantum-hackathon-2026-<id>`
- **Branche de base et commit :** `<branche>` @ `<hash>`
- **Phase :** 1 (local, ≤ 20 qubits par circuit)
- **Date de début :** YYYY-MM-DD

## 1. Objectif

<Reformuler l'hypothèse en une phrase testable : « À budget LP égal, <méthode> obtient une médiane de Q1
inférieure à <baseline> sur <instances> ».>

## 2. Références utilisées

| Papier (Auteur et al., année, DOI) | Ce qu'on en reprend |
|---|---|
| <…> | <algorithme, réglages, résultat attendu> |

## 3. Procédé d'implémentation

<Composants à écrire, avec leur fichier dans `src/network-experiments/<id>/`, ce que chacun réutilise de
H0 et de Divi, et les choix de conception.>

| Composant | Fichier | Rôle |
|---|---|---|
| <…> | `src/network-experiments/<id>/<…>.py` | <…> |

## 4. Plan d'évaluation

- **Instances (phase 1) :** <par ex. network05, network08, network12, network16>
- **Seeds :** 0 à 4
- **Budgets :** standard (`metrics.md` §2) <ou écart justifié>
- **Méthodes comparées :**

  | Nom (`method`) | Description | Rôle |
  |---|---|---|
  | <…> | <…> | méthode testée |
  | <…> | <…> | ablation classique (A1) |
  | B0 / B1 / B2 / B3 | baselines H0 | référence |

- **Métriques principales :** <ids de `metrics.md`, repris de la section de l'hypothèse>
- **Critères de succès :** <repris de `hypothesis.md`, en marquant ceux qui sont « reportés à la phase 2 »>
- **Taille maximale des circuits en phase 1 :** <qubits, profondeur estimée>
- **Commandes de reproduction :**

  ```bash
  export PYTHONPATH=src/network-experiments
  uv run python -m <id>.run_bench --instance <…> --seed <…> --method <…>
  ```

## 5. Préparation de la phase 2 (cloud)

<Runs prévus sur le cloud (instances, qubits, nombre de circuits estimé, crédits estimés) et commandes
prêtes à lancer.>

## 6. Écarts au plan

<À compléter pendant la session si le procédé change : date, écart, raison.>
