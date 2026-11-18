# P3 channel-unit declaration verification

The exact release manifest for NEMAR `nm000132/v1.0.0` assigns the same
512-byte Git blob, `4da38d26a268f636b287dfc0d9333d0cde5f5f63`, to all 40
P3 `channels.tsv` paths. The [versioned publisher-hosted table](https://github.com/nemarDatasets/nm000132/blob/v1.0.0/sub-001/eeg/sub-001_task-P3_channels.tsv)
and its [plain-text view](https://raw.githubusercontent.com/nemarDatasets/nm000132/v1.0.0/sub-001/eeg/sub-001_task-P3_channels.tsv)
declare `microV` for the 30 EEG and three EOG channels. This establishes what
the metadata declares. It does not independently calibrate the recording
device, authenticate the browser's raw HTTP response, or demonstrate that a
particular derivative retained the same scale.

An operator-side metadata check transcribed the displayed rows using tabs and
LF, then matched both the pre-existing 512-byte Git blob and the complete pinned
manifest through `verify()`. The resulting SHA-256 is
`19c4ca3fa445da3b823ae69c9ff9cd7fc3003c85a7142092cfd2f45411d8c000`.
This verifies the reconstructed metadata bytes; it is not a saved HTTP response
or an EEG amplitude measurement. The table was not materialized on disk.

`verify_channels.py` supplies an offline operator check for the exact manifest
and channel-table bytes. It checks the complete release inventory, Git object
identity, ordered source channel names and EEG/EOG roles. The report retains
literal unit strings, including unknown or mixed declarations; it never
converts amplitudes, corrects event times, loads recordings, or changes the
current packet. A new source-table declaration is not permission to relabel
the frozen numerical prompts or PNG axes.

```sh
python3 -I -S -B verify_channels.py \
  --manifest /absolute/existing/nm000132-v1.0.0-manifest.json \
  --channels /absolute/existing/sub-001_task-P3_channels.tsv \
  --output /absolute/new/channel-declaration.json
```

No input is downloaded. There is no production pin override. Input directories
belong to the trusted operator; the bounded reader is not an adversarial
filesystem sandbox. A failed input leaves no admitted output. The output must
be a new file.

The current task continues to classify the same 400 released-marker-relative
epochs from two exposed development people. The paper's physical monitor-delay
correction, the selected derivative's transformation history and independent
device calibration remain separate questions. This component adds no benchmark
ID, scientific score, participant mode or readiness promotion.

The generated controls exercise malformed tables, channel order/role errors,
unknown and mixed units, duplicate/incomplete/altered manifest entries, a wrong
manifest pin, bounded file reading and symlink refusal:

```sh
python3 -I -S -B -m unittest discover -s . -p test_verify_channels.py -v
```

These tests contain generated metadata only. No authentic EEG, API/model call,
native interpretation episode or scientific scoring was performed. Runtime
enrollment and acquisition of a raw-response receipt for the 512-byte table
remain integration/operator actions.
