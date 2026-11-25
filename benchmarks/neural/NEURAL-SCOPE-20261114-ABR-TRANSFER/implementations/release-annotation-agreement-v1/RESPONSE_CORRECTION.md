# Bounded malformed-response correction

The predecessor scorer could abort its one-shot scoring operation when a first
final was within the 4,096-byte response limit but contained JSON deeper than the
interpreter could parse. Such a response is invalid input, and must remain in
invalid coverage rather than prevent the complete panel from being reported.

The correction catches `RecursionError` in the existing per-response validation
boundary. It retains the original first final, counts it as invalid, withholds
that arm's aggregate metrics, and continues the other arm. Original metric
formulas, 936-case and 104-animal denominators, first-final sealing, source pins
for authentic inputs, and scientific qualification holds are unchanged.

A generated control with all 1,872 first-final records reproduced the predecessor
failure using one 3,076-byte nested response. The corrected scorer returned 935
valid and one invalid direct response, with all 936 programme responses valid.
The generated programme's exact agreement was one; this is a software control,
not participant performance or evidence about authentic neuroscience data.
Second scoring remained prohibited. The focused check is:

```sh
python3 -I -S -B test_nested_response.py --output /path/to/fresh-generated-output
```

The native-delivery package binds the corrected helper. Its observation-store
loader also retains the exact predecessor producer identity, because the release helper's observation-producing
code is unchanged by this exception-handling correction.
The externally pinned old store manifest is neither edited nor relabelled. A
focused generated metadata control admitted the two explicit producer pins and
rejected an unknown one. Existing manual sessions remain pinned to their original
source closure; this correction does not migrate their journals.

Earlier validation receipts describe their original source versions. No authentic
preparation, private annotation access, participant run, or scientific scoring was
repeated for this correction.
