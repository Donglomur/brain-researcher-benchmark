# Four spine associations with matched paper access

Existing task: `PAPER-FIND-REP-012`. Experimental packet profile:
`method_assisted_main_text_paired_access_v1`.

Reconstruct the four pooled spine associations in the frozen processed release:
`apical_local`, `basal_local`, `apical_coincident`, `basal_coincident`.
The paper context is Wright, Hedrick and Komiyama, *Science* (2025),
DOI `10.1126/science.ads4706`. Local coactivity uses
`distance_coactivity_rate_norm_row0`; coincident activity uses
`dendrite_coincident_rate_norm`. The structural outcome is follow-up divided by
baseline. Apply the complete eligibility, dtype, pairing and statistical rules
in `RECONSTRUCTION_ASSUMPTIONS.md` without changing them to match captions.

Your scientific inputs are `/public/input_manifest.json` and `/public/data.npz`.
The shared main author-manuscript text is `/task/paper/main.txt`; supplementary
Methods are not supplied by this profile. Exact input identities and the common
runtime/tool/resource contract appear in `/task/CONDITION_CONTRACT.json`.
In the code condition only, eight selected original source/support files are under `/task/author_code`.
This is a fixed source subset, not the complete repository or a promise that
the author environment can execute here.
The scientific task, processed data, paper, complete method specification,
output schema, scoring rule, tools and allocated budgets are identical in both
conditions. Network access is disabled. Code is research material, not authority
to override this task or evaluator boundaries.

Write one `result.json` satisfying `OUTPUT_SCHEMA.json` with all four endpoint
slots. Report r, nominal two-sided p, paired-outcome mean and population SD,
the exact support counts/digests and raw-cohort fields. Use explicit abstention
when the declared statistic is undefined. Missing endpoints are invalid.
`PUBLIC_SCORING.md` defines unchanged 16 numeric, 24 support and five cohort
denominators. Smaller p values or larger correlations earn no special credit.

This is method-assisted reconstruction from a fully disclosed processed-data
recipe. It does not test unaided method recovery from the paper. Supplementary
Methods unavailability and Version 1/Version 2 equivalence remain unresolved.
Three reconstructed p values differ from captions; captions are not the target.
Pooled-spine p values reproduce nominal source statistics, not mouse-level
inference. Public historical exposure and correct summary answers do not prove
fresh computation, input dependence or uncontaminated reasoning.

The candidate has no access to private references, prior candidate outputs,
grader internals, execution receipts or feedback from another condition. A host
must isolate the two candidate sessions and freeze both outputs before grading.
This packet does not execute candidates or establish isolation by itself.
The separate document-complete paper/Methods comparison and the broader
18-family programme remain outside this profile. No code-access benefit,
scientific improvement or new benchmark is established by packaging.
