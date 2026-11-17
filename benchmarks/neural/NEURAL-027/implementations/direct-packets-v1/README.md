# NEURAL-027 direct numeric packets

This adapter supplies frozen single-query prompts and complete paired response collection for the existing visual-stimulus decoding endpoint. It emits two separate conditions: the four regional neural means, and the matched two movement/position values. Both conditions use identical queries, class order, training demonstration identities and scoring units. No decoder is fitted or invoked.

The implementation is an **engineering delivery component**. It does not launch a participant, enforce a no-tools context, authenticate original NPY conversion, or qualify an authentic neural-understanding result. Viewer, tool-assisted and frozen-program modes remain separate and are not delivered by this adapter. A response file can originate from a program; its score alone does not establish direct interpretation. The report explicitly retains this limitation.

The unchanged predecessor [evaluator](../initial-evaluator-v1/evaluator.py) constructs complete trial/position packets and supplies the original mouse-macro phase log loss, balanced accuracy and paired mouse bootstrap. Its SHA-256 is checked before import. [The existing scientific protocol](../../docs/initial-evaluator-v1.md) supplies source pins and unresolved native intake, cohort, phase, position-unit and regional-calibration limitations. No new source retrieval or authentic array preparation was performed for this component.

Supply the existing frozen source plan and safe NPZ exports. `demonstration-ids.json` must be a JSON array of predeclared original training packet IDs obtained from the operator's preparation. Selection never uses evaluation targets or scores. Nonempty demonstrations must include equal packet counts in every training mouse/class cell and retain every position bin of each selected trial. An empty array selects a separately labeled zero-demonstration condition. The choice and count must be scientifically frozen before participant outcomes; no convenient small cohort is chosen by this software.

An access-mode comparison must match training exposure: a program comparator for this fixed-demonstration condition must receive only the same selected training records. The predecessor's full-training reference is not automatically a matched comparison when demonstrations use a subset. This adapter compares the two direct observation conditions on identical demonstration and query identities; it does not run a program comparator.

```sh
python3 delivery.py build \
  --plan /operator/plan.json --session-dir /operator/safe-exports \
  --demonstration-ids /operator/demonstration-ids.json \
  --public-dir /exchange/n027-direct --private-dir /operator/n027-binding

python3 delivery.py prompt \
  --packet /exchange/n027-direct/neural.json --item-id PUBLIC_ITEM_ID

python3 delivery.py score \
  --public-dir /exchange/n027-direct \
  --private-binding /operator/n027-binding/binding.json \
  --neural-responses /operator/neural-responses.json \
  --movement-position-responses /operator/context-responses.json \
  --output /operator/n027-binding/report.json
```

Output directories must be new and disjoint. The public directory contains only `neural.json` and `movement_position.json`. Each contains the frozen instructions, canonical class order, allowed feature names, training example values/labels and opaque query IDs/values. No mouse, phase, original trial/session identity, query target, raw source filename, private key or extraction audit is exported. A private random 256-bit HMAC key re-identifies query packets and determines their order without encoding source order or target values. Reuse the frozen packet bytes for collection; rebuilding creates a new identity set.

The private binding retains original item identities, targets and mouse/phase groups, input hashes, plan hashes and public-packet hashes. Keep it and scoring reports outside participant access. Directory separation and restrictive creation permissions help prevent accidental mixing; they are not an operating-system isolation or participant-execution boundary. The whole public bundle is operator transport material: serve only one `prompt` result to each fresh participant context, with the same frozen demonstration context each time. Do not give the bundle to a supposed single-query direct participant. Run each condition without cross-condition memory. Keep zero-demonstration, fixed-demonstration and feedback experiments distinct; this implementation supplies no feedback protocol.

Responses are JSON arrays, one per observation condition. Every entry must contain exactly `item_id` and `probabilities`. Reject duplicate JSON keys, nonnumeric/bool values, nonfinite numbers, invalid simplexes, wrong class width and missing/duplicate/extra IDs. Both complete arms are required before paired scoring. Query order in responses may vary; identity matching restores the frozen population. No answer imputation, automatic retry or outcome-based case removal occurs. All public content, including demonstration targets, must match the frozen private hash. The scorer uses original biological mouse identity privately and never treats packets or dates as independent mice.

Python 3.11+ and the existing NumPy dependency are required. Generated controls exercise the safe-NPZ-to-prompt-to-score CLI, a numerical oracle, label noninterference, complete paired coverage, permitted observations, full-trial balanced demonstrations, prompt isolation and malformed input rejection. They establish software behavior only. Run the tests through the coordinated lightweight pool during the parallel construction wave; no model, fitting or authentic-data run is part of these controls.

Canonical task and access-mode metadata are unchanged. Integration may link this component as direct prompt/collector software; authentic direct transport and protected execution remain unestablished.
