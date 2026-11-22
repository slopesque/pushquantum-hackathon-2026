#import "/template_article/lib.typ": *
#import "/_commun.typ": *

#show: article.with(
  title: "Optimisation de portefeuille (QOBLIB 06) : recherche à grand voisinage (LNS) et sous-problèmes quantiques",
  authors: (
    (name: "Clément Metz", affiliation: "EPITA - Quantum"),
    (name: "Leith Chakroun", affiliation: "EPITA - Quantum"),
    (name: "Ugo Col", affiliation: "EPITA - Quantum"),
    (name: "Alexandre Baconnet", affiliation: "EPITA - Quantum"),
  ),
  abstract: [
    La recherche locale (P4) améliore une solution par petits pas et s'arrête au premier optimum local. La
    recherche à grand voisinage (LNS) fait de grands pas : elle libère un morceau de la solution, le réoptimise
    entièrement, et garde le résultat s'il est meilleur. Ce morceau, écrit comme un petit QUBO, est l'endroit
    naturel où brancher QAOA ou PCE. Ce document explique l'idée, formalise le sous-problème et ses
    approximations, décrit la mise en œuvre et rapporte ce que les premières expériences nous ont appris.
  ],
  keywords: ("LNS", "QUBO", "QAOA", "PCE", "Divi", "Portefeuille"),
)

#show heading: set text(fill: accent)

= L'idée en une page

*Le problème de la recherche locale.* Elle n'essaie que de petits changements : une ou deux cases de $plus.minus 1$,
éventuellement sur quelques jours. Quand aucun petit changement n'améliore le score, elle s'arrête. Or une
meilleure solution peut exister à condition de changer *beaucoup de cases en même temps* : par exemple
recomposer tout le panier d'un jour pour former une couverture entre plusieurs actions.

*Ce que fait le LNS.* On part de la meilleure solution connue et on répète :
+ *libérer* un morceau de la solution, la *fenêtre* (par exemple : toutes les actions sur 2 jours
  consécutifs), le reste étant *figé* ;
+ *réoptimiser* ce morceau, en cherchant la meilleure combinaison pour les cases libérées, le reste ne bougeant
  pas ;
+ *garder* le résultat s'il améliore le score, sinon revenir en arrière.

*L'analogie.* Un puzzle presque terminé, avec des pièces mal placées : la recherche locale échange deux pièces
voisines ; le LNS retire un bloc entier de pièces et le refait.

#enbref[
  Le morceau libéré devient un *petit QUBO* : c'est lui qu'on confie au quantique (QAOA ou PCE, via Divi). Le
  quantique ne voit jamais le problème entier (jusqu'à 36 165 variables), seulement des morceaux ; mais à force
  de morceaux, il améliore la solution globale. Et la boucle reste la même quel que soit le solveur du morceau :
  on compare donc honnêtement quantique et classique, à boucle identique.
]

C'est exactement l'idée « *hybrid loops* » proposée par Qoro dans le notebook 01 : « fixer la plupart des
variables à la solution courante, re-résoudre une fenêtre actions × jours avec QAOA/PCE, accepter si le score
officiel s'améliore, et recommencer ».

= Formalisation

== Notations

Une solution est $v in {-3, dots, 3}^(T times n)$ (encodage entier, P1) ; $f(v)$ est l'objectif et $cal(F)$
l'ensemble des solutions faisables. On note $G_t = R_t + R_t^top$, et pour une solution courante $v$ :
$"net"_t = sum_i v_(t,i)$ et $"total"_t = sum_i |v_(t,i)|$.

#definition(title: "Fenêtre")[
  Une *fenêtre* est un ensemble de cases $W = A times D$, où $A$ est un ensemble d'actions et $D$ un intervalle
  de jours consécutifs. On lui associe un *signe* $sigma_c in {+1, -1}$ par case $c = (t, i) in W$. Le
  *sous-problème* de la fenêtre est
  $ min_(m in {0, dots, 3}^W) f(v^m) quad "sous" quad v^m in cal(F), $
  où $v^m$ coïncide avec $v$ hors de $W$ et vaut $v^m_c = sigma_c m_c$ sur $W$.
]

