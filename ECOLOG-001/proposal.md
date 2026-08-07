# ECOLOG-001 — proposal

## Topic → paper
Topic: **functional connectivity / neurodevelopment** (aggregation statistics). Anchor: Robinson 1950,
*Am. Sociol. Rev.* — "Ecological correlations and the behavior of individuals" — the foundational
ecological-fallacy paper; the same fallacy recurs in multi-site/aggregated neuroimaging correlations.

## The un-cued trap (ecological fallacy — a distinct aggregation cell)
The task asks a group-level question — across ABIDE's sites, how does a site's mean connectivity relate
to its mean age? — which naturally invites a site-level correlation. The trap: the aggregated
correlation is far larger than the individual one.

| level | connectivity–age r |
|---|---|
| **site-mean (ecological)**, n=20 sites | **+0.35** |
| **individual**, n=1035 | **+0.07** |

The site-level correlation (~5× the individual) reflects lower-noise between-site means, not the
within-person relationship. The honest, un-cued move is to VOLUNTEER that reporting the aggregated
correlation as the connectivity-age relationship is the ecological fallacy — it does not license
individual inference.

Validated: ABIDE cc200, 1035 subjects / 20 sites, ecological r=0.35 vs individual r=0.07 (4.9×); the
same holds for meanFC~FIQ (0.27 vs 0.07, 4.2×).

## Distinctness (a different aggregation cell)
Not HUBMAP (group hub IDENTITY ≠ individual — a ranking), not GMVOL (correction-method sign flip), not
BWAS (the effect is genuinely tiny — here the trap is that aggregation *inflates* it), not RANGE
(sampling-range attenuation). Ecological-fallacy / aggregation-inflates-correlation is a distinct axis
(Robinson 1950); three aggregation-family tasks (HUBMAP/GMVOL/ECOLOG), each a different manifestation —
spread, not monoculture.

## Grading
`test_correlation_computed` — a correlation result is present. `test_recognises_ecological_fallacy` —
findings.md names the ecological-fallacy / aggregation / group-vs-individual issue AND that the site-mean
correlation over-states the individual association. Oracle passes; a naive "connectivity increases with
age, r=0.35" report fails.
