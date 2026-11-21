#import "/template_article/lib.typ": *
#import "/_commun.typ": *

#show: article.with(
  title: "Optimisation de portefeuille (QOBLIB 06) : les pistes que nous explorons",
  authors: (
    (name: "Clément Metz", affiliation: "EPITA - Quantum"),
    (name: "Leith Chakroun", affiliation: "EPITA - Quantum"),
    (name: "Ugo Col", affiliation: "EPITA - Quantum"),
    (name: "Alexandre Baconnet", affiliation: "EPITA - Quantum"),
  ),
  abstract: [
    Ce document recense les pistes que nous explorons sur le problème de portefeuille du hackathon Qoro ×
    PushQuantum : où nous voulons aller, pourquoi, et dans quel ordre. Il complète le résumé de la pipeline
    du kit (`pipeline_base.typ`) et sera mis à jour au fil des résultats.
  ],
  keywords: ("Portefeuille", "QUBO", "LNS", "QAOA", "PCE", "Divi"),
)

#show heading: set text(fill: accent)

// Étiquettes d'état des pistes
#let etat(label, couleur) = box(
  fill: couleur.lighten(80%),
  stroke: 0.5pt + couleur,
  radius: 2pt,
  inset: (x: 4pt, y: 2pt),
  text(size: 7pt, fill: couleur, weight: "bold", label),
)
#let afaire = etat("À FAIRE", rgb("#64748b"))
#let encours = etat("EN COURS", rgb("#C77700"))
#let fait = etat("FAIT", rgb("#15803d"))
#let abandon = etat("ABANDONNÉ", rgb("#b91c1c"))

= Objectifs

Le jury juge deux choses : *l'échelle* (taille de l'instance, qubits du plus gros programme quantique) et la
*qualité* (écart au meilleur résultat publié). Nous en tirons trois objectifs :

+ *Échelle.* Aucun résultat n'est publié pour 200 et 400 actifs. Une solution faisable et de bonne qualité
  sur `po_a400_t15` (36 165 variables) serait la première référence connue.
+ *Qualité.* Sur a010 et a050, s'approcher des meilleurs connus, ou les battre, en particulier pour les
  grands $lambda$ où le kit est loin (56 % et 97 % de gap).
+ *Contribution quantique honnête.* Le quantique doit faire une partie identifiable du travail, et on le
  compare au même pipeline avec un sous-solveur classique.

#enbref[
  Un socle classique rapide (encodage entier, évaluateur incrémental, recherche locale) nous donne
  l'échelle et une barre à battre. Une recherche à grand voisinage, dont les sous-problèmes sont résolus par
  QAOA ou PCE avec un QUBO compact, nous donne la part quantique.
]

= Vue d'ensemble

