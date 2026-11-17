# Current clinical CCEP metadata validator

The current command is
[`validate_metadata.py`](../implementations/clinical-ccep-native-metadata/validate_metadata.py)
under this task's `implementations/clinical-ccep-native-metadata/` directory.
The [retained package guide](../implementations/clinical-ccep-native-metadata/README.md)
uses the former `benchmarks/neuroscience/` location. Use the command below with
the current layout; the historical guide and source inventory remain unchanged.

This component validates **operator-private metadata for all five recordings**.
It does not read MEF waveforms, fit a model, produce predictions or establish
the [task's scientific result](../task.json). The
[artifact grader](../implementations/clinical-ccep-artifact-grading/README.md)
and [paired controls](../implementations/clinical-ccep-pairing/README.md) remain
separate components.

## Validate the complete metadata set

Run from the repository root with standard-library Python 3.11 or later on a
POSIX host supporting the validator's non-following, nonblocking file opens:

```sh
CCEP_METADATA="$PWD/benchmarks/neural/clinical-ccep-stimulation-attribution/implementations/clinical-ccep-native-metadata"
python3 -I -S -B "$CCEP_METADATA/validate_metadata.py" \
  --binding /ABSOLUTE/operator/binding.json \
  --packets /ABSOLUTE/operator/recording-1.json \
    /ABSOLUTE/operator/recording-2.json \
    /ABSOLUTE/operator/recording-3.json \
    /ABSOLUTE/operator/recording-4.json \
    /ABSOLUTE/operator/recording-5.json \
  --report /ABSOLUTE/operator/new-metadata-audit.json
```

Replace the paths with independently supplied operator artifacts. The binding
has schema `clinical-ccep-native-metadata-binding-v1`, exactly five distinct
recording keys and reader commit
`c896ca41b28f2af927836d18b0afc8ba719b8d57`. Each key binds a native source-manifest
digest. The five complete packet files must match those identities; filenames
alone do not identify patients, sessions or runs. Report rows follow the binding
order. The report's parent directory must exist and the report itself must be
absent.

The validator rejects foreign or duplicate recordings, malformed fields,
mismatched declarations and incomplete declared channel, segment or index
inventories. Complete empty inventories remain explicit unusable metadata. Every
input file is limited to 8 MiB and each packet to 100,000 indices. Authentic
metadata has not been shown to fit these limits. Exceeding them requires a
reviewed complete operation; truncating the metadata is not an accepted workaround.

The binding, packets and resulting audit are assessor artifacts. Keep all three
outside candidate inputs: original channel names, times and source identities
are private protocol information. Matching declared hashes does not authenticate
the original native operation or prove that arbitrary keys represent the five
clinical recordings.

## Separate native preparation

The package contains an authored MATLAB projection,
[`ccep_project_native_metadata.m`](../implementations/clinical-ccep-native-metadata/ccep_project_native_metadata.m).
It accepts an independently obtained metadata object from the selected MatMef
reader. Source/compiler/binary identity, original files, permissions, exact call
and resource limits require separate admission before that native procedure is
used. The Python validation command above does not invoke MATLAB or MatMef and
does not acquire original recordings. External dependency notices and requirements
are in [DEPENDENCIES.md](../implementations/clinical-ccep-native-metadata/DEPENDENCIES.md).

Exact native integer clocks and sample identities remain opaque. The validator
does not infer offsets, align channels to annotations, resample signals or prove
the clinical target rules. The MATLAB projection is source-reviewed only;
faithful waveform conversion, complete pairing support and competent references
remain unverified. A structurally valid audit still reports
`scientifically_qualified: false`.

## Generated validator controls

The standalone validator tests use invented inputs and the standard library:

```sh
(
  cd "$CCEP_METADATA"
  python3 -B -m unittest -v test_metadata.py
)
```

The separate delivery tests require their authenticated CI setup and are not a
standalone substitute for this command. Generated checks establish software
behavior within their tested scope; they do not establish native correctness,
patient-data alignment or benchmark readiness.
