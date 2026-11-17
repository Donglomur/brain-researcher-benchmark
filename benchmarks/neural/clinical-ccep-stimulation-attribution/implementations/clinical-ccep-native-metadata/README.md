# Clinical CCEP native metadata preparation

This source component prepares and checks **operator-private metadata** for the existing five-recording clinical CCEP benchmark. It preserves complete declared channel, segment and block-index inventories, exact integer identities, unit declarations and missing-value diagnostics. It does not load neural waveforms or produce predictions, targets or a scientific benchmark result.

The [primary scorer](../clinical-ccep-artifact-grading/README.md) and [paired controls](../clinical-ccep-pairing/README.md) remain separate. This component adds no task, participant or qualified benchmark. Authentic native metadata, its channel correspondence and a faithful waveform converter are still required.

## Inputs and commands

`ccep_project_native_metadata.m` is an original projection of the metadata object returned by current MatMef commit `c896ca41b28f2af927836d18b0afc8ba719b8d57`. That 2025 dependency is not an established historical runtime for the paper. After independently admitting the exact native source/binary, original input files and resource limits, an operator can use this prospective API:

```matlab
meta = read_mef_session_metadata(sessionPath, [], true, false);
packet = ccep_project_native_metadata(meta, recordingKey, sourceManifestSha256);
packetText = jsonencode(packet);
```

The explicit flags request indices and disable records. The visible native entrypoint requests no time-series data; no native runtime or filesystem behavior has been verified here. Even that metadata call can create identity fields and signal extrema inside the operator's process before projection. It needs separate access and execution review. The projection rejects nonempty records and omits subject fields, paths, descriptions, UUIDs and extrema. Original channel names and times remain private. The returned JSON is an operator artifact, never a candidate input.

Capture each complete `packetText` as UTF-8 JSON using an independently admitted operator procedure. Provide a separate trusted binding with these exact fields:

```json
{
  "schema": "clinical-ccep-native-metadata-binding-v1",
  "reader_commit": "c896ca41b28f2af927836d18b0afc8ba719b8d57",
  "recordings": [
    {"recording_key": "operator-key", "native_source_manifest_sha256": "64 lowercase hexadecimal characters"}
  ]
}
```

This one-row illustration shows the schema; a valid binding requires **all five distinct recording keys** in fixed operator order. For each recording, independently authenticate its original patient/session/run, full original-file provenance and native source manifest. That manifest must identify the source/compiler/binary, exact metadata call, original recording and captured output. The validator checks matching digest declarations; it cannot prove those native operations occurred or that five arbitrary keys represent the five clinical patients. No original data or authenticated binding is distributed here.

From the repository root, validate all five complete packets with standard-library Python:

```sh
python3 -I -S -B benchmarks/neuroscience/clinical-ccep-native-metadata/validate_metadata.py \
  --binding operator/binding.json \
  --packets operator/recording-1.json operator/recording-2.json \
  operator/recording-3.json operator/recording-4.json operator/recording-5.json \
  --report operator/new-metadata-audit.json
```

The command refuses an existing report. It rejects malformed/extra fields, foreign or duplicate recordings, mismatched source declarations and incomplete declared channel/segment/index inventories. It retains complete empty inventories as explicit unusable metadata. Source input admission rejects nonordinary files and uses nonblocking/no-follow opens with stable file identities. CPython 3.11.6 on Ubuntu 24.04 is the CI configuration; MATLAB and MatMef are not invoked by CI.

## Scientific boundary

Integer sample/time identities are decimal strings, including values above 2^53. Binary64 fields use hexadecimal bits. Native index sample coordinates are segment-relative. Native clocks remain opaque exact integers: there is no offset correction, interpolation or inferred physical-gap rule. Native no-entry markers remain unknown, not measured support. Negative nonzero conversion factors are preserved. Channel-name collisions, acquisition-order ambiguity, missing units and inconsistent segment declarations remain visible diagnostics.

Every input file is capped at 8 MiB and each packet at 100,000 indices. Actual metadata has not been shown to fit these limits. Exceeding a limit requires a separately reviewed complete operation; truncation or sampling is not allowed. Native MATLAB and simultaneous parsed packets may require substantially more memory than the generated CI checks.

Real channel-to-annotation correspondence, recording clocks, downsampling/filter history, anatomical and mixed-target rules, complete pairing support and competent references remain unverified. A valid audit always reports `scientifically_qualified: false`. MATLAB projection is source-reviewed only. No patient packet or physiological result is supplied as an example.

## Source checks and licensing

CI verifies the literal-pinned manifest and every ordinary package member before executing package code. It then checks relocation and CLI barriers using invented inputs. The complete 18-test generated validator suite is included in `test_metadata.py`; it can also be run from this directory with `python3 -B -m unittest -v test_metadata.py`. Generated checks do not establish native correctness or scientific performance.

The original benchmark-authored source is covered by the included MIT license. MatMef is an external dependency with separate notices and requirements; see [DEPENDENCIES.md](DEPENDENCIES.md). No official reader source, binary, clinical metadata, waveform or target is redistributed in this package.