Fixer le signe réduit chaque case à une *quantité* $m_c in {0, dots, 3}$. C'est ce qui rend le sous-problème
quadratique (voir P7 dans `pistes.typ`). Le signe d'une case est celui de la position actuelle si elle est non
nulle ; sinon le sens dans lequel ajouter une unité coûte le moins. Avec une petite probabilité (10 %), il est
inversé pour explorer.

#definition(title: "Boucle LNS")[
  Partant de $v in cal(F)$ (issue de la recherche locale), on répète jusqu'à la limite de temps :
  + tirer une fenêtre $W$ et ses signes $sigma$ ;
  + construire le QUBO $E_W$ de la fenêtre (section suivante) ;
  + demander au *sous-solveur* une liste de candidats $m^((1)), dots, m^((r))$ ;
  + *réparer* chaque candidat (le rendre faisable en retirant des unités dans la fenêtre) ;
  + calculer la variation *exacte* $Delta^((k)) = f(v^(m^((k)))) - f(v)$ de chaque candidat réparé ;
  + si $min_k Delta^((k)) < 0$, remplacer $v$ par le meilleur candidat.
]

#theorem(title: "Le LNS ne dégrade jamais la solution")[
  À chaque itération, la solution courante reste faisable et son objectif ne peut que baisser.
]
#proof[
  Un candidat n'est accepté que s'il est faisable (après réparation, vérifiée par l'évaluateur exact P2) et si
  sa variation *exacte* est négative. Les approximations du QUBO ne servent qu'à proposer des candidats ; elles
  n'interviennent jamais dans la décision.
]

== Le QUBO d'une fenêtre

On note $u_t$ la solution du jour $t$ où les cases de la fenêtre sont mises à zéro. Le sous-problème s'écrit
$ E_W (m) = Delta_0 + h^top m + m^top J m + "pénalités"(m), $
où $Delta_0$ est la variation de l'objectif quand toute la fenêtre est mise à zéro, *intérêts comptés
linéairement* (voir la remarque ci-dessous), et où $h$ (vecteur) et $J$ (matrice symétrique, diagonale comprise)
rassemblent les termes suivants.

#single_column_table(
  headers: ("Terme de l'objectif", "Contribution", "Statut"),
  content: (
    [Risque du jour $t$], [$h_c += sigma_c (G_t u_t)_i$ et $J_(c c') += sigma_c sigma_(c') R^"sym"_t (i, i')$],
    [Exact],
    [Rendement], [$h_c += -sigma_c "ret"_(t,i)$], [Exact],
    [Intérêts du cash], [$h_c += 10 sigma_c$ (les intérêts valent $10 dot$ slack)], [Exact si faisable],
    [Coût du court], [$h_c += "sc"_(t,i)$ si $sigma_c = -1$], [Exact],
    [Achat (jour 0), liquidation (jour $T-1$)], [$h_c += "tc"_(t,i)$], [Exact],
    [Transition interne, signes opposés], [$|m_a + m_b|$ : $h_a, h_b += "tc"$], [Exact],
    [Transition interne, même signe], [$|m_b - m_a| approx (m_b - m_a)^2$], [*Approché*],
    [Transition de bord, voisin figé $w$ nul ou de signe opposé], [$|sigma m - w| = m + |w|$], [Exact],
    [Transition de bord, voisin figé de même signe], [$|m - |w|| approx (m - |w|)^2$], [*Approché*],
  ),
  false,
  [Les termes du QUBO d'une fenêtre ($c = (t, i)$, $c' = (t, i')$ sur le même jour).],
)

#theorem(title: "Exactitude du QUBO")[
  Pour toute affectation $m$ telle que $v^m$ est faisable et que, pour chaque transition de même signe, l'écart
  de quantité est au plus 1, on a $E_W (m) - "pénalités"(m) = f(v^m) - f(v)$.
]
#proof[
  Le risque est quadratique en $v$ et $v^m_t = u_t + sum_c sigma_c m_c e_i$, d'où
  $f_"risque" (v^m_t) - f_"risque" (u_t) = sum_c sigma_c m_c (G_t u_t)_i + m^top (sigma sigma^top compose R^"sym"_t) m$.
  Les termes linéaires le sont en $v$, donc en $m$ à signe fixé. Les intérêts valent $10 dot (C - "net")$ tant que
  la position nette est dans ses bornes, ce qui est le cas pour une solution faisable. Pour les frais, $|x - y|$
  vaut $x + y$ si les signes s'opposent, et $(x - y)^2 = |x - y|$ dès que $|x - y| <= 1$.
]

#remark[
  L'état intermédiaire « fenêtre à zéro » peut être infaisable : sa position nette peut sortir des bornes
  (par exemple $-6 < -5$). Là, les intérêts exacts ne sont plus linéaires (le slack de cash déborde de ses 4
  bits et vaut 0 au lieu de 160). $Delta_0$ est donc calculé avec la formule linéaire $10 dot "slack"$, la même
  que dans $h$ : c'est ce qui rend le théorème vrai pour *toute* affectation finale faisable. Une première version
  utilisait les intérêts exacts et a été corrigée grâce au test ; comme $Delta_0$ est commun à tous les
  candidats d'une fenêtre, l'erreur ne changeait ni leur classement ni les décisions.
]

