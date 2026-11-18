# UMBRAE source-grammar raw-response importer

This operator component converts structured model-response text into the exact nested box format consumed by the existing UMBRAE grounding scorer. It addresses the missing raw-text extraction seam; the task's source, execution and scientific-readiness holds remain unchanged.

The inspected [author inference](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/inference_rec.py) calls `extract_boxes` on each decoded response. The pinned [parser](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/utils.py) recognizes bracketed groups of four comma-separated numbers, with semicolons separating boxes. Each number has a single decimal digit before an optional decimal fraction. Spaces, signs, exponents and multi-digit integer parts are not accepted. Groups and boxes retain encounter order. This implementation follows that lexical language without cleaning or repairing responses.

The [author scorer](https://raw.githubusercontent.com/weihaox/BrainHub/4838666f1a04d0521c2184fa50b5b77e7e7ac5ee/eval_bbox_rec.py) consumes the first box of the first extracted group. The reviewed local scorer additionally rejects invalid normalized geometry. Consequently `[9,0,1,1;0,0,1,1]` retains its invalid first box; the later valid box is not substituted. A formatted answer such as `[0, 0, 1, 1]` produces empty extraction rather than receiving extra parser capability. Native author-parser execution and author-versus-corrected-scorer numerical parity have not been run.

## Inputs and outputs

`--query-roster` is an operator-owned JSON object from contiguous image-index strings to complete category-name lists. Empty-query images remain included. Its membership and original image/annotation join require independent authentication; cardinality checks cannot supply it. The importer does not read reference coordinates.

`--raw-panel` contains exactly:

```json
{
  "schema": "umbrae-keyed-raw-panel/v1",
  "task_id": "PAPER-paper-method-042",
  "profile": "paper_population",
  "query_roster_sha256": "SHA256_OF_CANONICAL_ROSTER_VALUE",
  "responses": {
    "candidate": {},
    "official_baseline": {},
    "neural_free": {},
    "shuffled_neural": {}
  }
}
```

Each role must contain exactly `S1`, `S2`, `S5`, and `S7`; each subject must contain every image and query from the roster. Each query holds decoded text or explicit JSON `null` for a missing answer. Missing keys reject the entire packet. An explicit null and an empty extraction remain failures under the existing scorer without changing the denominator. The `paper_population` profile requires 982 images; `engineering_controls` permits small generated populations. Neither profile establishes native authenticity or a verified query count.

The roster commitment uses `canonical_sha256`: UTF-8 JSON with sorted object keys, compact separators, literal Unicode and no NaN. The CLI also records exact input-file byte identities separately. The packet is a prospective structured capture ABI, not the author's saved append-log format. It deliberately does not reconstruct keys from `rec_response.txt`: multiline responses and marker-like generated text make such reconstruction ambiguous.

Run from this directory with Python 3.10+ and the standard library:

```sh
python3 raw_response.py --raw-panel RAW.json --query-roster QUERIES.json --output-directory NEW_DIRECTORY
```

The new directory receives sixteen `<role>-<subject>.json` files compatible with the existing scorer's response paths, plus `conversion.json` containing hashes and extraction diagnostics. `--compare-extracted-panel EXISTING.json` optionally compares every supplied arm/subject/query against a separately captured extracted panel, without attesting its producer. Comparison is exact canonical-JSON value identity, including numeric representation. The importer never changes the existing scoring contract automatically.

Each raw response is limited to 65,536 UTF-8 bytes and each input file to 256 MiB. These are explicit engineering refusals, not paper limits or measured runtime envelopes. The input JSON and converted panel are materialized in memory; production memory/compute admission is absent. Existing output directories are refused. Partial files may remain after an I/O failure; consumers must require a valid final manifest, all output hashes and an independently observed successful operator termination. A manifest or raw-text hash alone cannot prove that fMRI generated a response.

## Verification and remaining scope

Generated controls cover the restrictive lexical grammar, multiple groups/boxes, Unicode decimal digits, invalid first boxes, complete sixteen-stream membership, explicit missingness, original scorer denominator preservation, empty-query images, all 982 generated image IDs, comparison disagreements, input-byte pins, duplicate/nonfinite JSON, CLI output pins and overwrite refusal. Run `python3 -m unittest discover -s tests -v` through the project's existing coordinated two-slot test pool.

The local dependency hash is checked before importing the existing grounding scorer. Primary pages were inspected through the web tool; the author module was not downloaded or executed, and its raw bytes were not locally authenticated. No NSD arrays, annotations, image tensors, checkpoints, model calls, training, inference or scientific scoring occurred. Query provenance, checkpoint/preprocessing lineage, exposure equivalence, protected execution, native parity, complete numerical reproduction and a justified improvement decision remain unresolved. This component does not add a benchmark or promote readiness.