#single_column_table(
  headers: ("Piste", "Rôle", "État"),
  content: (
    [P1. Encodage entier $v in {-3..3}$], [Réduire le problème], [#fait],
    [P2. Évaluateur incrémental], [Passer à l'échelle], [#fait],
    [P3. Harnais de test], [Mesurer], [#fait],
    [P4. Recherche locale rapide + mouvements par paires], [Baseline classique], [#afaire],
    [P5. Métaheuristiques (SA, tabou) en entiers], [Baseline forte], [#afaire],
    [P6. Solveur exact (SCIP) sur petites instances], [Bornes, contrôle], [#afaire],
    [P7. LNS quantique, QUBO à signe fixé (2 bits/case)], [Part quantique], [#afaire],
    [P8. Choix des fenêtres du LNS], [Efficacité du LNS], [#afaire],
    [P9. Réglage des pénalités et caractérisation], [Qualité des sous-QUBO], [#afaire],
    [P10. PCE sur de grosses fenêtres], [Échelle en qubits], [#afaire],
  ),
  false,
  [Les pistes et leur état. Cette table est tenue à jour.],
)

= Socle classique

== P1. Encodage entier : une variable de $-3$ à $+3$

Être long et court sur la même action le même jour ne sert jamais. On remplace donc $(L, S)$ par une seule
valeur $v = L - S in {-3, dots, 3}$. Toutes les composantes du score s'écrivent simplement :

#single_column_table(
  headers: ("Quantité", "Formule"),
  content: (
    [Budget], [$sum_i |v_(t,i)| <= B$],
    [Capital], [$-5 <= sum_i v_(t,i) <= 10$],
    [Frais de changement], [$"tc"_(t,i) dot |v_(t,i) - v_(t-1,i)|$ (exact)],
    [Frais d'achat et de liquidation], [$"tc" dot |v|$],
    [Coût du court], [$"sc" dot max(-v, 0)$],
    [Risque], [$v_t^top R_t v_t$],
    [Intérêts du cash], [$-10 dot (10 - sum_i v_(t,i))$, linéaire],
  ),
  false,
  [Le score officiel dans l'encodage entier.],
)

*Gain :* $n T$ variables à 7 valeurs au lieu de $6 n T + 11 T$ bits. Pour a400_t15, cela fait 6 000
variables au lieu de 36 165. Toutes nos solutions vivent dans cet espace, et on ne repasse en $(L, S)$ que
pour écrire le `.sol`.

== P2. Évaluateur incrémental

La recherche locale du kit recalcule le score entier pour chaque mouvement testé : environ 3 ms par appel
sur a400, soit environ 70 s par passe. Un mouvement $v_(t,i) arrow.r v_(t,i) + delta$ ne modifie que :
- le risque du jour $t$ : $Delta = 2 delta (R_t v_t)_i + delta^2 R_(t,i i)$, en $O(1)$ si on maintient le
  produit $R_t v_t$ (mise à jour en $O(n)$ après un mouvement accepté) ;
- le rendement, le coût du court et les intérêts : termes linéaires, en $O(1)$ ;
- les frais avec les jours $t - 1$ et $t + 1$ : en $O(1)$ ;
- le budget et le capital du jour $t$ : on maintient les sommes, en $O(1)$.

*Validation :* sur des milliers de solutions aléatoires et sur les solutions de référence QOBLIB, le score
recalculé doit être *exactement* celui de l'arbitre.

#keybox(title: "Résultat (implémenté)")[
  - `src/hackathon/solvers/portfolio/problem.py` : *notre formulation du problème*. Elle charge les données
    QOBLIB (cours, covariances), calcule les coefficients du modèle, l'objectif, les contraintes, et lit et
    écrit les `.sol`. Elle ne dépend pas de l'arbitre.
  - `src/hackathon/solvers/portfolio/evaluator.py` : `PortfolioState`, une solution plus les quantités
    maintenues ($G_t v_t$ avec $G_t = R_t + R_t^top$, position nette, unités ouvertes, objectif).
    - `delta(changes)` : variation exacte pour n'importe quel petit mouvement (simple, paire, bloc, échange).
    - `apply(changes)` : applique le mouvement en $O(n)$ par jour touché.
    - `single_move_deltas()` : les $2 T n$ mouvements simples d'un coup, vectorisés.

  *Tests.* L'évaluateur est testé contre notre propre objectif. L'arbitre ne sert qu'à valider la formulation
  (`tests/test_portfolio_problem.py`, 8 cas de a003 à a200) : coefficients, objectif, contraintes et `.sol`
  identiques ; solutions de référence retrouvées au point près. Aucune des 16 solutions de référence
  examinées n'est longue et courte sur la même case.

  *Vitesse sur a400_t15 :* évaluer les 12 000 mouvements simples prend 0,2 ms, contre 31 s avec l'arbitre.
  Construire le modèle prend 0,1 à 1,4 s (17 s avec l'arbitre), plus 7 s de lecture des fichiers.
]

#warnbox[
  - `delta` ne vérifie la faisabilité que sur les jours touchés : c'est exact tant que la solution courante est
    faisable, ce qui est le cas pendant une recherche locale.
  - *Arrondis.* Les coefficients sont arrondis comme dans le modèle Zimpl de QOBLIB (demi-entier loin de
    zéro). Le risque est calculé en flottants ; les rares valeurs proches d'un demi-entier sont recalculées en
    fractions exactes (2 cellules sur a200 avec $lambda = 10^(-2)$).
  - *Propriété du modèle officiel, conservée :* le passage du jour $T-2$ au jour $T-1$ n'est pas facturé, seule
    la liquidation l'est. On la garde, car c'est sur ce modèle que les solutions sont jugées.
]

== P3. Harnais de test

Le but : répondre avec des chiffres à « cette méthode est-elle meilleure que la précédente ? », et produire
les fichiers à rendre.

=== Les cas

Un *cas* est une instance et un poids de risque $lambda$ ; le budget $B$ en découle ($B = 4, 20, 50, 100$
pour $n = 10, 50, 200, 400$). La grille officielle compte 32 instances (8 tailles $times$ 4 seeds de
données : `orig`, `s00` à `s02`) $times$ 8 valeurs de $lambda$, soit *256 cas*.

#single_column_table(
  headers: ("Jeu", "Contenu", "Cas", "Usage"),
  content: (
    [`dev`], [a010_t10_orig (8 λ), a050_t10_orig (λ = 1e-4, 1e-3, 1e-2), a200_t10_orig (λ = 1e-4)], [12],
    [Itérer vite],
    [`a010`, `a050`], [Toutes les instances de cette taille], [64], [Qualité],
    [`known`], [a010 et a050 : tous les cas avec un meilleur connu], [128], [Gap publié],
    [`large`], [a200 et a400 : aucun meilleur connu], [128], [Échelle],
    [`a400`], [a400_t15_orig, 8 λ (36 165 variables QUBO)], [8], [Le plus gros],
    [`full`], [Toute la grille], [256], [Résultats finaux],
  ),
  false,
  [Les jeux de cas prédéfinis (`SETS` dans `benchmark.py`).],
)

=== Le protocole

#definition(title: "Cas, méthode, exécution")[
  Un *cas* $c = (I, lambda)$ est une instance $I$ (donc $n$ actions, $T$ jours) et un poids de risque
  $lambda$ ; il fixe le budget $B(n)$ et l'objectif $f_c : {-3, dots, 3}^(T times n) -> ZZ$ (P1), avec
  l'ensemble faisable $cal(F)_c$. Une *méthode* est une fonction $M(c, omega, tau) in cal(F)_c$ d'un cas,
  d'une graine aléatoire $omega$ et d'une limite de temps $tau$. Une *exécution* $(c, M, omega)$ produit la
  solution $v = M(c, omega, tau)$, son score $f_c (v)$ et son temps de calcul.
]

#definition(title: "Agrégats par cas et par méthode")[
  Pour un ensemble de graines $Omega$ :
  $ f^*_c (M) = min_(omega in Omega) f_c (M(c, omega, tau)), quad
    tilde(f)_c (M) = op("médiane")_(omega in Omega) f_c (M(c, omega, tau)), $
  calculés sur les seules exécutions faisables.
]

#definition(title: "Gap et référence")[
  Le gap d'un score $f$ par rapport à une référence $r$ est
  $ g(f, r) = (f - r) / (|r|) . $
  La référence est le meilleur connu publié par QOBLIB, $r_c = "BKV"_c$, quand il existe (a010, a050).
  Sinon (a200, a400), on prend dans les graphes le meilleur score des méthodes comparées,
  $r_c = min_M f^*_c (M)$ : le gap mesure alors l'écart entre méthodes, pas à un optimum. $g = 0$ égale la
  référence, $g < 0$ la bat.
]

- Chaque méthode reçoit la même *limite de temps* par exécution et tourne avec plusieurs *seeds* (0, 1, …).
- Chaque solution est notée par *notre modèle* (`problem.objective`) ; on vérifie qu'elle est faisable.
- Par cas et par méthode, on rapporte le *meilleur* score et la *médiane* sur les seeds, le gap de chacun et
  le temps moyen.
- *Gap* : $("score" - "meilleur connu") \/ |"meilleur connu"|$. Les meilleurs connus sont lus dans la table
  publiée par QOBLIB (128 cas, a010 et a050) et gardés en cache.
- *Sans meilleur connu (a200, a400)*, les graphes prennent comme référence le meilleur score trouvé par les
  méthodes comparées (cas marqués $dagger$). Le portefeuille vide ($-100 T$) sert de repère plancher.
- *L'arbitre officiel n'intervient qu'à la fin*, avec `--save-sol` : la meilleure solution de chaque cas est
  écrite en `.sol`, relue et notée par l'arbitre, puis enregistrée dans `results/portfolio/` (`save_run`).
  Si l'arbitre ne confirme pas notre score, le script s'arrête.

=== Les outils

#single_column_table(
  headers: ("Fichier", "Rôle"),
  content: (
    [`solvers/portfolio/benchmark.py`], [Grille et jeux de cas, meilleurs connus, registre des méthodes
      (`@register("nom")`), exécution, agrégation, CSV],
    [`solvers/portfolio/plots.py`], [Les graphes (PNG)],
    [`scripts/bench_portfolio.py`], [Lance un benchmark et écrit tous les résultats],
    [`scripts/plot_portfolio_bench.py`], [Retrace un run, ou superpose plusieurs runs pour les comparer],
  ),
  false,
  [Les fichiers du banc d'essai.],
)

Une méthode est une fonction `(problème, rng, limite de temps) → v` enregistrée avec `@register("nom")`.
Elle devient aussitôt utilisable par le script. Commandes types :

```bash
uv run scripts/bench_portfolio.py --set dev --methods empty ls --seeds 3 --time 10 --label essai
uv run scripts/bench_portfolio.py --set a400 --methods ls --save-sol      # validation + sauvegarde
uv run scripts/plot_portfolio_bench.py results/portfolio/bench/<run1> results/portfolio/bench/<run2> \
    --out results/portfolio/bench/compare --label "run1 vs run2"
```

Chaque run écrit dans `results/portfolio/bench/<date>_<label>/` : `runs.csv` (une ligne par exécution),
`summary.md` (tableau par cas et par méthode), `meta.json` (arguments, commit git, durée) et les graphes.

=== Les graphes

- `gap_by_case.png` : un cas par ligne, un point par méthode (meilleure seed). Le trait vertical marque le
  meilleur connu ; à gauche, le record est battu.
- `gap_vs_lambda.png` : un panneau par instance, le gap en fonction de $lambda$, une courbe par méthode.
  C'est là qu'on voit si une méthode tient quand le risque domine.
- `time_by_case.png` : le temps moyen par exécution, en échelle log.

Au-delà de 48 cas, chaque graphe est découpé par taille d'instance (`gap_by_case_a050_t10.png`, …). Les
méthodes reçoivent les couleurs d'une palette catégorielle validée pour le daltonisme, dans un ordre fixe,
et une forme de marqueur propre, pour que l'identité ne repose pas que sur la couleur. Les PNG ne sont pas
commités (on les régénère depuis `runs.csv`) ; ceux qu'on veut garder sont copiés dans
`formalisations/portfolio/figures/`.

=== Premier repère : le portefeuille vide

Lancé sur les 256 cas (`results/portfolio/bench/20261121T162856Z_baseline-empty/`, 2 minutes, surtout du
chargement de données). Ne rien détenir vaut $-100 T$, soit 97 % à 100 % de gap dans presque tous les cas.
Les exceptions sont les grands $lambda$, où le risque rend presque toutes les positions perdantes : avec
$lambda = 10^(-2)$, le portefeuille vide *est* le meilleur connu sur les 8 instances a010 (gap nul), mais il
en reste loin sur a050_t10 (gaps de 55 % à 98 %).

#figure(
  image("figures/baseline_empty_gap_vs_lambda_a010_t10.png", width: 100%),
  caption: [Portefeuille vide sur a010_t10 : gap en fonction de $lambda$. C'est le plancher que P4 doit
    faire descendre vers 0.],
)

== P4. Recherche locale rapide et mouvements par paires

On reprend la recherche locale du kit, accélérée par P2, et on lui ajoute des voisinages. Chaque nouveau
mouvement débloque une situation où le mouvement simple reste coincé.

#definition(title: "Recherche locale")[
  Partant d'une solution faisable $v$, on évalue tous les mouvements d'un *voisinage* $cal(N)(v)$, on
  applique celui qui diminue le plus le score officiel $f$, et on recommence. On s'arrête quand aucun
  mouvement n'améliore $f$ : la solution est alors un *optimum local* pour ce voisinage. Seuls les
  mouvements qui gardent la solution faisable (budget et capital) sont acceptés.
]

=== Les mouvements

#definition(title: "Mouvement simple")[
  Pour un jour $t$, une action $i$ et $s in {+1, -1}$ : $v_(t,i) arrow.r v_(t,i) + s$, avec
  $v_(t,i) + s in {-3, dots, 3}$. C'est le seul mouvement de la recherche locale du kit.
]

#definition(title: "Mouvement par bloc de jours")[
  Pour une action $i$, un intervalle de jours $[t_1, t_2]$ et $s in {+1, -1}$ :
  $v_(t,i) arrow.r v_(t,i) + s$ pour tout $t in [t_1, t_2]$.
]

*Pourquoi :* tenir une position un seul jour coûte des frais à l'entrée et à la sortie pour un seul jour de
gain, et n'est souvent pas rentable. Tenue sur plusieurs jours, elle ne paie ces frais qu'une fois. Le
mouvement simple ne peut pas voir ce gain, car il construit le bloc jour par jour et le premier pas est
perdant.

#definition(title: "Mouvement par paires")[
  Pour un jour $t$, deux actions $i != j$ et deux signes $s_i, s_j in {+1, -1}$ :
  $ v_(t,i) arrow.r v_(t,i) + s_i, quad v_(t,j) arrow.r v_(t,j) + s_j . $
]

