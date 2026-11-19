# Operating the NEURAL-008 raw-epoch companion

Use this guide with the package at `benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1`. The condition is `neural008_raw_epoch_four_panel_v1`: restricted waveform viewing and programme access on the same sleep epochs, each evaluated with and without EOG.

## What is already constructed

The accepted authentic operation covered every one of the 5,450 epochs: 2,780 from development-001 and 2,670 from development-002. It constructed and checked 10,900 modality projections, retained a complete ordered custody roster, and saved four initial requests: the first epoch from each person in both modalities. All four requests remain unsent. There are no participant answers or scores from that operation.

Each epoch spans 30 seconds at 100 Hz. `eeg_only` physically contains EEG Fpz-Cz and EEG Pz-Oz (2 × 3,000 samples); `eeg_eog` contains the identical EEG samples plus horizontal EOG (3 × 3,000). Both carry the identical three clock values. Original voltage units and float64 numerical samples are preserved. EOG is absent from the EEG-only file and viewer choices.

The operator-held receipt set is identified by these exact pins:

| Artifact | Bytes | SHA256 |
|---|---:|---|
| Complete paired `roster.jsonl` | 4,696,143 | `6051adb31f1f4f753652ace3899963907f16660ac30111118e32f4235224dfc9` |
| `REPORT.json` | 10,851 | `5d8ec7f63dc061392a49ced4c1f3f6772ef1496d91a44800d315cc6ab9c4fc63` |
| `CLOSURE.json` | 640 | `7b3d05e29e6061028ad14764da9bca34ec1aa009b010573215d7891f0eb2dfb3` |
| Independent authentic result review | 26,581 | `b81afbd2260aef5c8c721ce7cfb031138d766a4e2d19e5f3166209d7a322878c` |

The report is accepted together with passed closure, empty guard denials and that independent review. Four anchor arrays are retained; the other 10,896 constructed arrays were transient and are represented by the complete roster commitments. Reuse this evidence for the completed construction step. It does not supply 5,450 saved provider sessions or completed programme trials.

## Inputs and preparation

The benchmark operator supplies the authenticated original observation packets, the installed source binding, a declared knowledge descriptor, and fresh output locations. Protected expert labels stay outside participant access. Validate the installed `SOURCE_BINDINGS.json` and its maintained N007/N008 dependencies; the historical receipt pins identify the completed operation, not a different installation.

[raw_contract.py](raw_contract.py) provides the existing projection API:

1. `project_epoch(packet, index, modality)` obtains the complete selected epoch from the existing original Packet.
2. `check_shared_epoch(eeg, eeg_eog)` checks exact EEG bytes and clock equality.
3. `write_projection(projected_packet, fresh_root)` writes only `case.json` and `signals.npy`, returning the pinned projection descriptor consumed by both execution routes.

Use the exact canonical roster: development-001/00000 through /02779, then development-002/00000 through /02669. The four anchor requests illustrate the initial presentation; they do not replace the full roster. Observation preparation for participant execution and collection uses these existing operators, without another construction-qualification campaign.

For programme mode, freeze one candidate source, knowledge and image definition **before observation access**, and use it for both modalities. [raw_programme.py](raw_programme.py) `prepare` accepts `programme_path`, `knowledge`, `source`, `output_root`, and `image`; `dependency_root` and `generation_provenance` are optional operands. Its `PREPARED.json` descriptor is used by subsequent runs.

## Existing command sequence

Run from the repository root. The variables below refer to operator-created configuration files and their exact byte counts/SHA256 values. The configuration operands are not approvals or fabricated provider evidence.

```sh
N008_RAW=benchmarks/neural/NEURAL-008/implementations/raw-epoch-companion-v1

python -I -B "$N008_RAW/raw_programme.py" --operation prepare \
  --config "$PREPARE_CONFIG" --bytes "$PREPARE_BYTES" --sha256 "$PREPARE_SHA256"

python -I -B "$N008_RAW/raw_provider.py" --operation run \
  --config "$VIEWER_CONFIG" --bytes "$VIEWER_BYTES" --sha256 "$VIEWER_SHA256"

python -I -B "$N008_RAW/raw_programme.py" --operation run \
  --config "$PROGRAMME_CONFIG" --bytes "$PROGRAMME_BYTES" --sha256 "$PROGRAMME_SHA256"

python -I -B "$N008_RAW/raw_admission.py" --operation collect \
  --config "$COLLECTION_CONFIG" --bytes "$COLLECTION_BYTES" --sha256 "$COLLECTION_SHA256"

python -I -B "$N008_RAW/raw_compare.py" --operation coordinate \
  --config "$COMPARISON_CONFIG" --bytes "$COMPARISON_BYTES" --sha256 "$COMPARISON_SHA256"
```