Ce théorème est vérifié par les tests (`tests/test_portfolio_lns.py`) : sur des milliers d'affectations, l'écart
entre le QUBO et l'objectif exact est nul sur toutes les solutions faisables ; les seuls écarts concernent des
affectations infaisables, qui sont de toute façon réparées avant d'être évaluées.

*Les contraintes.* Pour chaque jour de la fenêtre, si une contrainte (budget, bornes de la position nette)
peut être violée, on ajoute une pénalité $mu x (x + 1)$ où $x <= 0$ exprime la contrainte. Elle est nulle en
$x = 0$ et $x = -1$ (budget saturé ou presque), et croît de part et d'autre. Le poids est
$mu = "penalty_scale" times$ la moyenne de $|h|$. Une pénalité trop forte noie l'objectif, une trop faible
laisse passer des candidats infaisables : la réparation les rattrape, mais au prix de candidats moins bons.

== Des quantités aux bits, et le nombre de qubits

Chaque quantité s'écrit sur 2 bits : $m_c = b_(2c) + 2 b_(2c+1)$. Avec la matrice $P$ qui réalise cette
écriture ($m = P b$), le QUBO en bits a pour termes $P^top h + "diag"(P^top J P)$ (linéaires, car $b^2 = b$) et
$2 (P^top J P)_(j k)$ pour $j < k$ (quadratiques). Une fenêtre de $K$ cases donne donc $2K$ variables binaires.

#single_column_table(
  headers: ("Sous-solveur", "Qubits pour 2K variables", "Remarque"),
  content: (
    [Énumération], [—], [Exacte sur le QUBO, jusqu'à 22 bits ($K <= 11$)],
    [Recuit simulé], [—], [Classique, sur le même QUBO : la référence du quantique],
    [QAOA (Divi)], [$2K$], [Un qubit par bit : simulé en local jusqu'à une vingtaine de qubits],
    [PCE (Divi)], [environ $sqrt(4K)$ avec `PolyEncoding`], [200 bits tiennent sur une vingtaine de qubits],
  ),
  false,
  [Les sous-solveurs et leur taille quantique.],
)

#warnbox(title: "Deux pièges de Divi, rencontrés et contournés")[
  - *L'ordre des variables.* Divi lit les bits dans l'ordre *interne* du BQM dimod, qui n'est pas forcément
    $0, 1, 2, dots$ : une variable qui apparaît d'abord dans un couplage est rangée plus tôt. On construit donc
    toujours le BQM avec `from_numpy_vectors`, qui range les variables dans l'ordre $0 dots 2K - 1$.
  - *PCE renvoie deux choses.* `bitstring` est la mesure brute des qubits encodés, pas la solution ; la
    solution est dans `decoded` (avec `include_decoded=True`).

  Dans tous les cas, on recalcule nous-mêmes l'énergie et l'objectif exact de chaque candidat.
]

== Réparation

Un candidat infaisable est réparé en retirant des unités dans la fenêtre, une à la fois : à chaque étape, on
retire celle qui donne le meilleur objectif exact (en préférant les retraits qui rendent la solution faisable).
Retirer des unités ne peut que réduire l'usage du budget ; la réparation échoue seulement si la position nette
sort de ses bornes même fenêtre vide, et le candidat est alors écarté.