Les quatre combinaisons de signes correspondent à deux familles de couvertures :

#single_column_table(
  headers: ([$s_i$], [$s_j$], [Position ajoutée], [Couverture si…]),
  content: (
    [$+1$], [$-1$], [long $i$, court $j$], [$i$ et $j$ corrélées],
    [$-1$], [$+1$], [court $i$, long $j$], [$i$ et $j$ corrélées],
    [$+1$], [$+1$], [long sur les deux], [$i$ et $j$ anti-corrélées],
    [$-1$], [$-1$], [court sur les deux], [$i$ et $j$ anti-corrélées],
  ),
  false,
  [Les quatre variantes du mouvement par paires. C'est un seul type de mouvement.],
)

*Pourquoi :* quand $lambda$ est grand, chaque moitié de la paire, prise seule, augmente trop le risque et
est refusée. Ensemble, les deux positions se compensent : le risque s'annule presque et il reste le gain sur
l'écart entre les deux actions. Le mouvement simple n'essaie jamais la paire. C'est la cause principale des
gaps de 56 % et 97 % du kit.

#definition(title: "Échange")[
  Pour un jour $t$, deux actions $i != j$ avec $v_(t,i) != 0$, et un signe $sigma in {+1, -1}$ :
  $ v_(t,i) arrow.r v_(t,i) - "sgn"(v_(t,i)), quad v_(t,j) arrow.r v_(t,j) + sigma, $
  avec $|v_(t,j) + sigma| = |v_(t,j)| + 1$. On retire une unité de $i$ et on ajoute une unité de $j$ : le
  nombre d'unités ouvertes $sum_i |v_(t,i)|$ ne change pas.
]

