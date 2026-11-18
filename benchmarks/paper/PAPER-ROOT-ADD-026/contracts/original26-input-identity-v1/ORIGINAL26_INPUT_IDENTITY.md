# Original 26-electrode input identities

`ORIGINAL26_INPUT_IDENTITY.json` is the identity inventory for the 26 original category-selective `data.txt` response exports. A successful manifest records all 26 source objects without copying their contents into the repository. It is not a benchmark result or an inventory of every input required by the downstream biological figures.

The selection follows the authenticated `electrodes_categorySelective_0-5.txt` roster, preserves its row order, and removes electrodes whose stored preferred category is `SCRAMBLED`. This filter applies to electrode membership. Each response export still retains all 72 conditions, including the SCRAMBLED stimulus category, and 819 response samples per condition.

The provenance is deliberately explicit:

- `verification_scope: fresh_local_body_and_template` identifies the three reusable local exports whose extent, category-pointer MD5, recorded SHA256, and expected source format were checked during assembly.
- `verification_scope: prior_authenticated_body_and_template_not_reread` identifies the 22 separately acquired original category exports and G03. Their accepted independent identity and format evidence is joined into the manifest; assembly does not reread those 23 bodies or claim their current files cannot change.

Each entry binds its original electrode selection, category annex identity, observed content hashes, and verification scope. The public manifest omits private filesystem locations and response values. A later consumer must authenticate the actual bytes it loads against these pins; a historical verification receipt does not make a mutable file immutable.

The source-format check preserves empty fields, NaN, and infinities as separate cases. It does not impose an all-finite criterion, repair values, discard conditions, or substitute a smaller cohort. Format compatibility does not establish publication preprocessing parity.

This inventory adds input-identity evidence to `../../primary-endpoint-v1/source-resolution-join.v1.json`. It leaves that earlier source record and its historical observations intact. The original 26-electrode category-selectivity and mechanism questions remain distinct from the original 79-electrode response-prediction assay. The corrected named-response prospective assay, literal positional replay, and published historical scores retain their separate attribution.

The stored roster does not establish the historical selection producer. Retained Figure 8 configuration differences, Figure 9 model variants, epoch-level preference and exclusion processing, downstream figure recipes, historical folds, and participant isolation remain separately qualified. Complete support in this inventory does not establish reproduction, improvement, SOTA performance, or benchmark readiness.
