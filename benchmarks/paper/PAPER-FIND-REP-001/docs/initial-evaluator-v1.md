# Initial evaluator: the Fig. 2f population-correlation endpoint

This package implements a complete, source-derived **Fig. 2f numerical endpoint on prepared place-field exports** for PAPER-FIND-REP-001. It calculates the 46 × 46 near/far population correlations, all six fixed region summaries, each animal's normalized learning curves, and the equal-animal mean and source SEM. It is not a whole-paper reproduction, native fluorescence pipeline, protected grader, or scientifically qualified benchmark. The canonical task and historical evidence are unchanged.

The scientific input is the author's `binF` record, not a submitted score or correlation matrix. The [pinned notebook](https://github.com/sprustonlab/OSM_Paper_Figures/blob/c1d1788b54c737efe24402e02762eee10da0d0d7/fig_2/Fig_2f.ipynb) supplies the numerical algorithm. The [paper](https://doi.org/10.1038/s41586-024-08548-w) supplies the biological context and native processing obligations. Native dependencies and archive acquisition are intentionally outside this construction work. No authentic observations, model attempts, native notebook executions, or scientific results were produced.

## Source-defined computation

For each of the eleven recorded Set A animals (`Tyche-A4`, `A5`, `A7`, `B2`, `B3`, `B4`, `B5`, `C1`, `D1`, `F1`, `F5`, all with the `Tyche-` prefix), use the initial consecutive sessions whose unique cue-set list contains only `Cue Set A`. Stop at the first other or mixed cue session; later Set A sessions are not reintroduced. Native records are `Cue Set A/{1,2}/excl_no_response/{session}/putative`, with trial type 1 supplied as `near_binF` and trial type 2 as `far_binF`, each cells × 46. The evaluator requires identical ordered registered cell identifiers across the selected sessions. This is a conservative prepared-export admission condition; it does not establish that native registration or cell selection is correct.

Pearson correlation is taken **across cells**, with near bins as rows and far bins as columns. The six masks, in output order, are:

| Endpoint | Exact zero-based, half-open mask | Entries |
|---|---|---:|
| Off diagonal | All ordered cross-region pairs among `[0,12)`, `[20,26)`, `[30,36)`, `[40,46)` | 648 |
| Pre-R2 | `[34,37)` × `[34,37)` | 9 |
| Pre-R1 | `[24,27)` × `[24,27)` | 9 |
| Initial | `[0,12)` × `[0,12)` | 144 |
| Indicator | `[17,20)` × `[17,20)` | 9 |
| End | `[40,46)` × `[40,46)` | 36 |

The notebook's intermediate labels `Post R1` and `Post Ind` differ from final plot labels `Pre-R2` and `Pre-R1`; the exact index masks govern this implementation. Every selected matrix entry contributes to the arithmetic region mean; there is no Fisher transform, diagonal-only restriction, cell weighting, or pooling of animals.

Source behavior for undefined correlations is preserved: constant vectors or NaNs yield NaN coefficients; a NaN in a selected region propagates to its day mean. For each region and animal, NaN days are removed **before** the remaining observations are evenly placed on `[0,1]` and interpolated onto 1,000 endpoint-inclusive points. Missing interior day gaps are therefore compressed, exactly as in the source, and valid day counts are reported. Fewer than two valid observations produce an explicitly undefined curve; that animal remains in group arithmetic, so the group result is undefined for that region. JSON encodes undefined values as `null`. Infinity is rejected. No undefined result is substituted with zero.

Group curves use equal animal weights and `std(ddof=0)/sqrt(11)`, matching the notebook. This is the source's descriptive SEM, not a new confidence interval or generalization test. The notebook's 20-session plotting buffer is not a scientific inclusion criterion; the evaluator does not truncate declared sessions to that buffer. This endpoint tracks within-day near/far correlations across learning; it does not compute direct day-to-day PV stability or fit state versus continuous-position models.

## Prepared-export interface and execution