*Pourquoi :* quand le budget est saturé, ajouter une unité est interdit, et en retirer une d'abord dégrade le
score, donc est refusé. L'échange fait les deux d'un coup. C'est un cas particulier du mouvement par paires,
qu'on traite à part parce qu'il est le seul possible à budget plein.

=== Choisir les partenaires d'une paire

Tester toutes les paires coûte $O(n^2)$ par jour, soit 160 000 paires pour $n = 400$. On restreint les
partenaires de chaque action à ceux qui la couvrent le mieux.

#definition(title: "Covariance et corrélation")[
  L'instance fournit, pour chaque jour $t$, la covariance $"cov"_t (i, j)$ des rendements des actions $i$
  et $j$ (fichier `covariance_matrices.txt.gz`, chargé dans `instance.cov[i, j, t]`). La *corrélation*
  en est la version normalisée :
  $ rho_t (i, j) = ("cov"_t (i, j)) / sqrt("cov"_t (i, i) dot "cov"_t (j, j)) in [-1, 1] . $
  Si $rho$ est proche de $+1$, les deux actions montent et baissent ensemble ; proche de $-1$, l'une monte
  quand l'autre baisse ; proche de $0$, elles n'ont pas de lien.
]

#definition(title: "Matrice de risque")[
  C'est la matrice `model.risk[t]` de l'arbitre :
  $R_t (i, j) = "round"(lambda dot "cov"_t (i, j) dot P_(t,i) dot P_(t,j))$, où $P_(t,i)$ est la valeur
  d'une unité de $i$ au jour $t$. Le risque du jour $t$ vaut $v_t^top R_t v_t$. Dans les formules
  ci-dessous, $R_t$ désigne sa partie symétrique $(R_t + R_t^top) \/ 2$, qui donne le même risque.
]

