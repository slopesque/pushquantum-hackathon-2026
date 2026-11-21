// Boîtes et couleurs partagées par tous les documents du hackathon.
#let accent = rgb("#1F4E79")
#let soft = rgb("#F2F6FA")
#let warnfill = rgb("#FFF6E8")
#let warnstroke = rgb("#C77700")

#let keybox(title: none, body) = block(
  fill: soft,
  stroke: 0.6pt + accent,
  radius: 3pt,
  inset: 10pt,
  width: 100%,
)[
  #if title != none [#text(fill: accent, weight: "bold", title) \ ]
  #body
]

#let enbref(body) = keybox(title: "En bref", body)

#let warnbox(title: "Point de vigilance", body) = block(
  fill: warnfill,
  stroke: 0.6pt + warnstroke,
  radius: 3pt,
  inset: 10pt,
  width: 100%,
)[
  #text(fill: warnstroke, weight: "bold", title) \
  #body
]
