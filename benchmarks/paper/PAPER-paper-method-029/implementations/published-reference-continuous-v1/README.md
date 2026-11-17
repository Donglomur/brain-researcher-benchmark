# Complete published-pair discrepancies

This additive route reports the complete Deeprecon Figure2 comparison without requiring an arbitrary pass/fail tolerance. It retains all480 normalized pair-axis values and24 ROI/method/axis summaries, including signed, absolute, maximum and RMS errors. Cancelling signed errors remain visible in the individual rows and absolute diagnostics. No overall score combines unlike endpoints, and no reproduction or improvement decision is inferred.

The unchanged, byte-pinned `published-reference-v1` reader authenticates the publisher CSV and validates replay support: five people,20 directed pairs, six ROIs, two methods, both axes,50 test images and24 repeats. Source normalization clips individual feature ratios to[-1,1] before averaging; this route preserves that domain. It retains the existing explicit refusal of undefined eligible replay values. Publication pair means do not supply original noise ceilings, masks, native arrays, weights or training provenance.

From this directory, using Python3.11 or later and no third-party dependency:

```sh
python -I -B continuous.py /external/published-figure2.csv \
  --replay /external/complete-normalized-replay.json \
  --output /external/pair-discrepancies.json
```

The existing compact replay export is supported. All480 values remain mandatory. Input JSON is bounded to64MiB and rejects duplicate keys/nonfinite constants; output must be fresh. The pure function accepts generated controls and does not claim publisher authentication. Only the CLI adds that receipt after the existing authenticated reader succeeds. Result declarations and byte hashes do not establish native execution or fitting provenance.

The old tolerance-based comparator is preserved for separately specified decision rules. Continuous discrepancies require no binary margin; claims of agreement or superiority still require appropriate qualified execution and a justified decision rule. Twenty overlapping directed pairs share only five people. Arithmetic summaries here are neither independent-subject uncertainty nor the author's bootstrap figure bars.

This source addition does not change the scientific endpoint, current task qualification, historical artifacts or benchmark count. The published pair-mean source has been recovered; native ceiling/mask/data/model/custody and matched candidate evaluation remain separate gaps. It adds no authentic replay, AI attempt, candidate improvement or SOTA result. Generated checks cover the full panel, cancelling errors, invalid substitutions, clipped domains, ordering, input immutability, CLI binding and source-pin rejection.
