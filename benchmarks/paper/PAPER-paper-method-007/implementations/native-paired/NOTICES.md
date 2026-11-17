# Attribution and retained terms

The upstream UnitMatch project is
[EnnyvanBeest/UnitMatch](https://github.com/EnnyvanBeest/UnitMatch). Its recorded
README credits Enny H. van Beest for the initial MATLAB toolbox, Célian Bimbard
for optimization, and Sam Dodgson for the Python implementation. The original
publication link in that source is the
[UnitMatch preprint](https://www.biorxiv.org/content/10.1101/2023.10.12.562040v1).
These attributions and links come from the retained upstream source; they are not
a claim of a fresh website or publication-version verification.

The exact upstream [CC BY-NC-SA 4.0 license text](notices/UnitMatch_LICENSE_CC_BY_NC_SA_4.0.txt)
is retained. Upstream-derived MATLAB setup/call portions in `native_baseline.m`
and `unitmatch_native_capture.m` retain the applicable attribution,
noncommercial and share-alike terms. The capture adapter adds product capture
and identity checks; it does not claim authorship of the original UnitMatch
method. The new public package changes only configuration defaults, source-pin
metadata and documentation, not scientific function bodies.

The upstream nested `MATLAB/DataPreparation/zmat_Toolbox/` has a separate
[GNU GPL version 3 notice](notices/zmat_LICENSE_GPL_v3.txt). The full nested
implementation and full official native tree are external, not bundled here.
Retaining its notice does not blanket-relicense benchmark Python, settle license
compatibility for a future native distribution, or waive those nested terms.

The [project MIT notice](notices/PROJECT_LICENSE.txt) applies to original project
contributions where applicable. It does not supersede the upstream-derived or
nested third-party terms. Historical source documentation records separate
CC BY 4.0 dataset terms; this package includes no dataset and does not establish
new data rights. MATLAB and its toolboxes retain their own licensing requirements.
No notice or source-check result grants rights to otherwise excluded code,
models, data or native environments.
