# H2 · Substitut analytique enrichi (chemins à 2 sauts) : résultats

> Chaque chiffre provient de `results/network/bench/{h0,h1,h2}/*.jsonl` (définitions dans
> [`metrics.md`](../../metrics.md)). Process suivi : [`process.md`](process.md).

- **Branche @ commit des runs :** `network/h2-physics-surrogate` @ `e718c4f` (suffixe `-dirty` : seuls les
  JSONL de résultats étaient modifiés pendant les runs)
- **Date :** 2026-11-22
- **Conclusion :** **Validée**. Ajouter les chemins à 2 sauts au substitut du kit (β₂ = 1, λ = 1,3) bat B1
  sur network12 et network24 à budget LP égal. Combiné à H1 (option H1 + H2, `h2_fm_phys`), il donne les
  meilleurs résultats du projet : **279 667 (+1,15 %) sur network12 et 722 459 (+8,86 %) sur network24**.

## 1. Résumé

Le substitut H2 récompense les arcs directs (`t_ij x_ij`) et les chemins à 2 sauts (`t_ik x_ij x_jk`). Il
ordonne mieux les topologies que le kit (F1 = 0,433 contre 0,313) et, avec SA, bat B1 de près de 4 points
de gap sur network12 et de près de 2 points sur network24. Utilisé comme a priori dans la boucle FM de H1,
il améliore aussi H1 : médiane 282 556 contre 284 313 sur network12, 733 638 contre 737 450 sur network24.

## 2. Résultats

