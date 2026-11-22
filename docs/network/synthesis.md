# Synthèse : network design (QOBLIB 08)

> Support de la partie network de la présentation (2 min). Tous les chiffres viennent des `result.md` de
> [H0](hypothesis/h0/result.md), [H1](hypothesis/h1/result.md), [H2](hypothesis/h2/result.md) et
> [H4](hypothesis/h4/result.md). Gap = (score − meilleur connu) / meilleur connu ; plus bas = mieux.

## 0. En bref (pitch de 2 min)

- **Problème.** Choisir les liens d'un réseau de n nœuds (2 sortants, 2 entrants par nœud), puis router
  toute la demande. Score : la charge du lien le plus chargé. Cible : `network24`, 552 variables binaires.
- **Constat.** Le QUBO du kit ne voit que les liens directs. Il ignore le routage sur plusieurs sauts, alors
  que le vrai score se calcule exactement par un LP en quelques millisecondes.
- **Idée clé.** Rapprocher le QUBO du vrai score : ajouter la physique du routage (chemins à 2 sauts, H2)
  et l'apprendre en ligne à partir du LP (factorization machine, H1).
- **Résultat.** À budget LP égal, la combinaison H1 + H2 bat le pipeline du kit (B1). Meilleurs runs :
  **network12 à +1,15 %** du meilleur connu (B1 : +8,10 %), **network24 à +8,86 %** (B1 : +10,78 %).
- **Quantique.** PCE dans la boucle : **33 qubits sur le cloud Qoro** pour network24 (731 660, +10,24 %),
  pour 1,34 crédit. Pas de gain prouvé face à SA : c'est le repair qui fait le travail.
- **QAOA contraint (Dicke + XY).** Les degrés sortants sont respectés par construction, mais la part
  d'échantillons valides ne gagne qu'un facteur 1,5 (objectif : 10).

## 1. Le problème

QOBLIB 08 reprend un problème de Bienstock et al. (1995). On a n nœuds et une matrice de demande `t_ij`.

1. **Topologie.** On choisit un graphe orienté où chaque nœud a exactement 2 arcs sortants et 2 entrants.
   Une variable binaire `x_ij` par arc possible, soit n(n−1) variables : 20 (`network05`) à 552 (`network24`).
2. **Routage.** On route toute la demande (flots fractionnaires) sur les arcs choisis, en minimisant la
   charge maximale d'un arc. Le score officiel est cette charge, en unités de 1/1000.

Les deux étapes sont séparées :

| | Topologie | Routage |
|---|---|---|
| Nature | Combinatoire, se met en QUBO | LP exact |
| Coût | Le vrai problème difficile | ≈ 6 ms (network12), 30 à 65 ms (network24) |
| Rôle | Ce qu'on optimise | L'arbitre : il donne le score |

Le QUBO du kit (`qt.build_network_qubo`) n'est qu'un **substitut** : `−Σ t_ij x_ij` plus des pénalités de
degré. Il récompense une demande servie en direct, mais ignore qu'une demande peut passer par 2 sauts ou
plus. Toute la suite consiste à rendre ce substitut plus fidèle au vrai score.

## 2. Comment on mesure

- **Qualité :** gap au meilleur connu QOBLIB. network12 : **276 474** ; network24 : **663 688**. Ces records
  viennent d'un parallel tempering classique (Gupta, soumission QOBLIB) qu'on ne relance pas.
- **Budget :** nombre de résolutions LP, indépendant de la machine. **5 000 sur network12, 10 000 sur
  network24.** Il compte tout : données d'entraînement, candidats de la boucle, recherche locale.
- **Seeds :** 0, 1 et 2. On compare les **médianes** ; on rend le meilleur `.sol`.
- **Règle de gain :** A bat B si la médiane de A est plus basse **et** si 2 seeds de A sur 3 sont sous la
  médiane de B. Pas de test statistique : 3 seeds ne le permettent pas.

Deux baselines (H0) :

| Baseline | Méthode | network12 médiane | network24 médiane |
|---|---|---|---|
| B0 `b0_random` | Topologies aléatoires notées par le LP | 317 215 (+14,74 %) | 788 125 (+18,75 %) |
| **B1 `b1_sa_kit`** | SA sur le QUBO du kit, repair, LP (pipeline du notebook) | **302 316 (+9,35 %)** | **744 980 (+12,25 %)** |

**B1 est la barre à battre.** Avec le budget complet, B1 fait mieux que le repère à 100 lectures (+12,0 %
sur network12). Ses lectures SA sont presque toutes valides (E1 ≈ 0,999) : le repair y sert peu.

## 3. État de l'art (en bref)

- **Records actuels :** parallel tempering classique avec le LP comme énergie et des échanges de 2 ou
  3 arcs qui préservent les degrés (Gupta, QOBLIB). Aucun papier ne traite cette instance en quantique.
- **Substituts appris :** apprendre un QUBO qui imite une boîte noire coûteuse, puis l'optimiser en boucle
  (FMQA, Kitai 2020 ; BOX-QUBO, Nüßlein 2023).