= Quelles fenêtres ? Ce que les expériences nous ont appris

Le choix de la fenêtre décide de tout. Notre première idée (3 actions × 3 jours) ne donnait *aucune*
amélioration ; voici comment nous avons trouvé la bonne forme.

== Les petites fenêtres sont épuisées par la recherche locale

Avec des fenêtres de 3 actions × 3 jours, les quatre sous-solveurs (énumération, recuit, QAOA, PCE) n'ont
accepté *aucun* candidat en 30 s, sur a010_t10_orig et a050_t10_orig ($lambda = 10^(-3)$). Pour savoir si le
QUBO était en cause, nous avons énuméré, sur 60 fenêtres de 2 actions × 3 jours, *toutes* les affectations
avec l'objectif *exact* : aucune n'améliore la solution, ni à signes fixés, ni même à signes libres.

#enbref[
  Le QUBO n'y était pour rien : la recherche locale (P4), avec ses blocs, paires et échanges, a déjà optimisé
  tout ce qu'une petite fenêtre peut changer. Pour aller plus loin, il faut changer *beaucoup* de cases à la fois.
]

== Comparaison avec les meilleures solutions connues

Nous avons comparé nos solutions aux meilleures solutions publiées par QOBLIB : où diffèrent-elles ?

#single_column_table(
  headers: ("Cas", "Gap", "Cases différentes", "Actions", "Jours", "Changements de signe"),
  content: (
    [a010_t10_orig, $lambda = 10^(-3)$], [4,9 %], [8], [6 sur 10], [2], [0],
    [a050_t10_orig, $lambda = 5 dot 10^(-4)$], [1,9 %], [64], [36 sur 50], [6], [0],
    [a050_t10_orig, $lambda = 10^(-3)$], [8,3 %], [107], [44 sur 50], [8], [0],
    [a050_t10_orig, $lambda = 10^(-2)$], [97 %], [63], [36 sur 50], [4], [0],
  ),
  false,
  [Écarts entre notre recherche locale et le meilleur connu.],
)

Deux enseignements :
+ les différences touchent *beaucoup d'actions sur peu de jours* : la bonne fenêtre est *large et courte*,
  c'est-à-dire « recomposer tout le panier d'un jour », ce que ferait un gérant ;
+ il n'y a *jamais* de changement de signe : fixer le signe des cases ne coûte rien ici.

À $lambda = 10^(-2)$, la référence détient un panier diversifié de 20 unités (le budget) pendant les jours 1 à 3
et le jour 8 ; nous restons au portefeuille vide. Une couverture isolée ne paie pas ses frais ; il faut
construire le panier entier, et le tenir plusieurs jours.

== Réglage : fenêtres pleine largeur, 1 ou 2 jours

Recuit simulé comme sous-solveur, fenêtre couvrant toutes les actions, 60 s de LNS après la recherche locale :

#single_column_table(
  headers: ("Fenêtre", "Pénalité", [a010, $lambda = 10^(-3)$], [a050, $lambda = 10^(-3)$], [a050, $lambda = 10^(-2)$]),
  content: (
    [recherche locale seule], [—], [4,86 %], [8,31 %], [97,3 %],
    [toutes × 1 jour], [0,2], [*0,00 %*], [*2,63 %*], [53,0 %],
    [toutes × 2 jours], [0,1], [0,42 %], [4,05 %], [95,3 %],
    [toutes × 2 jours], [0,2], [*0,00 %*], [4,77 %], [*43,7 %*],
    [toutes × 3 jours], [0,1], [0,00 %], [5,45 %], [97,3 %],
    [toutes × 3 jours], [0,2], [3,78 %], [6,54 %], [97,3 %],
  ),
  false,
  [Gap au meilleur connu selon la forme de la fenêtre et le poids de pénalité.],
)

- Sur a010, $lambda = 10^(-3)$, le LNS *retrouve le meilleur connu* ($-8 thin 397$), là où la recherche locale
  restait à 4,9 %.
- Les fenêtres d'un jour font beaucoup d'itérations et marchent le mieux à $lambda = 10^(-3)$ ; celles de deux
  jours sont nécessaires à $lambda = 10^(-2)$, pour amortir les frais d'un panier tenu plusieurs jours. Nous
  tirons donc la longueur au hasard, 1 ou 2 jours, à chaque itération.
