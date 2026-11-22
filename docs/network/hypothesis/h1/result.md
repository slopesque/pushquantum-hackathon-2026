# H1 · Substitut QUBO appris (FMQA) : résultats

> Chaque chiffre provient de `results/network/bench/{h0,h1}/*.jsonl` (définitions dans
> [`metrics.md`](../../metrics.md)). Process suivi : [`process.md`](process.md).

- **Branche @ commit des runs :** `network/h1-learned-surrogate`. Le code des runs est celui de `606c589`
  (le hash `5d242b6` des JSONL est le même commit avant le rebase sur H0 ; le suffixe `-dirty` ne vient
  que de `process.md`, modifié pendant les runs).
- **Date :** 2026-11-21
- **Conclusion :** **Validée** sur network12 (critère principal) **et sur network24 à budget LP égal**
  (10 000 LP, finition du 2026-11-22) : médiane 737 450 (+11,11 %) contre 744 980 (+12,25 %) pour B1, 3 seeds
  sur 3 sous B1. Sous le plafond de 30 min, en revanche, H1 n'atteignait que ≈ 7 900 LP et ne battait pas B1.

## 1. Résumé

Une factorization machine (rang 8), apprise en ligne sur les scores LP et ajoutée à l'objectif du kit
(β = 0,5), sert de QUBO à SA dans une boucle active. **Sur network12, à 5 000 LP, `h1_sa_fm` a une médiane
de 284 313 (+2,84 %), contre 302 316 (+9,35 %) pour B1** : 3 seeds sur 3 sous la médiane de B1. Le PCE
dans la boucle n'apporte rien sur network12. Sur network24, le meilleur `.sol` (731 660, +10,24 %) vient
d'un run `h1_pce_fm` à 33 qubits sur le cloud Qoro, mais les médianes ne départagent pas les méthodes.

## 2. Résultats

Budgets `metrics.md` §2 : network12 = 5 000 LP / 10 min ; network24 = 10 000 LP / 30 min. Seeds 0, 1, 2.
Paramètres H1 : rang 8, cible `rank`, lr 0,003, l2 1e-2, β = 0,5, λ = 1, N₀ = 20 % du budget, SA 100
lectures par tour, 50 epochs par tour. `h1_pce_fm` : PCE `PolyEncoding`, 2 couches, MonteCarlo 20 × 5
itérations, top 100 par énergie, un tour sur 5 (network12) ou sur 10 (network24).

| Instance | Méthode | min (gap) | médiane (gap) | max | lp_calls | wall_time_s | max_qubits | backend |
|---|---|---|---|---|---|---|---|---|
| network12 | b0_random | 316 858 (+14,61 %) | 317 215 (+14,74 %) | 320 480 | 5 000 | 76 | 0 | none |
| network12 | b1_sa_kit | 298 858 (+8,10 %) | 302 316 (+9,35 %) | 304 556 | 5 000 | 100 | 0 | none |
| network12 | b1_sa_kit_p2 (ablation β) | 308 834 (+11,70 %) | 310 750 (+12,40 %) | 312 723 | 5 000 | 165 | 0 | none |
| network12 | **h1_sa_fm** | **283 900 (+2,69 %)** | **284 313 (+2,84 %)** | 285 625 | 5 000 | 250 | 0 | none |
| network12 | h1_pce_fm | 289 000 (+4,53 %) | 289 400 (+4,68 %) | 291 800 | 5 000 | 268 | 16 | maestro_local |
| network24 | b0_random | 781 448 (+17,74 %) | 788 125 (+18,75 %) | 793 534 | 10 000 | 1 369 | 0 | none |
| network24 | b1_sa_kit | 735 228 (+10,78 %) | 744 980 (+12,25 %) | 749 821 | 10 000 | 1 486 | 0 | none |
| network24 | h1_sa_fm (plafond 30 min) | 741 450 (+11,72 %) | 749 667 (+12,95 %) | 750 364 | 7 916 | 1 800 | 0 | none |
| network24 | **h1_sa_fm (10 000 LP)** | **731 261 (+10,18 %)** | **737 450 (+11,11 %)** | 740 667 | 10 000 | 1 958 | 0 | none |
| network24 | h1_pce_fm | **731 660 (+10,24 %)** | 747 595 (+12,64 %) | 756 726 | 5 000 | 1 930 | **33** | qoro_cloud |