- **Substituts physiques et pénalités :** le choix de λ est difficile (Alessandroni 2025) ; règles
  statiques (Ayodele 2022) et bornes (Broesamle 2026).
- **QAOA contraint :** état de Dicke et mixer XY qui restent dans l'espace valide ; le QAOA générique a une
  faisabilité exponentiellement faible sur ces problèmes (Onah 2025).
- **PCE :** beaucoup de variables sur peu de qubits (Sciorilli 2025).

## 4. Nos hypothèses et leur résultat

**H0 · Baselines (validée).** On a mesuré B0 et B1 au budget standard, et figé un jeu de test de
1 000 topologies sur network12. B1 bat nettement B0 : le substitut du kit oriente bien la recherche. Mais
presque chaque lecture SA donne une topologie nouvelle : c'est le budget LP qui limite, pas le SA.

**H1 · Substitut appris (validée).** Idée : apprendre en ligne, à partir des scores LP, un QUBO plus fidèle
que celui du kit. Une factorization machine (rang 8) est ajoutée à l'objectif du kit (β = 0,5), puis SA
l'échantillonne dans une boucle active. Sur network12, `h1_sa_fm` a une médiane de **284 313 (+2,84 %)**
contre 302 316 pour B1, 3 seeds sur 3. Sur network24 à 10 000 LP, **737 450 (+11,11 %)** contre 744 980.
L'a priori du kit et l'apprentissage se complètent : l'a priori seul fait pire que B1 (+12,40 %). Limite :
le QUBO appris est dense (152 000 couplages) ; sous un plafond de 30 min, H1 n'atteint que ≈ 7 900 LP sur
network24 et ne bat pas B1.

*Partie quantique de H1.* On remplace SA par PCE (`PolyEncoding`) dans un tour sur 5 ou sur 10.
- network12, local, **16 qubits** : médiane 289 400 (+4,68 %), moins bien que SA (284 313).
- network24, cloud Qoro, **33 qubits** en MPS : meilleur run 731 660 (+10,24 %), médiane 747 595 (+12,64 %),
  à 5 000 LP seulement. Coût : 1,34 crédit au total.
- Aucun échantillon PCE n'est valide avant repair : le repair transforme ses sorties en topologies. Pas de
  gain prouvé face à SA. L'apport est l'échelle, pas la qualité.

**H2 · Substitut physique (validée).** Idée : sans apprentissage, récompenser aussi les chemins à 2 sauts
(`t_ik x_ij x_jk`), car une demande servie en 2 sauts charge 2 arcs. Le substitut ordonne mieux les
topologies que le kit (corrélation de rang 0,433 contre 0,313). Avec SA (`h2_sa_phys`, λ = 1,3), médiane
**291 800 (+5,54 %)** sur network12 et **733 286 (+10,49 %)** sur network24, 3 seeds sur 3 sous B1. Le λ
recommandé par la Characterization Service sur network05 vaut 1,31, proche de notre réglage, mais le
service a coûté 10,02 crédits (network05) et 25,0 crédits (network08).

**Option H1 + H2 (validée).** On utilise le substitut H2 comme a priori dans la boucle H1 (`h2_fm_phys`).
Sur network12 : médiane **282 556 (+2,20 %)**, meilleur run **279 667 (+1,15 %)**. Sur network24 :
médiane 733 638 (+10,54 %), quasi égale à H2 seul, mais meilleur run **722 459 (+8,86 %)** : nos deux
meilleurs `.sol`.

**H4 · QAOA faisable par construction (invalidée).** Idée : un état de Dicke par ligne et un mixer XY
gardent exactement 2 arcs sortants par nœud à toute profondeur. Sur network05 (20 qubits, cloud), les
degrés sortants sont bien respectés (masse 1,00 contre 0,13). Mais la part d'échantillons valides passe
seulement de 0,042 à 0,062 : **1,5 fois** au lieu des 10 fois visés. Les degrés entrants, encore pénalisés,
restent le goulot. Selon la règle de décision, network06 et network12 n'ont pas été lancés.

## 5. Tableau récapitulatif

Médiane sur 3 seeds (gap), à budget LP égal : 5 000 sur network12, 10 000 sur network24.

| Méthode | Qubits | network12 | network24 |
|---|---|---|---|
| B0 aléatoire | 0 | 317 215 (+14,74 %) | 788 125 (+18,75 %) |
| B1 SA kit (notebook) | 0 | 302 316 (+9,35 %) | 744 980 (+12,25 %) |
| H1 `h1_sa_fm` | 0 | 284 313 (+2,84 %) | 737 450 (+11,11 %) |
| H2 `h2_sa_phys` | 0 | 291 800 (+5,54 %) | **733 286 (+10,49 %)** |
| H1 + H2 `h2_fm_phys` | 0 | **282 556 (+2,20 %)** | 733 638 (+10,54 %) |
| H1 `h1_pce_fm` (quantique) | 16 / 33 | 289 400 (+4,68 %) | 747 595 (+12,64 %), **5 000 LP seulement** |

