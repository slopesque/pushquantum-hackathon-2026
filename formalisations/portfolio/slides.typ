// Slides de la présentation finale (Qoro × PushQuantum 2026), en anglais.
// Compiler : `just build portfolio` ou `just preview portfolio/slides.typ` depuis formalisations/.

#let accent = rgb("#14532D")
#let accent2 = rgb("#16A34A")
#let soft = rgb("#F0FDF4")
#let warn = rgb("#C77700")
#let good = rgb("#0F766E")
#let grey = rgb("#64748b")

#set page(
  paper: "presentation-16-9",
  margin: (x: 1.6cm, top: 2.4cm, bottom: 1.3cm),
  fill: white,
)
#set text(font: "Fira Sans", size: 17pt, lang: "en", fill: rgb("#111827"))
#set par(leading: 0.6em)
#set list(indent: 0.4em, spacing: 0.75em, marker: text(fill: accent, "▸"))
#set enum(indent: 0.4em, spacing: 0.75em)
#set table(stroke: 0.4pt + luma(210), inset: (x: 7pt, y: 5pt))
#show table.cell.where(y: 0): set text(fill: white, weight: "bold")
#show raw: set text(font: "Fira Mono", size: 0.9em)
#show math.equation: set text(font: "New Computer Modern Math")
#show strong: set text(fill: accent)


#let slide(title, body) = {
  pagebreak(weak: true)
  // Bandeau de titre
  place(top + left, dx: -1.6cm, dy: -2.4cm, block(
    width: 100% + 3.2cm,
    height: 1.75cm,
    fill: accent,
    inset: (x: 1.6cm),
    align(horizon, text(fill: white, size: 25pt, weight: "bold", title)),
  ))
  // Pied de page
  place(bottom + left, dy: 0.85cm, text(size: 10pt, fill: grey)[
    Qoro × PushQuantum Hackathon 2026 · Portfolio optimisation (QOBLIB 06)
  ])
  place(bottom + right, dy: 0.85cm, text(size: 10pt, fill: grey, context [
    #counter(page).display()
  ]))
  body
}

#let box-key(title: none, color: accent, body) = block(
  fill: color.lighten(90%),
  stroke: (left: 3pt + color),
  inset: 11pt,
  radius: 2pt,
  width: 100%,
)[
  #if title != none [#text(fill: color, weight: "bold", title) \ ]
  #body
]

#let big(n, label, color: accent) = align(center, stack(
  spacing: 6pt,
  text(size: 34pt, weight: "bold", fill: color, n),
  text(size: 13pt, fill: grey, label),
))

#let hdr(..cells) = cells.pos().map(c => table.cell(fill: accent, c))

// ───────────────────────────────── 0. Title (~10 s)
#page(margin: 0pt, fill: accent)[
  #set text(fill: white)
  #pad(x: 2cm, top: 4.5cm)[
    #text(size: 15pt, fill: accent2.lighten(50%), weight: "bold")[QOBLIB 06 · Multi-period portfolio optimisation]
    #v(0.3cm)
    #text(size: 38pt, weight: "bold")[Structure-guided partitioning \ for portfolio QUBOs]
    #v(0.5cm)
    #text(size: 17pt)[Exact window QUBOs, a large-neighbourhood search, and QAOA / PCE sub-programs with Divi]
    #v(1.6cm)
    #text(size: 14pt)[Clément Metz · Leith Chakroun · Ugo Col · Alexandre Baconnet · EPITA Quantum]
  ]
]

// ───────────────────────────────── 1. Problem + reformulation (~40 s)
#slide[Largest instance, no published result: reformulate first][
  #grid(
    columns: (1.1fr, 1fr),
    gutter: 1cm,
    [
      - $n$ assets × $T$ days, 0–3 units long or short, daily *budget* and *capital* limits.
      - Official QUBO: up to *36 165 binaries* (a400_t15). Best-known values stop at 50 assets: *nothing at 200 and 400*.

      #v(0.2cm)
      *Our reformulation.* Long and short on the same asset never pays:
      $ v_(t,i) = L_(t,i) - S_(t,i) in {-3, dots, +3} $
      Every term of the official score stays exact, and a move is re-scored in $O(1)$.
    ],
    [
      #v(0.2cm)
      #grid(
        columns: (1fr, 1fr),
        row-gutter: 0.9cm,
        big("36 165", "official QUBO bits", color: grey), big("6 000", "integer variables"),
        big("31 s", "12 000 moves, official checker", color: grey), big("0.2 ms", "12 000 moves, ours"),
      )
      #v(0.5cm)
      #box-key(color: warn)[*Size is not the difficulty:* at $lambda = 0$ even a400 is solved exactly in 0.4 s. The *risk term* is.]
    ],
  )
]