- Une pénalité trop faible (0,1) laisse passer des candidats infaisables que la réparation dégrade ; nous
  retenons 0,2.

Sur les grandes instances (a200, a400), une fenêtre pleine largeur aurait jusqu'à 1 600 bits : la stratégie
`wide` retient au plus 50 actions — celles détenues ces jours-là, puis les plus intéressantes à ajouter, puis
des actions au hasard.

= Mise en œuvre et utilisation

#single_column_table(
  headers: ("Élément", "Où", "Rôle"),
  content: (
    [`WindowSampler`], [`lns.py`], [Tire les fenêtres (stratégie `wide` par défaut)],
    [`choose_signs`], [`lns.py`], [Fixe le signe de chaque case],
    [`build_window_qubo`], [`lns.py`], [Construit $E_W$ (objectif, approximations, pénalités)],
    [`WindowQUBO`], [`lns.py`], [Énergies, passage aux bits, BQM pour Divi et dimod],
    [`EnumSolver`, `SASolver`, `DiviSolver`], [`lns.py`], [Les sous-solveurs (qubits et circuits comptés)],
    [`repair`, `lns`], [`lns.py`], [Réparation et boucle],
    [`lns-*`], [`methods.py`], [Les méthodes du banc d'essai],
  ),
  false,
  [Les briques du LNS.],
)

Méthodes enregistrées (toutes : recherche locale `ls-full`, puis LNS jusqu'à la limite de temps, puis une
dernière descente) :

#single_column_table(
  headers: ("Méthode", "Fenêtre", "Sous-solveur", "Taille quantique"),
  content: (
    [`lns-enum`], [10 actions × 1 jour (20 bits)], [Énumération exacte du QUBO], [—],
    [`lns-sa-small`], [8 actions × 1 jour (16 bits)], [Recuit simulé], [— (référence de QAOA)],
    [`lns-qaoa`], [8 actions × 1 jour (16 bits)], [QAOA, Divi], [16 qubits],
    [`lns-sa`], [50 actions × 1 ou 2 jours (jusqu'à 200 bits)], [Recuit simulé], [— (référence de PCE)],
    [`lns-pce`], [50 actions × 1 ou 2 jours (jusqu'à 200 bits)], [PCE, Divi], [environ 20 qubits],
  ),
  false,
  [Chaque méthode quantique a sa référence classique sur *exactement* les mêmes fenêtres.],
)

```bash
uv run scripts/bench_portfolio.py --set hard --methods ls-full lns-sa lns-pce --time 60 --label essai
```

Le jeu `hard` regroupe les 9 cas où la recherche locale est faible (a010_t10_orig, a050_t10_orig et
a050_t10_s01, pour $lambda in {5 dot 10^(-4), 10^(-3), 10^(-2)}$). Par défaut, QAOA et PCE tournent sur le
simulateur local ; le cloud Qoro s'active avec `use_cloud=True` dans `divi_solver` (crédits consommés).

= Résultats : le LNS marche, le quantique pas encore

Jeu `hard` (9 cas), 60 s par méthode, une seed, tous sur le même commit
(`results/portfolio/bench/20261121T183659Z_p7-hard/`). Chaque méthode quantique est comparée au recuit simulé
sur *exactement* les mêmes fenêtres.

#single_column_table(
  headers: ("Cas", [`ls-full`], [`lns-sa`], [`lns-pce`], [`lns-sa-small`], [`lns-qaoa`], [`lns-enum`]),
  content: (
    [a010 $10^(-3)$], [4,86 %], [*0,00 %*], [0,60 %], [0,00 %], [3,97 %], [3,97 %],
    [a050 $5 dot 10^(-4)$], [1,91 %], [*1,04 %*], [1,91 %], [1,91 %], [1,91 %], [1,81 %],
    [a050 $10^(-3)$], [8,31 %], [*2,03 %*], [8,31 %], [8,01 %], [8,31 %], [8,10 %],
    [a050 $10^(-2)$], [97,3 %], [*72,5 %*], [97,3 %], [97,3 %], [97,3 %], [97,3 %],
    [s01 $5 dot 10^(-4)$], [6,31 %], [*1,25 %*], [6,31 %], [6,15 %], [6,28 %], [6,28 %],
    [s01 $10^(-3)$], [27,9 %], [*2,73 %*], [27,9 %], [25,5 %], [27,9 %], [27,9 %],
    [s01 $10^(-2)$], [55,5 %], [55,5 %], [55,5 %], [55,5 %], [55,5 %], [55,5 %],
  ),
  false,
  [Gap au meilleur connu (a010 et a050 : `_orig` ; s01 : a050_t10_s01). Les deux cas déjà à 0 % pour toutes
    les méthodes (a010, $lambda = 5 dot 10^(-4)$ et $10^(-2)$) sont omis.],
)

#figure(
  image("figures/p7_hard_gap_by_case.png", width: 100%),
  caption: [Jeu `hard` : `lns-sa` (triangles roses) décroche nettement des autres méthodes.],
)

== Ce que ça montre

+ *Le LNS avec fenêtres pleine largeur marche très bien.* Avec le recuit simulé comme sous-solveur, il divise
  le gap par 4 à 10 sur les cas difficiles : de 27,9 % à 2,7 % sur a050_t10_s01 ($lambda = 10^(-3)$), de 8,3 % à
  2,0 % sur a050_t10_orig, et il retrouve le meilleur connu sur a010 ($lambda = 10^(-3)$).
+ *Les petites fenêtres n'apportent presque rien*, quel que soit le sous-solveur (`lns-enum`, `lns-sa-small`,
  `lns-qaoa`) : c'est la forme de la fenêtre qui compte, pas la qualité du solveur.