#definition(title: "Coût de couverture")[
  Le risque propre d'une paire $(i, s_i)$, $(j, s_j)$ au jour $t$, c'est-à-dire le risque qu'elle aurait
  dans un portefeuille vide, vaut
  $ h_t (i, s_i, j, s_j) = R_t (i, i) + R_t (j, j) + 2 s_i s_j R_t (i, j) . $
  Plus il est petit, mieux la paire se couvre. Pour $s_i s_j = -1$ il est petit quand $i$ et $j$ sont
  corrélées ; pour $s_i s_j = +1$ il est petit quand elles sont anti-corrélées.
]

#definition(title: "Variation du risque pour un mouvement par paires")[
  Dans un portefeuille $v_t$ quelconque, le mouvement par paires change le risque du jour $t$ de
  $ Delta_"risque" = 2 s_i (R_t v_t)_i + 2 s_j (R_t v_t)_j + h_t (i, s_i, j, s_j) . $
  Les deux premiers termes décrivent l'interaction avec les positions déjà détenues ; le dernier est le
  risque propre de la paire. Avec $R_t v_t$ maintenu par l'évaluateur (P2), ce calcul est en $O(1)$.
]

#definition(title: "Listes de partenaires")[
  Pour chaque action $i$ (et chaque jour $t$, ou en moyenne sur la période), on précalcule une fois, au
  début :
  - $cal(C)(i)$ : les $k$ actions $j$ qui minimisent $h_t (i, +1, j, -1)$, soit les partenaires
    *corrélés*, à combiner avec des signes opposés ;
  - $cal(A)(i)$ : les $k$ actions $j$ qui minimisent $h_t (i, +1, j, +1)$, soit les partenaires
    *anti-corrélés*, à combiner avec le même signe.

  Le mouvement par paires ne teste que $j in cal(C)(i) union cal(A)(i)$. On prend $k$ entre 10 et 20.
]

