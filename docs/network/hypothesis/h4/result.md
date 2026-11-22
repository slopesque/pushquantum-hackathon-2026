# H4 · Dicke par ligne et mixer XY : résultats

> Chaque chiffre provient de `results/network/bench/h4/*.jsonl` (définitions dans
> [`metrics.md`](../../metrics.md)). Process suivi : [`process.md`](process.md).

- **Branche @ commit des runs :** `network/h4-dicke-xy` @ `1fcd48d`
- **Date :** 2026-11-22
- **Conclusion :** **Invalidée**. Le QAOA Dicke-XY satisfait bien les degrés sortants par construction
  (masse 1,00), mais sa part d'échantillons valides n'est que 1,5 fois celle du QAOA à pénalités sur
  network05 (critère : 10 fois). Selon la règle de décision, network06 et network12 n'ont pas été lancés.

## 1. Résumé

Sur network05 (20 qubits, p = 2, 201 circuits par run, seeds 0, 1, 2), le QAOA Dicke-XY donne une masse
valide médiane de 0,062 contre 0,042 pour le QAOA à pénalités du notebook, à circuits égaux. Les degrés
entrants, encore pénalisés, restent le goulot. `p_opt` n'est meilleur que sur 1 seed sur 3. Les deux
méthodes retrouvent l'optimum (65 500) après repair sur toutes les seeds, comme B0 et B1.

## 2. Résultats

network05, p = 2, MonteCarlo 20 × 10 itérations (201 circuits), 10 000 shots, λ = 1, top 100 réparés,
cloud Qoro (statevector, 20 qubits).

| Méthode | E1 `feasible_mass` (s0 / s1 / s2) | médiane E1 | `outdeg_mass` (méd.) | `p_opt` (s0 / s1 / s2) | `rank_best` | Q1 | n_circuits | max_qubits |
|---|---|---|---|---|---|---|---|---|
| h4_qaoa_dicke | 0,205 / 0,034 / 0,062 | **0,062** | **1,000** | 0,0028 / 0,0000 / 0,0002 | 1 / 2 / 1 | 65 500 (3/3) | 201 | 20 |
| h4_qaoa_penalty | 0,132 / 0,025 / 0,042 | 0,042 | 0,127 | 0,0009 / 0,0001 / 0,0004 | 1 / 1 / 1 | 65 500 (3/3) | 201 | 20 |

- Hasard : 216 topologies valides sur 2²⁰ ≈ 2·10⁻⁴. Les deux QAOA sont des centaines de fois au-dessus.
- Sensibilité λ = 3 (seed 0, local) : E1 = 0,107 (Dicke) contre 0,080 (pénalités), rapport 1,3. Le
  constat ne dépend pas de λ.
- Temps : environ 24 min par run sur le cloud (6 runs en parallèle, file d'attente), contre 4,5 min en
  local pour le même run. Crédits : quelques crédits au total (consommation mêlée à celle de H1 et H2 sur la
  période).

## 3. Critères de succès

| Critère | Valeur mesurée | Atteint ? |
|---|---|---|
| Faisabilité : médiane E1(Dicke) ≥ 10 × médiane E1(pénalités), network05 et network06 | 0,062 / 0,042 = 1,5 × (network05) | ❌ |
| `p_opt`(Dicke) > `p_opt`(pénalités) sur network05, 3 seeds sur 3 | 1 seed sur 3 (seed 0) | ❌ |
| Passage à l'échelle : médiane Q1(`h4_rows_q`) < médiane Q1(`h4_rows_sa`) sur network12 | non lancé (décision n° 1) | ⏳ non testé |

## 4. Solution rendue

Aucune : sur network05, toutes les méthodes trouvent l'optimum, déjà rendu par H0.

## 5. Analyse et suite

- La contrainte de degré sortant est bien imposée par construction (masse 1,00 contre 0,13). Mais sur
  network05, le QAOA à pénalités est déjà très au-dessus du hasard, car la pénalité domine le BQM
  normalisé. Le gain exponentiel prédit par Onah 2025 n'apparaît pas à cette taille.
- La faisabilité complète dépend surtout des **degrés entrants**, encore traités par pénalité. La suite
  logique serait un mixer qui préserve aussi les degrés entrants (échanges de colonnes, ou Grover local,
  Choi 2026), ou de passer aux permutations (deux permutations disjointes) : c'est l'objet de H5.
- Leçon d'exécution : pour ces QAOA à 20 qubits, le cloud a été 5 fois plus lent que le local. Il ne sert
  à décharger le CPU que si le local est saturé.