Budgets : network12 = 5 000 LP ; network24 = 10 000 LP avec `--time-limit 5400` (le budget LP est la seule
limite, voir `process.md`). Seeds 0, 1, 2. `h2_sa_phys` : α = 1, β₂ = 1, γ = 0, λ = 1,3, SA 100 lectures.
`h2_fm_phys` : boucle H1 (rang 8, cible rang, lr 0,003, l2 1e-2, poids de l'a priori β = 0,5, λ = 1) avec
l'objectif H2 (β₂ = 1) comme a priori.

| Instance | Méthode | min (gap) | médiane (gap) | max | lp_calls | wall_time_s | max_qubits | backend |
|---|---|---|---|---|---|---|---|---|
| network12 | b0_random | 316 858 (+14,61 %) | 317 215 (+14,74 %) | 320 480 | 5 000 | 76 | 0 | none |
| network12 | b1_sa_kit | 298 858 (+8,10 %) | 302 316 (+9,35 %) | 304 556 | 5 000 | 100 | 0 | none |
| network12 | h1_sa_fm | 283 900 (+2,69 %) | 284 313 (+2,84 %) | 285 625 | 5 000 | 250 | 0 | none |
| network12 | **h2_sa_phys** | 290 750 (+5,16 %) | **291 800 (+5,54 %)** | 295 273 | 5 000 | 132 | 0 | none |
| network12 | **h2_fm_phys** (H1 + H2) | **279 667 (+1,15 %)** | **282 556 (+2,20 %)** | 282 625 | 5 000 | 112 | 0 | none |
| network24 | b0_random | 781 448 (+17,74 %) | 788 125 (+18,75 %) | 793 534 | 10 000 | 1 369 | 0 | none |
| network24 | b1_sa_kit | 735 228 (+10,78 %) | 744 980 (+12,25 %) | 749 821 | 10 000 | 1 486 | 0 | none |
| network24 | h1_sa_fm | 731 261 (+10,18 %) | 737 450 (+11,11 %) | 740 667 | 10 000 | 1 958 | 0 | none |
| network24 | **h2_sa_phys** | 732 674 (+10,39 %) | **733 286 (+10,49 %)** | 739 182 | 10 000 | 1 590 | 0 | none |
| network24 | **h2_fm_phys** (H1 + H2) | **722 459 (+8,86 %)** | 733 638 (+10,54 %) | 737 685 | 10 000 | 1 940 | 0 | none |

Par seed (0 / 1 / 2) : network12 h2_sa_phys = 295 273 / 290 750 / 291 800 ; h2_fm_phys = 282 625 /
282 556 / 279 667. network24 h2_sa_phys = 732 674 / 739 182 / 733 286 ; h2_fm_phys = 722 459 / 737 685 /
733 638.

Métriques spécifiques :
- **F1, F2 (jeu de test network12) et F3 (network05)**, `python -m h2.tune --grid` :

  | Substitut | F1 ρ | F2 top-10 % | F3 percentile de l'optimum (network05) |
  |---|---|---|---|
  | Kit (β₂ = 0) | 0,313 | 0,20 | 0 % (1 ex aequo) |
  | β₂ = 0,25 | 0,366 | 0,22 | 0 % |
  | β₂ = 0,5 | 0,403 | 0,28 | 2,3 % |
  | **β₂ = 1 (retenu)** | **0,433** | **0,37** | 10,2 % |
  | β₂ = 2 | 0,382 | 0,33 | 30,6 % |

  Le terme γ (équilibrage) n'améliore F1 qu'avec β₂ = 0,5 (0,424) et le dégrade fortement à γ = 2.
- **E1 et λ** (network12, seed 0, β₂ = 1) : λ = 1 → E1 = 0,000, Q1 = 293 500 ; λ = 1,15 → 0,091, 294 800 ;
  **λ = 1,3 → 0,322, 295 273** ; λ = 2 → 0,894, 299 858. La règle d'Ayodele (MOC) vaut 1 sur nos objectifs
  normalisés ; la borne de Broesamle (32 à 400) est bien trop grande. Le λ recommandé par la
  Characterization Service sur network05 est **1,31**. Log : `results/network/bench/h2/tuning_network12_seed0.log`.
- `h2_fm_phys` : F1 de l'objectif final (FM + a priori H2) = 0,354 / 0,380 / 0,381 (kit 0,313) ; E1
  médiane 0,539.
- **Characterization Service** : network05 en 91 s, **10,02 crédits**, λ recommandé 1,31 ; network08 en
  10 s, **25,0 crédits**, pas de λ recommandé (λ sûr 51,6). Plus chère que prévu.
- Trajectoire `h2_fm_phys` sur network24 (meilleur à 5 000 / 7 900 / 10 000 LP) : seed 0 = 749 508 /
  722 459 / 722 459 ; seed 1 = 741 273 / 737 852 / 737 685 ; seed 2 = 744 000 / 738 488 / 733 638.

## 3. Critères de succès

| Critère | Valeur mesurée | Atteint ? |
|---|---|---|
| F1(H2) ≥ F1(kit) + 0,1 | 0,433 contre 0,313 (+0,12) | ✅ |
| F3(H2) meilleur que F3(kit) sur network05 | 10,2 % contre 0 % : le kit place déjà l'optimum en tête | ❌ |
| **Principal** : médiane Q1(h2_sa_phys) < médiane Q1(B1) sur network12, ≥ 2 seeds sur 3 | 291 800 < 302 316 ; 3/3 | ✅ |
| λ réglé : E1 ≥ E1 à λ = 1 sans dégrader Q1 | E1 0,32 contre 0,00 ; Q1 295 273 contre 293 500 (+0,6 %, une seed) | ⚠️ partiel |
| **Option H1 + H2** sur network12 : médiane Q1(h2_fm_phys) < médiane Q1(h1_sa_fm) | 282 556 < 284 313 ; 3/3 | ✅ |
| Option H1 + H2 sur network24 | 733 638 < 737 450 ; 2/3 (722 459 et 733 638) | ✅ |
| Consolidation network24 : h2_sa_phys contre B1 | 733 286 < 744 980 ; 3/3 | ✅ |

Remarque : sur network24, h2_sa_phys (733 286) et h2_fm_phys (733 638) ont des médianes quasi égales ; la
FM n'apporte un gain net que sur network12 et sur la meilleure seed de network24.

## 4. Solution rendue

| Instance | Score | Gap | Qubits max | `.sol` | Méthode et seed |
|---|---|---|---|---|---|
| **network24** | **722 459** | **+8,86 %** | 0 | `results/network/20261122T020927Z_network24.sol` | h2_fm_phys, seed 0 |
| network12 | 279 667 | +1,15 % | 0 | `results/network/20261122T020928Z_network12.sol` | h2_fm_phys, seed 2 |

Les deux fichiers sont validés par `qt.check_network_solution` (score égal à Q1) avant `save_run`.
Reproduction :

```bash
export PYTHONPATH=src/network-experiments OMP_NUM_THREADS=1
uv run python -m h2.run --instance network24 --seed 0 --method h2_fm_phys --beta2 1 --lam 1 --rank 8 \
  --beta 0.5 --lr 0.003 --l2 1e-2 --time-limit 5400
uv run python -m h2.run --instance network12 --seed 2 --method h2_fm_phys --beta2 1 --lam 1 --rank 8 \
  --beta 0.5 --lr 0.003 --l2 1e-2 --time-limit 1800
```

## 5. Analyse et suite

- **La physique du routage paie.** Récompenser les chemins à 2 sauts rapproche le substitut du vrai score
  (F1 +0,12) et donne un gain net à budget égal, sans apprentissage. C'est la meilleure méthode « simple ».
- **H1 + H2 se complètent sur network12** (+2,20 % de médiane, record du projet à +1,15 %). Sur network24,
  le gain de la FM au-delà de H2 est faible en médiane, mais la meilleure seed (722 459) est le meilleur
  `.sol` network24 du projet.
- **λ** : avec les termes à 2 sauts, λ = 1 ne suffit plus (aucune lecture valide) ; le λ de la
  Characterization (1,31) est un bon choix, mais le repair compense largement un λ trop faible.
- **F3** n'est pas un bon critère sur network05 : le kit y classe déjà l'optimum premier.
- Suite : relancer `h1_pce_fm` sur network24 à 10 000 LP (annulé dans H1), et essayer le PCE à
  33 qubits sur le QUBO H2 (plus creux que celui de H1, donc plus rapide) pour l'argument d'échelle.