// ───────────────────────────────── 2. Method (~50 s)
// Schéma du LNS : grille actifs × jours. mode : "plain", "window" (fenêtre en vert, reste figé),
// "proposal" (fenêtre avec les cases modifiées en évidence).
#let fmt(x) = if x > 0 { "+" + str(x) } else if x < 0 { "−" + str(-x) } else { "0" }
#let lns-grid(vals, win: none, changed: (), mode: "plain") = {
  let days = vals.at(0).len()
  let names = ("A", "B", "C", "D")
  table(
    columns: (0.8cm,) + (1.2cm,) * days,
    rows: 0.95cm,
    align: center + horizon,
    stroke: 0.5pt + luma(200),
    inset: 0pt,
    table.cell(fill: none, stroke: none)[],
    ..range(days).map(d => table.cell(
      fill: if d == win { accent2 } else { luma(235) },
      text(size: 11pt, weight: "bold", fill: if d == win { white } else { grey }, "t" + str(d + 1)),
    )),
    ..range(vals.len()).map(i => {
      (table.cell(stroke: none, text(size: 12pt, weight: "bold", fill: grey, names.at(i))),)
      range(days).map(d => {
        let inwin = d == win
        let ch = inwin and changed.contains(i)
        table.cell(
          fill: if mode == "plain" { white } else if inwin { if ch { accent2.lighten(55%) } else { accent2.lighten(85%) } } else { luma(242) },
          stroke: if inwin { 1pt + accent2 } else { 0.5pt + luma(200) },
          text(
            size: 13pt,
            weight: if ch { "bold" } else { "regular" },
            fill: if mode != "plain" and not inwin { luma(170) } else if ch { accent } else { black },
            fmt(vals.at(i).at(d)),
          ),
        )
      })
    }).flatten(),
  )
}
#let cur = ((2, 2, 1, 0), (0, -1, -1, 0), (1, 1, 2, 2), (-1, 0, 0, 1))
#let prop = ((2, 3, 1, 0), (0, -2, -1, 0), (1, 0, 2, 2), (-1, 0, 0, 1))
#let panel(title, body) = align(center, stack(
  spacing: 0.25cm,
  text(size: 13pt, weight: "bold", fill: accent, title),
  body,
))
#let arrow = align(horizon + center, text(size: 26pt, fill: accent, "→"))
#let verdict(sym, color, title, body) = block(
  fill: color.lighten(88%),
  stroke: (left: 3pt + color),
  inset: 8pt,
  width: 100%,
)[#text(fill: color, weight: "bold")[#sym #title] \ #text(size: 12pt, body)]

#slide[Large-neighbourhood search: one window at a time][
  #grid(
    columns: (auto, auto, auto, auto, auto, auto, 1fr),
    column-gutter: 0.35cm,
    align: horizon,
    panel("① Current solution", lns-grid(cur)),
    arrow,
    panel("② Window: all assets, day t2", lns-grid(cur, win: 1, mode: "window")),
    arrow,
    panel("③ QAOA / PCE proposal", lns-grid(prop, win: 1, changed: (0, 1, 2), mode: "proposal")),
    arrow,
    stack(
      spacing: 0.2cm,
      text(size: 13pt, weight: "bold", fill: accent, "④ Official score"),
      verdict("✓", accent2, "Δ < 0: accept", [new current solution]),
      verdict("✗", rgb("#b91c1c"), "Δ ≥ 0: reject", [keep the old one]),
      text(size: 12pt, fill: grey, "↻ then next window"),
    ),
  )
  #v(0.15cm)
  #text(size: 12pt, fill: grey)[Cells: $v = L - S in {-3..+3}$ units of asset A–D on day $t$. Grey cells are *frozen*: only the green window is re-optimised, as a small QUBO.]
  #v(0.2cm)
  #set text(size: 14pt)
  #grid(
    columns: (1.15fr, 1fr),
    gutter: 0.9cm,
    [
      *Window QUBO, sign-fixed.* Keep each cell's sign $sigma$, encode only the quantity: $v = sigma (b_0 + 2 b_1)$. Risk stays quadratic, budget and costs linear: *2 bits per cell*, exact. Real windows: 50 assets × 2 days = *200 variables ≈ 20 PCE qubits*.
    ],
    box-key(title: "Why not partition the official QUBO?")[
      Budget and capital penalties couple every variable of a day: a generic decomposer cuts the constraints. We cut in the *problem space*.
    ],
  )
]