Par seed (0 / 1 / 2) :
- network12 : h1_sa_fm = 285 625 / 283 900 / 284 313 ; h1_pce_fm = 291 800 / 289 000 / 289 400.
- network24 : B1 = 735 228 / 744 980 / 749 821 ; h1_sa_fm = 750 364 / 749 667 / 741 450 ;
  h1_pce_fm = 756 726 / 731 660 / 747 595.

Métriques spécifiques :

| Instance | Méthode | E1 `feasible_mass` (médiane) | F1 ρ (kit → appris) | F2 top-10 % (kit → appris) | n_circuits par run |
|---|---|---|---|---|---|
| network12 | h1_sa_fm | 0,967 | 0,313 → 0,321 (0,305 à 0,347) | 0,20 → 0,31 (0,29 à 0,36) | 0 |
| network12 | h1_pce_fm | 0,760 | 0,313 → 0,352 | 0,20 → 0,29 | 909 à 1 010 |
| network24 | h1_pce_fm | 0,741 | — (pas de jeu de test) | — | 404 (4 tours PCE) |

- E1 de `h1_pce_fm` mélange les tours SA et les tours PCE : les échantillons PCE ne sont **jamais** valides
  avant repair (E1 = 0 sur les tours PCE, voir la sonde cloud).
- F1 et F2 sont mesurés à la fin du run sur le jeu de test figé de network12 (H0), pénalités exclues.
- Pas de recherche locale : E5 = Q1, E6 non applicable.
- **Crédits cloud :** 1,34 crédit au total (solde 1 000 → 998,66), dont 0,08 pour les deux sondes
  (`results/network/bench/h1/cloud_probe.jsonl` : 101 circuits à 33 qubits = 47 s et 0,06 crédit).
- **Réglage** (network12, seed 0, 12 configurations) : `results/network/bench/h1/tuning_network12_seed0.log`.
  FM seule (β = 0) : 294 667 ; β = 0,25 / 0,5 / 1 / 2 : 283 400 / 285 625 / 287 067 / 287 308 ; λ = 2 :
  304 400 ; cible z-score : 298 143.

### Finition network24 à 10 000 LP (2026-11-22)

Relance de `h1_sa_fm` avec `--time-limit 5400` et `OMP_NUM_THREADS=1`, pour que le budget LP (10 000) soit
la seule limite, comme pour B1. Les 3 runs atteignent 10 000 LP en ≈ 33 min. Trajectoires (meilleur
score à 5 000 / 7 900 / 10 000 LP) : seed 0 = 766 277 / 750 364 / 731 261 ; seed 1 = 766 000 / 749 667 /
740 667 ; seed 2 = 763 567 / 741 450 / 737 450. Les valeurs à 7 900 LP sont **identiques** à celles des runs
plafonnés à 30 min : `h1_sa_fm` est déterministe à seed donnée, quelle que soit la charge machine.

La relance de `h1_pce_fm` à 10 000 LP a été **annulée** après 63 min (règle des +10 min sur la durée
prévue) : la file d'attente du cloud, partagée avec H4, l'a ralentie. Elle reste à refaire ; le tableau
garde donc `h1_pce_fm` à 5 000 LP.

### Consolidation network24 : runs écartés

Le premier lot de runs network24 (12 processus en parallèle, 18 threads BLAS chacun, charge ≈ 18 sur
8 cœurs) a été faussé par la contention : B1 et H1 ont buté sur le plafond de 30 min à 8 700 LP (B1) et
4 000 à 5 400 LP (H1). Ces lignes restent dans les JSONL (même seed, écrites avant). Le tableau ne retient
que le second lot, relancé avec `OMP_NUM_THREADS=1` (9 processus). B0, qui avait atteint 10 000 LP, n'a
pas été relancé. Même dans le second lot, H1 bute sur le plafond de temps.

## 3. Critères de succès

| Critère (network12, seeds 0, 1, 2) | Valeur mesurée | Atteint ? |
|---|---|---|
| **Principal** : médiane Q1(h1_sa_fm) < médiane Q1(B1), et ≥ 2 seeds sur 3 sous la médiane de B1 | 284 313 < 302 316 ; 3/3 seeds sous 302 316 | ✅ |
| L'apprentissage compte : médiane Q1(h1_sa_fm) < médiane Q1(B0) | 284 313 < 317 215 | ✅ |
| F1(appris) > F1(kit) sur le jeu de test | 0,321 > 0,313 (médiane), dans le bruit (± 0,045) ; F2 nettement meilleur (0,31 contre 0,20) | ✅ (faible) |
| Bonus quantique : médiane E5(h1_pce_fm) < médiane E5(h1_sa_fm), même règle | 289 400 > 284 313 | ❌ |
| *Ablation de β* : le gain ne vient pas du seul a priori du kit | b1_sa_kit_p2 = 310 750, pire que B1 | ✅ |

