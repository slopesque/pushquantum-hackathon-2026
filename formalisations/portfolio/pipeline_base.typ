#import "/template_article/lib.typ": *
#import "/_commun.typ": *

#show: article.with(
  title: "Optimisation de portefeuille (QOBLIB 06) : la pipeline de résolution du kit Qoro",
  authors: (
    (name: "Clément Metz", affiliation: "EPITA - Quantum"),
    (name: "Leith Chakroun", affiliation: "EPITA - Quantum"),
    (name: "Ugo Col", affiliation: "EPITA - Quantum"),
    (name: "Alexandre Baconnet", affiliation: "EPITA - Quantum"),
  ),
  abstract: [
    Ce document résume la chaîne de résolution fournie par Qoro dans le notebook
    `01_portfolio_optimisation.ipynb` : du chargement d'une instance QOBLIB jusqu'au fichier `.sol`
    rendu au jury. Il décrit chaque étape, les outils utilisés, les résultats obtenus par le kit et les
    limites qui motivent nos propres choix.
  ],
  keywords: ("Portefeuille", "QUBO", "QAOA", "PCE", "Divi", "QOBLIB"),
)

#show heading: set text(fill: accent)

= Le problème en bref

On joue le rôle d'un gérant de fonds pendant $T$ jours de bourse (10 ou 15), avec $n$ actions réelles
(de 10 à 400) et un capital de 1 million. Chaque jour, pour chaque action, on choisit de détenir de 0 à
3 « paquets » de 100 000 *en long* (on gagne si l'action monte) ou *en court* (on gagne si elle baisse).
Les cours futurs sont connus : il ne s'agit pas de prédire, mais de trouver la meilleure combinaison de
décisions.

- *Ce qui rapporte :* les gains sur les actions, et un petit intérêt sur le cash non investi.
- *Ce qui coûte :* les frais à chaque achat, vente ou changement de position ; le *risque*, pondéré par
  un paramètre $lambda$ ; de petits frais sur les ventes à découvert.
- *Les règles, chaque jour :* au plus $B$ paquets ouverts ($B = 4, 20, 50, 100$ pour
  $n = 10, 50, 200, 400$), et une position nette comprise entre $-5$ et $10$ paquets.

#enbref[
  Quand $lambda$ est petit, il suffit d'acheter ce qui monte et de vendre à découvert ce qui baisse. Quand
  $lambda$ est grand, toute position isolée est trop risquée : il faut trouver des *paires couvertes*
  (long sur une action, court sur une action corrélée). C'est là que le problème devient difficile.
]

Le score officiel est calculé par l'arbitre `qoblib_tools.py`. Plus il est bas, mieux c'est. La qualité
se mesure par l'écart au meilleur résultat publié :
$ "gap" = ("score" - "best known") / (|"best known"|) . $

= Vue d'ensemble de la pipeline

#single_column_table(
  headers: ("Étape", "Outil", "Ce qu'elle produit"),
  content: (
    [1. Charger l'instance], [`qt.load_portfolio_instance`], [Cours et covariances],
    [2. Modèle officiel], [`qt.PortfolioModel`], [Coefficients arrondis + arbitre],
    [3. QUBO], [`qt.PortfolioQUBO`], [`objective` + `penalty`],
    [4. Caractérisation (option)], [`characterize_and_validate`], [Conseils : $W$, partitions, angles],
    [5. Résolution], [SA, PCE ou QAOA partitionné], [Bitstrings candidats],
    [6. Décodage], [`q.decode`], [Positions (long, court)],
    [7. Réparation], [`model.repair`], [Solution faisable],
    [8. Recherche locale], [`model.local_search`], [Solution améliorée],
    [9. Score et fichier], [`model.score`, `write_solution`], [Fichier `.sol` à rendre],
  ),
  false,
  [Les neuf étapes de la pipeline du kit.],
)

= Les étapes en détail

== Charger l'instance

`qt.load_portfolio_instance("po_a010_t10_orig")` télécharge depuis QOBLIB, une seule fois, les cours
journaliers et les matrices de covariance. Le nom se lit : 10 actifs, 10 jours, données d'origine
(`orig`) ou générées (`s00` à `s02`).

== Construire le modèle officiel

`qt.PortfolioModel(instance, budget=4, lam="1e-4")` pré-calcule tous les coefficients (risque,
rendements, frais) avec exactement les mêmes arrondis que QOBLIB. Ce modèle est aussi *l'arbitre* :
`model.score(positions)` renvoie le score officiel, sa décomposition et la liste des règles violées.

== Transformer le problème en QUBO

`qt.PortfolioQUBO(model)` reproduit le modèle QOBLIB en bits :
- *positions :* un bit par (action, copie, sens, jour), soit $6 n T$ bits ;
- *slacks :* chaque règle est réécrite en égalité grâce à un registre binaire (4 bits pour le capital, 7
  pour le budget, chaque jour), soit $11 T$ bits.

Cela donne 710 variables pour $10 times 10$, et 36 165 pour $400 times 15$. Le résultat se présente en
deux morceaux : `objective`, le coût, et `penalty`, la somme des règles élevées au carré, qui vaut 0
exactement quand elles sont respectées. Le solveur minimise
$ E(x) = "objective"(x) + W dot "penalty"(x) . $

