# Dendritic morphology scorer prototype

**NOT READY for authentic benchmark evaluation.** This package specifies frontal-versus-parietal morphology prediction within each species, and provides a scorer plus invented controls. It does not implement the paper's historical reproduction pipeline, prepare authentic features, verify donor identities, fit references or isolate candidate execution.

The scorer requires a complete 2,363-human/16,011-mouse source accounting and source-supported biological groups. These are published metadata expectations, not an admitted payload census. Its primary metric averages donor/animal class recalls within species before averaging species. The official neuron-level validation recipe and prospective held-group improvement remain distinct.

From this directory, run `python3 -B -m unittest -v test_score_lobes`. A future evaluator CLI is `python3 -I -S -B score_lobes.py MANIFEST.json PREDICTIONS.json --frozen-reference REFERENCES.json`. Placeholders are not supplied inputs. The optional reference argument permits raw descriptive scoring; an improvement claim still requires all competent references and independent verification in CONTRACT.md.

Authentic cohort/group mapping, all feature transformations, dataset reuse terms, nested references, uncertainty and protected execution remain open. Code licensing does not grant data rights. No paper, official code, authentic labels or morphology archive is redistributed.
