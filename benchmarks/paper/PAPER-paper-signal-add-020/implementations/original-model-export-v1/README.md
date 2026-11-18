# Export the original conditional ERP models

This component bridges **already-produced** FRN, P3a and P3b R mixed models to
the existing numerical-summary contract for `PAPER-paper-signal-add-020`.
It does not fit a model, repeat preprocessing, score a submission or change the
task's scientific endpoint. The companion ERP and choice models are outside
this export's scope.

`export_models.R` reads trusted, already-present `lmerMod`/`lmerModLmerTest`
objects in an existing R session. It checks the source formula, actual REML
state, actual fixed and random design matrices, response, participant factor,
absence of weights/offsets, covariance axes and complete conditional support.
The three models must each retain 6,403 original rows and 41 participants.
It records optimizer settings, convergence messages, warnings and the runtime
present at export. It never calls `lmer`, `glmer`, `readRDS`, `load` or a fitter.
Existing `lme4` and `jsonlite` packages are required; it installs nothing.

The source's `model.frame` participant column can remain numeric while lme4's
actual grouping factor is categorical. Both native class/values and the fitted
group levels are retained. Native model-frame row names are preserved separately
and **never interpreted as original source row numbers**.

`finalize.py` checks the export against all ordered values and participant IDs in
the existing `processed-inputs-v1` CSVs. It checks their receipt, file hashes,
source pins and registered contract hash before emitting `summary.json` and
`provenance.json`. The summary contains only the exact existing ABI fields.
Provenance remains a separate file; keep the original native export as well.

## Use with already-produced objects

First prepare the eight exact public inputs using the existing
`processed-inputs-v1/prepare.py`. Keep its three CSVs and `receipt.json` together.
An operator must explicitly bind each existing fit's ordered observations to
those original source rows. Equality of ordered fitted-frame values is checked;
it is not evidence of when a model was fitted or independent ERP/trial linkage.

In the trusted R session containing the author's conditional objects:

```r
source("export_models.R")
fits <- list(FRN = fig3a_model, P3a = fig3b_model, P3b = fig3c_model)
# Supply independently tracked original-row bindings in each fit's actual order.
# Do not derive these from rownames(model.frame(fit)).
bindings <- list(FRN = frn_original_rows,
                 P3a = p3a_original_rows,
                 P3b = p3b_original_rows)
export_erp_models(fits, bindings, "/scratch/native-export.json")
```

Then, with a fresh output directory outside the repository and source inputs:

```sh
python3 -I -S -B finalize.py \
  --export /scratch/native-export.json \
  --prepared-dir /scratch/prepared-conditional \
  --contract ../registered-runtime/public_contract.json \
  --output-dir /scratch/conditional-summary \
  --accept-ordered-operator-binding
```

No input override weakens the production contract pin. Alternative estimators,
weights, offsets, random structures or companion designs require separate
adjudication; this exporter does not silently relabel them as original models.
The resulting summary can be submitted to the existing numerical scorer through
its existing interface. This component does not read its private reference.

## Contrast conventions

Both reports use **P3b valence coefficient minus reward coefficient**. The full
covariance report uses both off-diagonal covariance entries and a two-sided
normal tail. The historical report uses the sum of marginal coefficient
variances and a single normal tail. Neither is replaced by a `lmerTest` term
p-value. The exact public output contract defines these report fields; the
locally retained conditional source extract omits the original contrast lines.

## Qualification and limits

The maintained controls generate small artificial interchange objects. They
cover ordered row/frame identity, group support, term/covariance permutation,
weights/offsets/REML/design refusals, malformed covariance and numbers, source
receipt linkage, both contrast conventions, exact ABI boundaries and warning
retention. They do not construct R models or exercise native R methods.

The R exporter has received static review only. `Rscript` was not found on the
authoring host's PATH; no R syntax execution, native export, authentic-data run or
cross-language numerical parity is claimed. A later authorized qualification
must exercise it against already-produced objects in the registered runtime,
including intentionally altered objects and exact prepared-row binding.
The current package does not establish those objects' availability.

The unverified native interfaces are `stats::model.frame`/`vcov` dispatch on
`lmerModLmerTest`, `lme4::findbars`/`mkReTrms`/`getME` and sparse-matrix design
comparison, plus `jsonlite::write_json` serialization into the Python interchange.
Retained runtime records identify the historical registered Linux R image and
package versions; they do not establish current local image availability. No
Docker probe, startup, substitute host runtime or environment installation was
performed. Python interchange checks do not validate these R interfaces.

The retained public source extract and manifest identify the exact original
conditional code ranges. The full original Rmd is not authenticated locally in
this phase. An unnecessary planned source GET was canceled before execution.
Export-time versions do not establish original author or fit-time versions.
Prepared source authenticity depends on the existing preparer and its receipt;
this bridge does not independently reopen all eight original tables. Its JSON
and check flags are inspectable engineering artifacts, not execution attestation.

There is no new readiness designation, whole-paper reproduction result or
improvement claim. Larger coefficients or stronger significance do not define
better performance on this descriptive endpoint. Existing improvement
ineligibility remains unchanged.