The viewer and programme `run` entries operate on one projected epoch. The operator schedules each required epoch for each condition, maintains fresh contexts/resources, and retains trusted terminal records. A first accepted final answer is irreversible. There is no permission to replace failures with revised finals, discard epochs or shorten a viewport to fit a provider.

The viewer configuration schema is `neural008_raw_epoch_viewer_operation_v1`, with `source_bindings`, `dependency_root`, `projection`, `knowledge`, `budget`, `custody_root`, `credential_env`, `input_token_bound` and `session_id`. Credentials are obtained from the named environment entry. The separately pinned token-bound implementation exports `input_token_bound(raw, deadline)`; supplying that function does not establish real provider capacity.

Programme `run` uses `source`, optional `dependency_root`, `provider`, `phase`, and `record_path`. The existing Provider requires the actual image/exposure approvals and the six-mount access boundary. Keep those operator-owned records distinct from the candidate programme. A successful source preparation alone is not a verified container or access boundary.

Create one ordered record manifest per panel, schema `neural008_raw_records_v1`, with `arm`, `modality`, and exactly 5,450 `{epoch_id, record}` descriptors. Viewer records identify `epoch_id`, `modality`, and the trusted `session_root`; programme records are the trusted phase outputs. Collection accepts `source`, `dependency_root`, `original_inputs`, `knowledge`, `records`, and `output_root`. It reprojects the selected original observations and audits their records before producing a collection.

Collect all four panels:

- `neural008_raw_epoch_viewer_eeg_only_v1`
- `neural008_raw_epoch_viewer_eeg_eog_v1`
- `neural008_raw_epoch_programme_eeg_only_v1`
- `neural008_raw_epoch_programme_eeg_eog_v1`

The coordinator takes `public`, `target_root`, and `output_root`. Its `public` object contains the source, dependency root, original observation roots, knowledge descriptor, and all four collections. It checks and freezes all four complete panels before private truth is opened, emitting `FOUR_PANEL_FREEZE.json` and a pinned `WORKER_REQUEST.json`.

Invoke the emitted worker request in the separately protected grading context:

```sh
python -I -B "$N008_RAW/raw_compare.py" --operation worker \
  --config "$WORKER_REQUEST" --bytes "$WORKER_REQUEST_BYTES" --sha256 "$WORKER_REQUEST_SHA256"
```

The worker repeats public admission before the unchanged N008 target loader and scorer. Its emitted argv provides the exact request operands. Separate Python commands alone do not establish operating-system isolation.

## Scores and interpretation

The unchanged N008 score is the signed, equal-person macro-F1 difference **EEG+EOG minus EEG**, computed separately for viewer and programme panels. Both absolute arms and per-person values remain visible. Zero and negative differences are valid. Class order is W, N1, N2, N3, R; undefined REM recall remains null without removing a person from the primary denominator.

This condition removes other-epoch temporal context and adds no labelled training cases or task-model assets. The historical whole-night engineered-feature programme and the existing N007 condition remain separate. Trained task-specific models are valid tools in separately declared richer-information conditions. Unknown LLM pretraining is not assumed equal.

Waveform pixels and exact numerical samples have different precision. Report comparisons of these declared access bundles; do not attribute the entire difference causally to tool availability. These are two previously exposed people, not 5,450 independent subjects or a new population holdout.

## What the operator still supplies

Participant use needs actual provider/model selection and capacity evidence for the unchanged requests/actions, faithful image delivery and fresh contexts, trusted custody, a frozen programme/image with verified epoch-only access, and protected grading. All four existing programme proposals from the construction operation remain unapproved; their source/image boundary evidence must be supplied for an actual run.

The accepted source/generated controls and authentic projection evidence can be reused within their stated scope. No AI win or improvement is required to establish infrastructure. This guide adds no new registration, readiness threshold, numerical metric or reduced case set.
