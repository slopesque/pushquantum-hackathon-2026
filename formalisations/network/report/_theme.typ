// Theme of the final presentation (copied from portfolio/slides.typ, the mandatory template), so that
// the network slides look the same whether they are compiled alone or appended to the full deck.
// Only the footer label differs. Keep in sync with portfolio/slides.typ if the template changes.

#let accent = rgb("#14532D")
#let accent2 = rgb("#16A34A")
#let soft = rgb("#F0FDF4")
#let warn = rgb("#C77700")
#let good = rgb("#0F766E")
#let grey = rgb("#64748b")

// Global rules of the template, for the standalone build only (`network/report/slides.typ`).
// In the full deck they come from portfolio/slides.typ.
#let deck(body) = {
  set page(
    paper: "presentation-16-9",
    margin: (x: 1.6cm, top: 2.4cm, bottom: 1.3cm),
    fill: white,
  )
  set text(font: "Fira Sans", size: 17pt, lang: "en", fill: rgb("#111827"))
  set par(leading: 0.6em)
  set list(indent: 0.4em, spacing: 0.75em, marker: text(fill: accent, "▸"))
  set enum(indent: 0.4em, spacing: 0.75em)
  set table(stroke: 0.4pt + luma(210), inset: (x: 7pt, y: 5pt))
  show table.cell.where(y: 0): set text(fill: white, weight: "bold")
  show raw: set text(font: "Fira Mono", size: 0.9em)
  show math.equation: set text(font: "New Computer Modern Math")
  show strong: set text(fill: accent)
  body
}

#let slide(title, body) = {
  pagebreak(weak: true)
  // Title banner
  place(top + left, dx: -1.6cm, dy: -2.4cm, block(
    width: 100% + 3.2cm,
    height: 1.75cm,
    fill: accent,
    inset: (x: 1.6cm),
    align(horizon, text(fill: white, size: 25pt, weight: "bold", title)),
  ))
  // Footer
  place(bottom + left, dy: 0.85cm, text(size: 10pt, fill: grey)[
    Qoro × PushQuantum Hackathon 2026 · Network design (QOBLIB 08)
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

// Part divider (copy of portfolio/slides.typ: keep in sync).
#let part-slide(num, kicker, title, subtitle) = page(margin: 0pt, fill: accent)[
  #set text(fill: white)
  #pad(x: 2cm, top: 4.2cm)[
    #text(size: 14pt, fill: accent2.lighten(50%), weight: "bold", tracking: 1pt)[PART #num OF 2 · #kicker]
    #v(0.3cm)
    #text(size: 36pt, weight: "bold", title)
    #v(0.5cm)
    #text(size: 17pt, subtitle)
  ]
]

#let hdr(..cells) = cells.pos().map(c => table.cell(fill: accent, c))

// Box of a "step → step" chain.
#let step(body) = box(
  fill: accent2.lighten(85%),
  stroke: 0.8pt + accent2,
  radius: 2pt,
  inset: (x: 7pt, y: 5pt),
  text(size: 14pt, body),
)
#let arrow = text(size: 18pt, fill: accent, " → ")