// ───────────────────────────────── 3. Results (~50 s)
#slide[Results: scale and quality, validated by the official checker][
  #grid(
    columns: (1fr, 1.2fr),
    gutter: 0.9cm,
    [
      #text(weight: "bold", fill: accent)[Scale · po_a400_t15 (36 165 variables)]
      #v(0.1cm)
      #grid(
        columns: (1fr, 1fr),
        big("8 / 8", "risk weights solved, feasible"), big("< 10 s", "per risk weight"),
      )
      #v(0.3cm)
      #box-key(title: "Quality check at λ = 0", color: good)[
        vs. exact MILP optimum: *0.005 % gap*.
      ]
    ],
    [
      #text(weight: "bold", fill: accent)[Quality · gap to best known (hard cases)]
      #v(0.1cm)
      #set text(size: 14pt)
      #table(
        columns: (auto, 1fr, 1fr),
        align: (left, right, right),
        ..hdr[Case][Local search][LNS],
        [a010 λ=1e-3], [4.86 %], [*0.00 %*],
        [a050 λ=5e-4], [1.91 %], [*1.04 %*],
        [a050 λ=1e-3], [8.31 %], [*2.03 %*],
        [a050 s01 λ=5e-4], [6.31 %], [*1.25 %*],
        [a050 s01 λ=1e-3], [27.9 %], [*2.73 %*],
        [a050 λ=1e-2], [97.3 %], [72.5 %],
      )
      #text(size: 11pt, fill: grey)[60 s per run, seed 0, reproduced identically on re-run. Small λ: 0 % with local search alone.]
    ],
  )
]

// ───────────────────────────────── 4. Quantum, honestly (~40 s)
#slide[The quantum part, measured honestly][
  #grid(
    columns: (1.1fr, 1fr),
    gutter: 0.9cm,
    [
      Same LNS, *same windows*, only the sub-solver changes (200-bit windows):
      #v(0.1cm)
      #table(
        columns: (1.3fr, 1fr, 1fr),
        align: (left, center, center),
        ..hdr[Sub-solver][Improving windows][Time / window],
        [Simulated annealing], [*8 / 12*], [0.2 s],
        [PCE, ≈ 20 qubits], [3 / 12], [3.6 s],
      )
    ],
    [
      #v(0.6cm)
      - PCE *does real work*: a010, λ = 1e-3, from 4.86 % to *0.60 %*.
      - Today, our *best results are classical*.
    ],
  )
  #v(0.2cm)
  #text(weight: "bold", fill: accent)[Submitted solutions]
  #v(0.1cm)
  #set text(size: 13pt)
  #table(
    columns: (1.6fr, auto, 1fr, 1fr, auto, 1.3fr),
    align: (left, right, right, right, right, left),
    ..hdr[Instance][Variables][Score][Best known][Gap][Method],
    [a400_t15_orig, λ = 0], [36 165], [−4 194 749], [MILP −4~194~965], [0.005 %], [`ls-full-b20`],
    [a400_t15_orig, λ = 1e-3], [36 165], [−2 797 435], [none], [n/a], [`ls-full-b20`],
    [a010_t10_orig, λ = 1e-3], [710], [−8 397], [−8 397], [*0.00 %*], [`lns-sa`],
    [a050_t10_orig, λ = 1e-3], [3 110], [−202 054], [−206 239], [2.03 %], [`lns-sa`],
    [a050_t10_s01, λ = 1e-3], [3 110], [−137 512], [−141 376], [2.73 %], [`lns-sa`],
  )
  #text(size: 11pt, fill: grey)[17 `.sol` files (8 × a400, 9 × LNS hard set), all re-scored by the official QOBLIB checker; method, parameters, seed and git hash stored with each run.]
]

// ───────────────────────────────── Network design (QOBLIB 08), ~2 min 30 s
#include "/network/report/_network.typ"
