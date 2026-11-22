#import "/template_article/lib.typ": *
#import "/_commun.typ": *

#show: article.with(
  title: "Optimisation de portefeuille (QOBLIB 06) : notes de travail",
  authors: (
    (name: "Clément Metz", affiliation: "EPITA - Quantum"),
    (name: "Leith Chakroun", affiliation: "EPITA - Quantum"),
    (name: "Ugo Col", affiliation: "EPITA - Quantum"),
    (name: "Alexandre Baconnet", affiliation: "EPITA - Quantum"),
  ),
  abstract: [
    Journal des constats, mises en garde et questions ouvertes rencontrés en cours de route, du plus récent
    au plus ancien. Les pistes elles-mêmes sont décrites dans `pistes.typ` ; ce document garde la trace de
    ce qu'on a appris et de ce qu'il ne faut pas surinterpréter.
  ],
  keywords: ("Portefeuille", "Notes", "Benchmarks"),
)

#show heading: set text(fill: accent)

= 21 novembre 2026 (soir) : le LNS marche, le quantique pas encore

*Constat.* Avec des fenêtres pleine largeur (toutes les actions sur 1 ou 2 jours), le LNS avec recuit simulé
divise le gap par 4 à 10 sur les cas difficiles. Avec QAOA ou PCE comme sous-solveur, à fenêtres identiques,
on ne fait presque jamais mieux que la recherche locale de départ (seule exception : PCE sur a010,
$lambda = 10^(-3)$, de 4,86 % à 0,60 %, là où le recuit atteint 0 %). Détails : `lns.typ`.

#warnbox(title: "À ne pas surinterpréter")[
  - Les bons résultats du LNS sont *classiques* (`lns-sa`). Les présenter comme quantiques serait faux.
  - Une seule seed par cas : les écarts entre méthodes proches (moins de 0,5 point) ne sont pas significatifs.
  - PCE dépasse la limite de temps (le temps n'est vérifié qu'entre deux fenêtres) : jusqu'à 108 s pour 60 s.
]

*Ce qu'on a appris en route.*
- La forme de la fenêtre compte bien plus que le sous-solveur : petites fenêtres = aucun gain, quel que soit
  le solveur, même exact.
- Divi lit les bits dans l'ordre interne du BQM dimod (pas forcément $0, 1, 2, dots$) et, pour PCE,
  `bitstring` n'est pas la solution (il faut `decoded`). On construit les BQM avec `from_numpy_vectors` et on
  recalcule toujours les énergies nous-mêmes.
- Un état intermédiaire (fenêtre à zéro) peut être infaisable : les intérêts n'y sont plus linéaires. Le test
  d'exactitude du QUBO l'a révélé ; le décalage est maintenant calculé avec des intérêts linéaires.

= 21 novembre 2026 : les solutions a400 sont valides et rapides, pas forcément bonnes

*Contexte.* La recherche locale `ls-full-b20` produit en moins de 10 s une solution pour chacune des 8 valeurs
de $lambda$ de `po_a400_t15_orig` (36 165 variables QUBO). On s'est demandé si une telle vitesse n'était pas
suspecte.

== Ce qui est établi

- *Les solutions sont valides.* L'arbitre officiel a relu chaque `.sol` et recalculé son score : ni bug de
  calcul, ni contrainte violée.
- *La vitesse s'explique.* En encodage entier, a400_t15 compte 6 000 variables. L'évaluateur teste environ
  $6 dot 10^6$ mouvements par passe en quelques dizaines de millisecondes, et la descente applique 1 000 à
  2 000 mouvements avant de s'arrêter.

== Ce qu'on ne sait pas : la qualité

#warnbox(title: "À ne pas surinterpréter")[
  Une descente s'arrête au *premier optimum local* : le point où aucun mouvement de ses voisinages n'améliore
  plus le score. Ce point peut être *très loin du vrai optimum*. Sur a050, la même méthode est à 0 % du
  meilleur connu pour les petits $lambda$, mais à 9 % pour $lambda = 10^(-3)$ et à 97 % pour
  $lambda = 10^(-2)$.

  Pour a400, *aucun meilleur connu n'est publié* : on ignore notre écart à l'optimum. Le « 0 % » affiché pour
  a400 dans les graphes signifie seulement « le meilleur parmi nos méthodes », pas « optimal ». Il ne faut
  donc pas écrire qu'on a « résolu » a400 : on a produit des solutions valides, de qualité inconnue.
]

== Vérification : l'optimum exact à $lambda = 0$

Sans terme de risque, l'objectif est *linéaire* (rendement, frais, intérêts, coût du court) : un solveur
MILP (HiGHS, via `scipy.optimize.milp`) en donne l'optimum prouvé. Les valeurs absolues des frais de
transition sont linéarisées par des variables auxiliaires $u >= plus.minus (x_t - x_(t-1))$.

#single_column_table(
  headers: ("Instance", "Optimum MILP", "Temps", "`ls-full-b20`", "Écart"),
  content: (
    [a050_t10_orig], [$-501 thin 737$ (= meilleur connu, optimal)], [0,0 s], [$-501 thin 737$], [0 %],
    [a400_t15_orig], [$-4 thin 194 thin 965$ (prouvé)], [0,4 s], [$-4 thin 194 thin 749$], [0,005 %],
  ),
  false,
  [À $lambda = 0$, la descente locale est quasi optimale ; le MILP retrouve l'optimum publié sur a050.],
)

== Ce qu'on en retient

+ *La taille n'est pas la difficulté.* Sans risque, même a400 se résout exactement en moins d'une seconde.
+ *La difficulté, c'est le risque* ($lambda > 0$) : le problème devient quadratique, avec des couvertures
  entre actions. C'est là que nos solutions a400 sont probablement loin de l'optimum, sans qu'on puisse le
  mesurer.
+ *Actions :*
  - ajouter une méthode exacte pour $lambda = 0$ (optimum prouvé sur les 32 instances, a200 et a400 compris) ;
  - obtenir des *bornes* pour $lambda > 0$ (solveur quadratique en nombres entiers, piste P6), seul moyen de
    chiffrer notre écart sur a200 et a400 ;
  - concentrer P5 et P7 sur les grands $lambda$.