#warnbox(title: "Le réglage clé : le poids W")[
  Si $W$ est trop petit, les solutions trichent sur les règles. S'il est trop grand, le solveur ne cherche
  plus qu'à les respecter et ignore le gain. Le kit prend $W = 1000$ sur la petite instance et $W = 100$
  sur la grande, en comptant sur la réparation (étape 7) pour restaurer la faisabilité.
]

== Caractérisation (optionnelle, dans le cloud)

Le *Characterization Service* de Qoro analyse le QUBO et renvoie : les variables qu'on peut fixer
d'avance, la façon dont le problème se découpe, une valeur de $W$ recommandée, une baseline classique
avec une borne inférieure, et des angles QAOA pour démarrer à chaud. Il coûte des crédits,
proportionnellement à la taille du QUBO.

== Résoudre le QUBO

Le kit propose trois méthodes. Toutes produisent des *bitstrings candidats*, pas directement une
solution.

#single_column_table(
  headers: ("Méthode", "Type", "Principe"),
  content: (
    [Recuit simulé (SA)], [Classique], [100 parcours aléatoires qui « refroidissent » vers une bonne
      solution],
    [PCE], [Quantique], [Chaque variable est encodée dans un corrélateur de Pauli : 58 variables tiennent
      sur 11 qubits],
    [QAOA partitionné], [Quantique], [Le QUBO est découpé en blocs de 10 à 12 variables, un circuit
      QAOA par bloc (en parallèle dans le cloud), puis les morceaux sont recollés par beam search],
  ),
  false,
  [Les trois solveurs du kit.],
)

== Décoder

`q.decode(bits)` transforme les bits en positions `{(jour, action): (long, court)}` en comptant les
copies à 1.

== Réparer

`model.repair(positions)` : tant qu'une règle est violée, on retire l'unité dont le retrait dégrade le
moins le score. Le résultat est toujours faisable.

== Recherche locale

`model.local_search(positions)` essaie tous les mouvements « $plus.minus 1$ unité » sur chaque case
(jour, action, sens), applique le meilleur, et recommence tant que le score officiel s'améliore.

== Noter et écrire le fichier

`model.score(...)` donne le score officiel ; `model.write_solution(...)` écrit le fichier `.sol` au
format QOBLIB, nommé `<instance>_b<budget>_l<lambda>.sol`. C'est ce fichier qu'on rend, avec la taille
de l'instance, le nombre de qubits utilisés et la méthode.

= Ce que donne le kit

Sur `po_a010_t10_orig` avec $B = 4$ et $lambda = 10^(-4)$ (meilleur connu : $-69 thin 482$) :

#single_column_table(
  headers: ("Méthode", "Score", "Gap"),
  content: (
    [Recherche locale seule, depuis le portefeuille vide], [$-69 thin 372$], [0,16 %],
    [QAOA partitionné + réparation + recherche locale (meilleur de 3 seeds)], [$-69 thin 169$], [0,45 %],
    [SA + recherche locale], [$-69 thin 482$], [0 %],
  ),
  false,
  [Résultats du notebook 01 sur l'instance de référence.],
)

Et sur d'autres instances, avec SA + recherche locale :

#single_column_table(
  headers: ("Instance", "λ", "Meilleur connu", "Kit", "Gap"),
  content: (
    [a010_t10_orig], [5e-4], [−27 044], [−26 548], [1,8 %],
    [a010_t10_s02], [1e-4], [−53 255], [−51 805], [2,7 %],
    [a050_t10_orig], [1e-3], [−206 239], [−197 953], [4,0 %],
    [a010_t10_orig], [1e-3], [−8 397], [−3 703], [56 %],
    [a050_t10_orig], [1e-2], [−37 107], [−1 000], [97 %],
    [a200, a400], [tous], [aucun publié], [—], [—],
  ),
  false,
  [Les écarts explosent quand le risque domine (grand λ).],
)

= Limites et pistes

#warnbox(title: "Ce que montre le kit")[
  - *Le travail est surtout fait par les étapes 7 et 8, qui sont classiques.* Le QAOA partitionné fait même
    un peu moins bien que la recherche locale partie de zéro.
  - *Les étapes 7 et 8 ne passent pas à l'échelle :* elles recalculent tout le score à chaque mouvement
    testé, ce qui fait environ 70 s par passe pour 400 actions, et des heures au total.
  - *La recherche locale à un seul mouvement se bloque quand λ est grand*, car il faut bouger deux actions à
    la fois pour former une paire couverte.
  - *L'encodage QUBO est très redondant :* les 3 copies sont interchangeables, être long et court en même
    temps ne sert jamais, et les slacks ajoutent $11 T$ bits.
]

Nos réponses (détaillées dans `pistes.typ`) :
+ une variable entière $v in {-3, dots, 3}$ par action et par jour, soit $n T$ variables au lieu de
  $6 n T + 11 T$ bits ;
+ un évaluateur incrémental rapide, validé contre l'arbitre, pour une recherche locale qui passe à
  l'échelle ;
+ des mouvements par paires pour les grands $lambda$ ;
+ pour le quantique, une recherche à grand voisinage : une petite fenêtre (actions $times$ jours) est
  résolue par QAOA ou PCE avec le signe fixé et la quantité sur 2 bits (2 qubits par case), et n'est
  acceptée que si le score officiel s'améliore.