+ *Le quantique, en l'état, ne fait pas mieux que le classique à fenêtres égales*, et le plus souvent moins
  bien. Sur les mêmes 12 fenêtres de 200 bits (a050_t10_s01, $lambda = 10^(-3)$) :

#single_column_table(
  headers: ("Sous-solveur", "Fenêtres améliorantes", "Gain moyen par fenêtre", "Temps par fenêtre"),
  content: (
    [Recuit simulé], [*8 / 12*], [$-2 thin 130$], [0,2 s],
    [PCE (20 qubits, simulé)], [3 / 12], [$-632$], [3,6 s],
  ),
  false,
  [À fenêtres identiques, PCE est moins bon *et* 18 fois plus lent ; en 60 s il traite donc bien moins de fenêtres.],
)

+ *$lambda = 10^(-2)$ reste difficile* : 72 % sur a050_t10_orig, et aucun progrès sur a050_t10_s01. Il faut
  probablement des fenêtres plus longues pour amortir les frais d'un panier tenu plusieurs jours, ou un autre
  point de départ que le portefeuille vide.

#warnbox(title: "Honnêteté sur la part quantique")[
  À ce stade, *nos résultats viennent du LNS classique*. La boucle est prête pour le quantique (même QUBO, mêmes
  fenêtres, comptage des qubits et des circuits), mais QAOA et PCE, avec leurs réglages par défaut et sur le
  simulateur local, ne battent pas le recuit simulé. Il ne faut pas présenter `lns-sa` comme un résultat
  quantique.

  Une limite pratique aussi : le temps n'est vérifié qu'entre deux fenêtres ; avec PCE, une fenêtre longue fait
  dépasser la limite (jusqu'à 108 s pour 60 s demandées).
]

== Pistes pour la part quantique

- *Donner plus de budget à PCE* (population, itérations, couches, `alpha`) et mesurer le taux de fenêtres
  améliorantes à fenêtre égale, avant de regarder le temps.
- *Démarrer à chaud* : la solution courante de la fenêtre est un très bon candidat ; la passer en état de
  référence (`reference_states`) et partir des angles du Characterization Service.
- *Paralléliser dans le cloud Qoro* : les fenêtres de jours différents sont indépendantes ; en lancer beaucoup en
  parallèle compense la lenteur d'une fenêtre.
- *Objectif CVaR* pour PCE (`CVaRObjective`), mieux adapté à la recherche du meilleur échantillon.
- *Mesurer le juste critère* : pour l'échelle, le jury compte les qubits du plus gros programme ; PCE traite
  déjà des fenêtres de 200 bits sur 20 qubits, il reste à ce qu'il le fasse *utilement*.