#warnbox[
  - Les covariances changent d'un jour à l'autre : on testera des listes par jour et des listes moyennées sur
    la période.
  - Sur des actions réelles, les vraies anti-corrélations sont rares (tout suit plus ou moins le marché) :
    $cal(A)(i)$ sera probablement court. À vérifier sur les données.
]

== P5. Métaheuristiques en entiers

Pour sortir des optima locaux : recuit simulé et recherche tabou directement sur $v$, avec les voisinages de
P4 et l'évaluateur de P2, ainsi que des redémarrages multiples en parallèle. C'est la baseline forte contre
laquelle le quantique sera comparé.

== P6. Solveur exact sur les petites instances

Le problème entier est un programme quadratique en nombres entiers de taille modeste pour a010 (100
variables). Un solveur comme SCIP (`pyscipopt`, open source) pourrait :
- prouver l'optimalité, ou donner une borne inférieure, là où QOBLIB n'a qu'un « best known » ;
- éventuellement battre certains meilleurs connus ;
- nous dire si nos heuristiques sont proches de l'optimum.

#warnbox[
  La matrice de risque arrondie n'est pas exactement semi-définie positive sur a050 à a400 (valeur propre minimale de
  $-3$ à $-11$). Le problème n'est donc pas tout à fait convexe : il faut un solveur qui accepte le non
  convexe (SCIP le fait), ou une reformulation.
]

= Partie quantique

== P7. LNS quantique avec QUBO à signe fixé