Sur network24 à 10 000 LP : **h1_sa_fm (médiane 737 450) bat B1 (744 980)**, 3 seeds sur 3 sous la médiane
de B1 (règle de gain ✅). Sous le plafond de 30 min (≈ 7 900 LP), il ne le battait pas (749 667). h1_pce_fm a une médiane (747 595) inférieure à h1_sa_fm, avec 2 seeds sur 3 sous sa médiane,
mais avec moins de LP (5 000 contre 7 900) et sans battre B1 : signal non concluant.

## 4. Solution rendue

| Instance | Score | Gap | Qubits max | `.sol` | Méthode et seed |
|---|---|---|---|---|---|
| **network24** | **731 261** | **+10,18 %** | 0 | `results/network/20261122T015004Z_network24.sol` | h1_sa_fm, seed 0, 10 000 LP (`--time-limit 5400`) |
| network24 (quantique) | 731 660 | +10,24 % | **33** | `results/network/20261121T232032Z_network24.sol` | h1_pce_fm, seed 1 : boucle FM (β = 0,5) + PCE cloud Qoro (PolyEncoding, MPS χ = 32), `every:10`, 5 000 LP |
| network12 | 283 900 | +2,69 % | 0 | `results/network/20261121T232033Z_network12.sol` | h1_sa_fm, seed 1 |

Les deux fichiers sont validés par `qt.check_network_solution` (score égal à Q1) avant `save_run`.
Reproduction :

```bash
export PYTHONPATH=src/network-experiments OMP_NUM_THREADS=1
uv run python -m h1.run --instance network12 --seed 1 --method h1_sa_fm --lr 0.003 --l2 1e-2 --rank 8 --beta 0.5
uv run python -m h1.run --instance network24 --seed 1 --method h1_pce_fm --lr 0.003 --l2 1e-2 --rank 8 --beta 0.5 \
  --cloud --quantum-rounds every:10 --pce-population 20 --pce-iterations 5 --pce-mps-bond-dim 32 --pce-max-retries 400
```

Le run network24 dépend du plafond de temps (30 min) et donc de la charge machine : le nombre de LP
atteint, et donc le score, peuvent varier.

## 5. Analyse et suite

- **Le substitut appris aide nettement sur network12** : −6,5 points de gap par rapport à B1. L'a priori du
  kit (β) compte : la FM seule fait +6,6 % (seed 0), contre +3,3 % avec β = 0,5. Mais l'a priori seul
  (b1_sa_kit_p2) fait pire que B1 : c'est la combinaison qui marche.
- **Sur network24, le coût par LP limite H1 dans le temps, pas en qualité** : à 10 000 LP, H1 bat B1. Le QUBO appris est dense (152 000 couplages, contre
  ≈ 12 000 pour le kit) : un tour SA prend environ 4 s, et le réentraînement grandit avec les données. Sous
  le plafond de 30 min, H1 n'utilise que 7 900 LP sur 10 000. Pistes : moins de lectures SA par tour, FM
  creuse ou de rang 4, plafond de temps relevé, ou réentraînement moins fréquent.
- **Le PCE n'est pas un bon échantillonneur ici** : aucun échantillon valide avant repair, et sur network12
  il fait moins bien que SA à calendrier égal. C'est le repair qui transforme ses sorties en topologies.
  Son seul apport est l'échelle : 33 qubits sur network24 (MPS cloud), pour un coût négligeable
  (≈ 0,0006 crédit par circuit).
- **Limite à signaler à H0** : `h0.report` plante sur les lignes sans `lp_calls` (`cloud_probe`) ; il faut
  passer `--methods`. Non corrigé (H1 ne modifie pas H0).
- Suite proposée : rendre la boucle H1 moins chère sur network24 (voir plus haut), puis H2 (substitut
  analytique enrichi) ou H7 (recherche locale quantique sur les 2-exchanges) pour réduire l'écart au PT.
