# H1 · Substitut QUBO appris (FMQA) : process

> Copié depuis le modèle [`../_template/process.md`](../_template/process.md) **avant de coder**. Process
> commun : [`../../workflow.md`](../../workflow.md).

- **Hypothèse :** h1 ([`hypothesis.md`](../../hypothesis.md))
- **Branche @ commit de base :** `network/h1-learned-surrogate` @ `3aa115a`
- **Date :** 2026-11-21

## 1. Objectif

À budget LP égal (5 000 LP, network12, seeds 0, 1, 2), `h1_sa_fm` obtient une médiane de Q1 inférieure à
B1, selon la règle de gain de `metrics.md` §1.

## 2. Implémentation

| Composant | Fichier (`src/network-experiments/h1/…`) | Rôle |
|---|---|---|
| Échantillonneurs | `samplers.py` | `SampleBatch` (échantillons et métadonnées), `sa_sampler` |
| Substitut appris | `fm.py` | Factorization machine en numpy (Adam), `make_target`, `to_bqm`, `learned_qubo` = objectif normalisé + λ·pénalité de degré du kit |
| Diagnostics | `diagnostics.py` | F1 (Spearman) et F2 (précision du top 10 %) sur le jeu de test figé |
| Boucle active | `loop.py` | `h1_fm` : N₀ = 20 % du budget en topologies aléatoires, puis des tours SA (100 lectures) → repair → LP sur les nouvelles topologies → réentraînement en warm start. Exploration aléatoire si moins de 5 nouvelles. Tours quantiques choisis par `quantum_rounds` |
| PCE | `pce.py` | Échantillonneur PCE Divi : `PolyEncoding`, `MonteCarloOptimizer`. Refuse plus de 24 qubits en local |
| CLI | `run.py` | Lance une méthode sur une instance et une liste de seeds |

Choix et paramètres principaux : réutilisation du scorer, du harnais et des baselines de H0 (sans les
modifier). Paramètres à régler sur network12 seed 0 : rang k ∈ {4, 8}, λ, cible (rang ou z-score), nombre
d'epochs. Calendrier quantique : PCE remplace SA sur un sous-ensemble de tours (`quantum_rounds`, par
exemple `every:k`). Le même calendrier avec SA partout, c'est-à-dire `h1_sa_fm`, sert d'ablation. Papiers
suivis : Kitai 2020 (FMQA), Sciorilli 2025 (PCE).

## 3. Évaluation

| Étape | Instance | Seeds | Méthodes lancées |
|---|---|---|---|
| Vérification | network05 | 0 | `h1_sa_fm` |
| Réglage | network12 | 0 | `h1_sa_fm` (k, λ, cible, epochs) |
| Évaluation | network12 | 0, 1, 2 | `h1_sa_fm` + baselines B0, B1 (H0), puis `h1_pce_fm` (Maestro local, environ 16 qubits) comme ablation |
| Consolidation | network24 (sinon network20, puis network16) | 0, 1, 2 | `h1_sa_fm` + baselines B0, B1 en local ; `h1_pce_fm` sur le cloud Qoro (environ 33 qubits, `PolyEncoding`), crédits notés |

- **Budgets :** `metrics.md` §2.
- **Critères de succès :** (network12, seeds 0, 1, 2, à budget égal)
  - **Principal**, le substitut appris aide : médiane de Q1(`h1_sa_fm`) < médiane de Q1(B1), **et** au
    moins 2 seeds sur 3 sous la médiane de B1.
  - L'apprentissage compte : médiane de Q1(`h1_sa_fm`) < médiane de Q1(B0).
  - Le substitut appris ordonne mieux les topologies : F1(appris) > F1(kit) sur le jeu de test.
  - Bonus quantique : médiane de E5(`h1_pce_fm`) < médiane de E5(`h1_sa_fm`), avec la même règle des
    2 seeds sur 3. Sans recherche locale, E5 = Q1.
- **Décisions :**
  1. Après l'évaluation sur network12 : si `h1_sa_fm` ne bat pas B1, pas de consolidation classique et H1
     est invalidée.
  2. Après l'ablation PCE sur network12 : retenir ou non `h1_pce_fm`.
  3. Après un test cloud unique sur network24 (latence, crédits) : lancer ou non les 3 seeds.

  Le PCE sur network24 est fait même si la décision n° 1 est négative, comme argument d'échelle
  uniquement.
- **Commande :** `PYTHONPATH=src/network-experiments uv run python -m h1.run --instance network12 --seed 0 1 2 --method h1_sa_fm`

## 4. Écarts au plan

- **2026-11-21 · Graine des tours SA.** Graine du tour = seed·1 000 003 + r, comme les lots de B1 dans H0.
  Sinon les seeds 0, 1 et 2 partagent leurs tours.
