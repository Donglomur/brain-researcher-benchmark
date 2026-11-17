# OpenMIIR matched-support audit

**The original OpenMIIR source does not support NEURAL-082's proposed matched different-melody contrast.** This executable audit establishes the stimulus-support problem before EEG acquisition or model fitting. It is not a neural scorer, a completed neural benchmark, or a replacement song-identification task.

Both original metadata versions contain 12 stimuli. Exhaustive within-version pair comparisons find:

| Metadata rule | Version 1 | Version 2 |
| --- | --- | --- |
| Same cue tempo and meter | 1/11, 2/12, 3/13, 4/14 | 1/11, 2/12, 3/13, 4/14 |
| Same author-effective tempo and meter | 3/13, 4/14 | 1/11, 2/12, 3/13, 4/14 |
| Above rules plus same recorded song duration | No pairs | No pairs |
| Different-composition pairs sharing either tempo definition and meter | No pairs | No pairs |

Each listed pair consists of vocal and instrumental recordings of the **same composition**, as explicitly identified by the [author's Table 1](https://doi.org/10.3389/fpsyg.2017.01255). These are different recordings and arrangements, not a controlled change in melody. Matching their tempo does not establish identical detailed rhythms, beat onsets, acoustic envelopes, or imagined timing.

The author metadata loader uses the measured-BPM column for version 1 and cue BPM for version 2. Treating these columns as interchangeable changes the admissible pairs. Durations are compared as the exact recorded decimal values in the source workbook XML, with no tolerance or extra rounding. Equality at that precision would still not establish physical timing equality. The paper's coarse 7.7-second table entries for stimuli 2 and 12 conceal unequal version-2 durations, approximately 7.6701 and 7.7737 seconds.

Equal-duration windows could remove the full-length difference. They cannot create different-composition alternatives at the same declared tempo. Ordinary identity prediction or vocal-versus-instrumental rendition classification would therefore answer a different question and must not satisfy NEURAL-082.

The [source presentation](https://github.com/sstober/openmiir/blob/f3418202d8ae9311e9d69238fba694dc437232f8/scripts/presentation/OpenMIIR_StimulusPresentation.m#L216) displays song title and lyric state before imagery, including imagery without rhythmic clicks. If a nuisance comparator receives that full cue identity or a stimulus-coded alias, the requested excerpt is determined by design. An EEG improvement beyond that identity is not an identifiable conditional-information target. This is a design argument, not a measured model result. A future protocol using only rhythmic-click features would need to state that narrower input boundary and still address the missing melody overlap. Intended presentation code is not evidence that every actual recording executed these exact lines.

## Reproduce the metadata audit

Use the five files enumerated in [source_manifest.json](source_manifest.json) from the pinned [OpenMIIR source](https://github.com/sstober/openmiir/tree/f3418202d8ae9311e9d69238fba694dc437232f8), plus the pinned [author metadata loader](https://github.com/sstober/deepthought/blob/ec7f12f0be7b0a19f728c612fb8f9e5a42cb9d7e/deepthought/datasets/openmiir/metadata.py). No EEG or audio files are required. The loader is checked as bytes and never imported.

```sh
python3 support.py \
  --source-root /path/to/openmiir \
  --metadata-loader /path/to/deepthought/datasets/openmiir/metadata.py \
  --output /path/to/new-support-report.json
```

The command verifies SHA256, file sizes and original OpenMIIR Git blob identities before parsing. It reads workbook cached values without evaluating formulas or macros, enumerates all 66 unordered pairs in each version, and writes an exclusive new output. [support_report.json](support_report.json) is the actual source-metadata output, containing the complete 24 versioned rows and their input identities. It contains no participant EEG, raw audio, inferred response, or model score.

The original released participant roster remains ten people: P01/P04/P05/P06/P07 use stimulus version 1; P09/P11/P12/P13/P14 use version 2. This source roster does not authenticate participant payloads or session-level event timing. It does not import the later paper's nine-person analysis exclusion or the unrelated 21-person music/score runtime previously attached to this task.

## Remaining scope

NEURAL-082 retains its original scientific question and its mismatched implementation history. This component replaces an unknown-support gap with a reproducible negative design finding. There is no original-target eligibility, EEG metric, model trial, native signal-understanding result, or scientific qualification. Any alternative rendition or song-identification experiment needs a separately stated target and controls; it is not silently substituted here.