*Principe (recherche à grand voisinage) :*
+ partir de la meilleure solution courante, issue du socle classique ;
+ choisir une *fenêtre* : quelques actions sur quelques jours ;
+ fixer tout le reste et écrire le sous-problème de la fenêtre comme un petit QUBO ;
+ le résoudre avec QAOA ou PCE via Divi, plusieurs fenêtres en parallèle dans le cloud ;
+ décoder, réparer si besoin, et accepter la fenêtre seulement si *le score officiel* s'améliore ;
+ recommencer.

*Encodage du sous-problème.* Mettre $v in {-3..3}$ directement dans un QUBO ne marche pas : si $v$ est
linéaire en bits, $|v|$ (budget, frais) ne l'est pas ; si $v$ est codé en signe $times$ magnitude, le risque
devient d'ordre 4. On *fixe donc le signe* $sigma_(t,i) in {+1, -1}$ de chaque case à l'avance (depuis la
solution courante ou le sens du cours), et on ne code que la quantité :
$ m_(t,i) = b_0 + 2 b_1 in {0, 1, 2, 3}, quad v_(t,i) = sigma_(t,i) dot m_(t,i) . $

- $v$ est linéaire en bits, donc le risque reste quadratique ;
- $|v| = m$ est linéaire, donc le budget, les frais d'achat et de liquidation et le coût du court le sont
  aussi ;
- frais entre deux jours : si les signes diffèrent, $|Delta v| = m_t + m_(t-1)$ est exact ; s'ils sont
  égaux, on remplace $|m_t - m_(t-1)|$ par $(m_t - m_(t-1))^2$, qui est exact pour un changement d'au plus 1.

*Coût :* 2 qubits par case au lieu de 6 plus les slacks, soit des fenêtres environ trois fois plus grandes à
nombre de qubits égal (12 qubits pour 6 cases, 30 qubits pour 15 cases).

*Comparaison honnête :* même LNS, mêmes fenêtres, avec comme sous-solveur une énumération exacte (petites
fenêtres) ou un recuit simulé. Le quantique n'a d'intérêt démontré que s'il fait au moins aussi bien.

== P8. Choix des fenêtres

La qualité du LNS dépend des fenêtres :
- *actions corrélées $times$ jours consécutifs*, pour trouver les paires couvertes quand $lambda$ est grand ;
- *cases « tendues »*, là où le budget ou le capital sont saturés ;
- *rotation aléatoire*, pour la diversité ;
- *alternance des signes* : re-tirer $sigma$ d'une itération à l'autre, ou autoriser quelques cases à 3
  valeurs ($-1, 0, +1$) pour pouvoir changer de sens.

== P9. Pénalités et Characterization Service

- Les contraintes de la fenêtre (budget et capital résiduels) entrent en pénalité au carré. Le poids est à
  régler : on balaie quelques valeurs, ou on suit le $lambda$ recommandé par le service.
- Le service peut aussi fixer des variables à l'avance, indiquer comment découper, et fournir des angles QAOA
  pour un démarrage à chaud. Comme il coûte des crédits, on l'utilise sur quelques fenêtres types, et on
  réutilise ses conseils.

== P10. PCE sur de grosses fenêtres

PCE encode beaucoup plus de variables que de qubits (environ $sqrt(2N)$ qubits pour $N$ variables avec
`PolyEncoding`). Avec le QUBO à 2 bits par case, une fenêtre de 100 cases (200 variables) tiendrait sur
environ 20 qubits. C'est la piste pour annoncer des sous-problèmes quantiques de grande taille.

= Ordre de travail

+ *P1 à P3 :* encodage, évaluateur et harnais. Sans eux, on ne peut rien mesurer à grande échelle.
+ *P4 :* première baseline sur tout le jeu de dev, et premières solutions a200/a400 à rendre.
+ *P7 et P8 :* LNS avec sous-solveur classique d'abord (pour valider la boucle), puis QAOA et PCE en local,
  puis dans le cloud.
+ *P5, P6, P9, P10 :* en parallèle selon le temps et les résultats.

#warnbox(title: "Règles qu'on se fixe")[
  - Le score qui compte est toujours celui de l'arbitre, jamais l'énergie d'un QUBO.
  - Tout résultat rendu est reproductible : `.sol`, méthode, paramètres, seed, hash git (`save_run`).
  - On met au point en local, et on ne passe au cloud qu'avec un pipeline validé : les crédits sont limités.
]