Meilleurs `.sol` rendus (validés par `qt.check_network_solution`) :

| Instance | Score | Gap | Qubits max | Méthode, seed | Fichier `results/network/` |
|---|---|---|---|---|---|
| network05 | 65 500 | 0,00 % (optimum) | 0 | b0_random, seed 0 | `20261121T215730Z_network05.sol` |
| network12 | **279 667** | **+1,15 %** | 0 | h2_fm_phys, seed 2 | `20261122T020928Z_network12.sol` |
| network24 | **722 459** | **+8,86 %** | 0 | h2_fm_phys, seed 0 | `20261122T020927Z_network24.sol` |
| network24 (quantique) | 731 660 | +10,24 % | **33** | h1_pce_fm, seed 1, cloud Qoro | `20261121T232032Z_network24.sol` |

## 6. Ce qu'on retient

- **La physique du routage et l'apprentissage en ligne battent le substitut du kit.** Les chemins à 2 sauts
  donnent le gain le plus simple ; la factorization machine ajoute un gain net sur network12 et sur la
  meilleure seed de network24.
- **Le budget LP doit être la seule limite.** Sous un plafond de temps, H1 perdait face à B1 sur network24 ;
  à 10 000 LP, il gagne. Comparer à temps fixe mesure la charge machine, pas la méthode.
- **Le quantique apporte l'échelle, pas encore la qualité.** PCE tourne à 33 qubits sur network24 pour un
  coût négligeable, mais il ne bat pas SA, et le QAOA contraint ne gagne qu'un facteur 1,5 en faisabilité.
- **Le cloud n'accélère pas les petits QAOA.** À 20 qubits, un run H4 a pris 24 min sur le cloud contre
  4,5 min en local. Le cloud sert pour les gros circuits (MPS 33 qubits) ou pour décharger le CPU.
- Limites : 3 seeds par méthode, pas de test statistique ; écart restant au parallel tempering : +8,86 %
  sur network24.

**Suite.**
1. Relancer `h1_pce_fm` sur network24 à 10 000 LP (annulé dans H1), pour une ablation à budget égal.
2. PCE à 33 qubits sur le QUBO H2, plus creux que celui de H1, donc plus rapide.
3. Un mixer qui préserve aussi les degrés entrants, ou un encodage par deux permutations (H5).

## 7. Reproduire et soumettre

```bash
export PYTHONPATH=src/network-experiments OMP_NUM_THREADS=1
uv run python -m h0.run --instance network12 --seed 0 1 2 --method b1_sa_kit
uv run python -m h1.run --instance network12 --seed 0 1 2 --method h1_sa_fm --rank 8 --beta 0.5 --lr 0.003 --l2 1e-2
uv run python -m h2.run --instance network24 --seed 0 --method h2_fm_phys --beta2 1 --lam 1 --rank 8 \
  --beta 0.5 --lr 0.003 --l2 1e-2 --time-limit 5400
uv run python -m h4.run --instance network05 --seed 0 1 2 --method h4_qaoa_dicke --layers 2 --population 20 \
  --iterations 10 --time-limit 1800
```

- `.sol` et métadonnées : `results/network/<timestamp>_network<NN>.{sol,json}`.
- Une ligne par run : `results/network/bench/<id>/<méthode>.jsonl`.
- Paramètres exacts et commandes complètes (dont le run PCE cloud) : section 4 de chaque `result.md`.

### Soumission Aqora

Le leaderboard ([aqora.io/qoro/pushquantum-2026-leaderboard](https://aqora.io/qoro/pushquantum-2026-leaderboard))
lit le dossier `pushquantum-2026-qoro` de notre stockage aqora : un `network<NN>.sol` par instance, et à
côté un `network<NN>.json` `{"qubits": …, "method": …}`. Il ne garde que **le meilleur score par
instance** (à égalité, le premier soumis). Pour que chaque hypothèse laisse une trace, on dépose et on
soumet en trois étapes, de la moins bonne à la meilleure :

| Étape | network05 | network12 | network24 |
|---|---|---|---|
| 1 | H4 QAOA Dicke-XY, 20 qubits (65 500) | H1 `h1_sa_fm` (283 900) | H1 `h1_pce_fm`, PCE 33 qubits (731 660) |
| 2 | H1 `h1_sa_fm` (65 500) | — | H1 `h1_sa_fm`, 10 000 LP (731 261) |
| 3 | H2 + H1 `h2_fm_phys` (65 500) | H2 + H1 `h2_fm_phys` (279 667) | H2 + H1 `h2_fm_phys` (722 459) |

Sur network05, toutes les méthodes trouvent l'optimum : le classement garde la première soumission, celle
du QAOA à 20 qubits. Sur network24, le classement final affiche 722 459 (0 qubit) ; le run à 33 qubits
reste dans l'historique des soumissions. Copies locales des fichiers déposés :
`results/network/aqora/stage<k>/`.
