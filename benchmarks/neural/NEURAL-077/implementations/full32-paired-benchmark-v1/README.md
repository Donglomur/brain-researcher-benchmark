# ERP CORE full32 paired benchmark source

This package contains an explicit-path packet builder, a per-query consumer and collector, and an offline paired evaluator for the 32-person, 6,400-event NEURAL-077 condition. It retains the existing four labeled demonstrations and both numeric conditions. The original 400-query condition remains unchanged.

The code is source preparation. Material authentication and generated controls do not establish a completed full32 packet, model performance, provider isolation, or scientific readiness. [STATUS.md](STATUS.md) records the verified material facts, historical sex-description correction and remaining scientific limits.

## Build a packet

The builder requires Python 3.11.6 and NumPy 1.26.3. It consumes original float32 FDT files and previously admitted metadata, rather than precomputed features. Supply a trusted input descriptor matching [inputs.schema.json](inputs.schema.json), its byte count and SHA-256, a metadata directory containing ALL32_METADATA_ADMISSION.json and sub-NNN.json files, and a flat FDT directory containing sub-NNN_task-P3_eeg.fdt files. The descriptor fixes all 32 participants, 200 events per participant, source metadata and full-file FDT identities. The builder verifies the supplied identities; it does not independently establish the provenance of an operator-supplied descriptor.

Supply the same original demonstrations.json, prompt.txt and response_schema.json as external pinned operands, plus an unpredictable private 32-byte key and its SHA-256. Keep the key, private targets and participant joins inaccessible to participants. None is bundled in this source package. The output directory must not exist.

```sh
python3 -B builder.py build \
  --inputs inputs.json --inputs-bytes INPUT_BYTES --inputs-sha256 INPUT_SHA256 \
  --metadata-root admitted-metadata --fdt-root fdt \
  --demonstrations demonstrations.json --prompt prompt.txt \
  --response-schema response_schema.json \
  --key private-key.bin --key-sha256 KEY_SHA256 \
  --output new-packet --work-seconds 1740 --whole-seconds 1800
```

The bundled recipe is pinned. It uses all 33 source channels, promotes P9/P10 to binary64 before their average reference, extracts Cz/Pz, and subtracts each channel's first 256-sample baseline. At 1,024 Hz, each epoch starts 256 samples before the released SET latency minus one and ends at offset 767. There is no added 26 ms shift, filter or trial rejection. The builder returns success only for a complete full32 output; an explicit incomplete result exits with status 2.

## Preserve the information available to the participant

Every query contains two complete channels of 1,024 binary64 values. A participant request includes that query and all four complete labeled demonstrations. Values use round-trip decimal serialization, including signed zero. Do not truncate the prompt, reduce waveforms to features, substitute demonstrations, or silently drop cases to fit a backend. Configure input capacity for the complete serialized request; token usage depends on the backend tokenizer.

The two conditions are numeric_direct_four_demo and numeric_program_four_demo. Their information is identical; only the permission sentence differs. Per-query projection exposes the opaque trial ID, condition, complete prompt and context hash. It excludes the staging manifest, participant roster, source times, grouping and private targets. The full staging packet is operator material, not the participant interface.

## Project and collect responses

Projection and collection use only the Python standard library. The generated controls were prepared for Python 3.11.6. Pin the public manifest's exact byte count and SHA-256 before requesting a context:

```sh
python3 -I -S -B evaluator.py project \
  --public-root new-packet/public --manifest-bytes MANIFEST_BYTES \
  --manifest-sha256 MANIFEST_SHA256 --trial-id OPAQUE_TRIAL_ID \
  --condition numeric_direct_four_demo

python3 -I -S -B consumer.py collect \
  --public-root new-packet/public --manifest-bytes MANIFEST_BYTES \
  --manifest-sha256 MANIFEST_SHA256 --condition numeric_direct_four_demo \
  --responses first-attempts.jsonl --output new-collection \
  --work-seconds 120 --whole-seconds 125
```

The collector preserves the first-attempt ledger, rejects missing/duplicate/invalid responses, and admits predictions only after all 6,400 unique responses succeed. A response must be strict JSON with exactly trial_id and target_probability; the probability must be finite, nonboolean and between zero and one. Collection is target-blind admission and produces no score.

The context UTF-8 ceiling is 262,144 bytes. The offline evaluator additionally requires each complete retained prompt frame to be at most 196,608 prompt bytes, and each first response at most 4,096 UTF-8 bytes. Configure the backend for the complete accepted text within these bounds. These limits are refusal thresholds, not permission to truncate. Framing uses a four-byte big-endian length followed by the exact original bytes.

## Evaluate a complete paired capture

The package provides an offline evaluator, not a participant arm executor. A trusted external producer must capture both complete arms under the same selected contract, including the frozen complete Python/config bundles, every original input and first response, and required closure attestations. The collector alone does not create these capture records. [CAPTURE_FORMAT.md](CAPTURE_FORMAT.md) specifies the required artifact layout and checks; [PAIR_CONTRACT_TEMPLATE.v1.json](PAIR_CONTRACT_TEMPLATE.v1.json) is deliberately unselected and has no actual study identities.

```sh
python3 -I -S -B evaluator.py freeze \
  --root participant-source --manifest participant-manifest.json --output frozen-participant.json

python3 -I -S -B evaluator.py evaluate \
  --contract selected-contract.json --contract-bytes CONTRACT_BYTES \
  --contract-sha256 CONTRACT_SHA256 --public-arms public-arms.json \
  --private-material private-material.json --output new-evaluation --work-seconds 120
```

Evaluation authenticates both complete public arms, frozen bundles, reconstructed client, inputs, first responses and closure records before opening even the private-material descriptor. Candidate declarations are compiled for integrity but never imported or executed by evaluation. Hashes and receipt consistency do not establish the truth of external capture attestations or provider isolation; the operator must supply trusted custody.

Scoring uses balanced accuracy at probability >= 0.5 and natural-log loss with metric-only clipping at 1e-15. It averages each metric equally across 32 participants, reports all paired participant differences, and uses direct-minus-program macro balanced accuracy as the primary contrast. It does not compute the planned paired-participant bootstrap, confidence intervals or reference-grade comparison.

## Generated source controls

The public tests use generated data and fixtures. They do not read original FDT or demonstration bodies or execute a participant model. Run the builder controls only in the required Python/NumPy environment; the consumer/evaluator controls require only the standard library:

```sh
python3 -I -B test_builder.py
python3 -I -S -B test_consumer_evaluator.py -v
```

These commands contain 10 builder methods and 18 consumer/evaluator methods. Their exact local qualification is recorded in SOURCE.json; the earlier private 76-method source preparation is not a public test count. Fresh hosted qualification and any actual scientific operation remain separate.
