// Network part of the final presentation (~2 min 30 s), appended to the full deck by
// portfolio/slides.typ (`#include "/network/report/_network.typ"`), or compiled alone by
// network/report/slides.typ. Numbers: docs/network/synthesis.md and
// docs/network/hypothesis/*/result.md on branch network/main.
#import "_theme.typ": *

// ───────────────────────────────── Part 2 divider (~3 s)
#part-slide(
  "2",
  "QOBLIB 08 · Network design",
  [Teaching the QUBO \ what routing costs],
  [Physics-informed and learned surrogates, with PCE and constrained QAOA in Divi],
)

// ───────────────────────────────── 1. Problem (~35 s)
// Choose 2 out-links and 2 in-links per node, then route all the demand; the score is the load of the
// busiest link, given exactly by an LP in milliseconds. The kit's QUBO only rewards direct links.
#slide[Choose the links, then route: the kit's QUBO only sees direct links][
  #grid(
    columns: (1.1fr, 1fr),
    gutter: 1cm,
    [
      - $n$ nodes, traffic demand $t_(i j)$ between every pair.
      - *Topology:* exactly 2 out- and 2 in-links per node: one bit per possible link, *20 to 552
        binaries* (network05 to network24).
      - *Routing:* all demand flows over the chosen links. *Score:* load of the busiest link.

      #v(0.2cm)
      *The kit's surrogate* only rewards direct links:
      $ E_"kit" = - sum t_(i j) x_(i j) + lambda dot "degree penalties" $
    ],
    [
      #v(0.2cm)
      #grid(
        columns: (1fr, 1fr),
        row-gutter: 0.9cm,
        big("552", "binaries, network24"), big("≈ 6 ms", "one exact routing LP", color: grey),
        big("+9.35 %", "kit pipeline, network12", color: grey),
        big("+12.25 %", "kit pipeline, network24", color: grey),
      )
      #v(0.4cm)
      #box-key(color: warn)[*The gap:* a demand routed over 2 hops loads 2 links. The kit's QUBO
        ignores it; the LP referee does not.]
    ],
  )
]

// ───────────────────────────────── 2. Method (~40 s)
// Two levers: H2 adds routing physics (2-hop paths); H1 learns the score online from the LP in an
// active loop; H1 + H2 combines them. Quantum: PCE replaces SA in the loop; H4 tests a constrained QAOA.
#slide[Two ways to make the QUBO see routing][
  #set text(size: 15pt)
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.9cm,
    [
      #box-key(title: "H2 · Routing physics")[
        Also reward 2-hop paths $i -> j -> k$ for the demand $t_(i k)$:
        $ - beta_2 sum t_(i k) x_(i j) x_(j k) $
        Ranks topologies better than the kit (rank correlation *0.43* vs 0.31).
      ]
      #v(0.25cm)
      #box-key(title: "H1 · QUBO learned online (FMQA)")[
        A factorization machine fits the LP scores seen so far:
        #v(0.05cm)
        #align(center)[#step[QUBO]#arrow#step[SA]#arrow#step[repair]#arrow#step[LP]#arrow#step[re-fit]]
        #v(0.05cm)
        *H1 + H2:* the physics QUBO is the prior of the learned one.
      ]
    ],
    [
      #box-key(title: "Quantum variants", color: warn)[
        - *PCE* replaces SA in the H1 loop: *16 qubits* (network12, local), *33 qubits* (network24,
          Qoro cloud, MPS).
        - *H4:* QAOA with a Dicke state + XY mixer per node: out-degrees valid *by construction*
          (20 qubits, network05).
      ]
      #v(0.25cm)
      #box-key(title: "Fair comparison", color: good)[
        Same budget for everyone: *5 000 / 10 000 LP solves*, 3 seeds, median gap to the best known
        (classical parallel tempering). Every `.sol` is re-checked by the official referee.
      ]
    ],
  )
]

// ───────────────────────────────── 3. Results (~40 s)
// network12: the median gap drops from 9.35 % to 2.20 %, best run 1.15 %. network24: 12.25 % → 10.5 %,
// best run 8.86 %.
#slide[Results: at equal LP budget, both levers beat the kit][
  #grid(
    columns: (1.45fr, 1fr),
    gutter: 0.8cm,
    [
      #image("../figures/gap_medians.png", width: 100%)
      #text(size: 11pt, fill: grey)[Median gap to best known over 3 seeds (bars) and min–max (whiskers).]
    ],
    [
      #text(weight: "bold", fill: accent)[Submitted solutions]
      #v(0.1cm)
      #set text(size: 13pt)
      #table(
        columns: (auto, 1fr, auto, auto),
        align: (left, right, right, right),
        ..hdr[Instance][Score][Gap][Qubits],
        [network05], [65 500], [*0.00 %*], [20],
        [network12], [279 667], [*1.15 %*], [0],
        [network24], [722 459], [*8.86 %*], [0],
        [network24], [731 660], [10.24 %], [33],
      )
      #text(size: 11pt, fill: grey)[Kit best runs: +8.10 % (network12), +10.78 % (network24). network05:
        H4 QAOA; network12/24: H1 + H2; 33 qubits: H1 + PCE.]
      #v(0.2cm)
      #box-key(title: "Takeaway", color: good)[
        *Routing physics + online learning* divide the median gap by 4 on network12.
      ]
    ],
  )
]

// ───────────────────────────────── 4. Quantum, honestly (~40 s)
// PCE runs at 33 qubits for 1.34 credits, but never beats SA: the repair does the work. Constrained QAOA
// fixes out-degrees, not in-degrees. Our gains are classical.
#slide[The quantum part, measured honestly][
  #set text(size: 16pt)
  #grid(
    columns: (1.1fr, 1fr),
    gutter: 0.9cm,
    [
      Same H1 loop, only the sampler changes (network12, median of 3 seeds):
      #v(0.1cm)
      #table(
        columns: (1.4fr, 1fr, 1fr),
        align: (left, center, center),
        ..hdr[Sampler][Median gap][Qubits],
        [Simulated annealing], [*2.84 %*], [0],
        [PCE (PolyEncoding)], [4.68 %], [16],
      )
      #v(0.2cm)
      Constrained QAOA (H4, network05, 201 circuits):
      #v(0.1cm)
      #table(
        columns: (1.4fr, 1fr, 1fr),
        align: (left, center, center),
        ..hdr[Valid samples][Penalty QAOA][Dicke + XY],
        [Out-degrees], [13 %], [*100 %*],
        [Full topology], [4.2 %], [6.2 % (×1.5)],
      )
    ],
    [
      - PCE *scales*: network24 at *33 qubits* on the Qoro cloud, 731 660 (+10.24 %), for 1.34 credits.
      - But PCE samples are never valid before repair: *the repair does the work*.
      - Dicke + XY fixes out-degrees; *in-degrees* remain the bottleneck (target was ×10).
      #v(0.3cm)
      #box-key(color: warn)[Today our *best results are classical*; quantum brings scale, not yet
        quality. Next: PCE on the sparser H2 QUBO, a mixer preserving in-degrees too.]
    ],
  )
]
