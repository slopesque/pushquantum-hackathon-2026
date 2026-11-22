// Network slides compiled alone (same template as the full deck).
// The full deck is portfolio/slides.typ, which appends `_network.typ` at its end.
// Compile: `just network-report` (alone) or `just build portfolio` (full deck), from formalisations/.
#import "_theme.typ": deck

#show: deck
#include "_network.typ"