Use an existing Python environment with NumPy; construction tests used Python 3.11 and NumPy 2.4.6. No installation is required by this package. From this implementation directory:

```sh
python3 evaluator.py /absolute/path/to/manifest.json /absolute/path/to/new-report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Output is created exclusively and never overwrites an existing file. Each selected session uses a local NPZ with exactly `near_binF`, `far_binF` (numeric cells × 46), and `cell_ids` (unique Unicode strings or signed integers). Object arrays and pickle loading are forbidden. Near and far must share their cell ordering; the single `cell_ids` array binds both. At least two cells are required. Files are SHA256-checked and must remain within the manifest directory. The evaluator streams one session export at a time; native-scale resource use has not been measured.

The strict JSON manifest contains:

```json
{
  "schema_version": 1,
  "task_id": "PAPER-FIND-REP-001",
  "source_revision": "c1d1788b54c737efe24402e02762eee10da0d0d7",
  "input_kind": "prepared_putative_placefields_binF",
  "evidence_kind": "empirical_unqualified_export",
  "lineage": {
    "article_id": 27273552,
    "article_version": 1,
    "placefields_record": "identified native placefields asset and digest",
    "registered_fluorescence_record": "identified registered input and digest",
    "behavior_record": "identified complete trial/session metadata and digest",
    "export_procedure": "versioned export procedure and review evidence",
    "rights_review": "separate data/dependency rights review evidence"
  },
  "animals": [
    {
      "animal_id": "Tyche-A4",
      "native_session_count": 3,
      "sessions": [
        {"session_index": 0, "cue_sets": ["Cue Set A"], "behavior_record": "native record locator", "selection": "putative/excl_no_response", "arrays": "A4/day0.npz", "sha256": "64 lowercase hexadecimal characters"},
        {"session_index": 1, "cue_sets": ["Cue Set A"], "behavior_record": "native record locator", "selection": "putative/excl_no_response", "arrays": "A4/day1.npz", "sha256": "64 lowercase hexadecimal characters"},
        {"session_index": 2, "cue_sets": ["Cue Set B"], "behavior_record": "native record locator"}
      ]
    }
  ]
}
```

This abbreviated format illustration is deliberately not a runnable empirical manifest: all eleven animals, each animal's entire contiguous native session ledger, and real file pins are required. `native_session_count=3` is illustrative, not a historical day count. The notebook does not freeze those counts. Structural coverage checks cannot prove an operator-supplied ledger complete. The report therefore retains independent full-population and export-lineage verification holds even after all input checks pass. `generated_engineering_control` is the other permitted evidence kind; tests generate all eleven labels without claiming that they are observations of those animals.

## Provenance, reuse, validation, and retained gates

`provenance.json` binds the immutable task, source revision, fetched notebook/README/license bytes, algorithm mapping, and scope. This is newly authored evaluator code derived from the published algorithm; the upstream BSD-3-Clause notice is retained in `UPSTREAM_LICENSE.txt`. The license resolves the pinned figure-code reuse question only. Dataset CC BY 4.0 recorded in the canonical task, dependency licenses, model exposure, and candidate packet rights remain separate. No upstream notebook images or empirical arrays are redistributed.

Independent tests derive mask geometry, Pearson orientation, exact rational region means, interpolation, animal averaging and SEM; interface controls exercise the full eleven-label path, source-session stopping, missing animals/sessions, changed pins, unsafe arrays, registration order, and undefined values. These tests establish engineering behavior only.

The preserved gates are: authentic native `vr2p`/Zarr-to-NPZ equivalence; matched behavior and source processing (including mean fluorescence in 5-cm bins for running speed strictly greater than 5 cm/s); original multiday cell eligibility and registration; independently evidenced full animal/session population; native environment/dependency qualification; authentic executable reference and independently audited protected numeric targets/tolerances; complete-paper stability and state/spatial-model comparison; animal-held-out improvement/generalization; empirical compute envelope; and remaining rights/exposure checks. The 3.9-GB stretched-trial subset cannot discharge these longitudinal requirements. No binary reward or admission change is registered.
