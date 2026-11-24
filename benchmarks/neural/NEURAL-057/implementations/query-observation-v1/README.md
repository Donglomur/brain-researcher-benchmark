# Complete query observation delivery

The registered programme receives a target-free query view and its complete
200-row feature matrix, but provides no human-readable delivery of those same
numbers. `observation.py` exports one such view to a self-contained offline HTML
page. Row navigation exposes every feature without transformation or selection;
the complete matrix remains embedded. This supports inspection of the existing
observations before a future direct/restricted-viewer comparison is qualified.

```sh
python3 observation.py --query /participant/input/query.json --output /participant/observations.html
```

Open the new file locally in a browser. No server, dependency installation,
network request or model is required. The command reads only the supplied query
JSON and its same-directory `features.npy`. It rejects extra fields (including
targets), FIT views, incomplete rows/categories, altered feature identities,
nonfinite values and nonprimitive arrays. It never overwrites an existing output.
The page retains the exact query-file SHA-256, feature descriptor, taxonomy digest,
FIT-state digest and preparation digest. These identities support provenance;
they do not authenticate an arbitrary caller's source or confer run authority.

All 200 query IDs and 53 category names retain their original order, including
queries whose category support is unknown to the participant. IMAGE has 176
columns, PRE 170, BASE 346 and LATE 686. The column labels follow the registered
RGB/Sobel extraction and channel-major EEG flattening exactly. EEG axis and time
sample labels are positional because the participant query schema does not carry
the original coordinate names or exact timestamps. No anatomical sensor label,
raw image, concept name or protected target is reconstructed or added.

The exporter preserves the registered observation boundary and requires an
already generated view. It does not execute preparation, training, inference or
scoring; alter the protected loss; fit a model; or enroll a new scientific lane.
The F/I modes remain programme-development modes. This delivery artifact does
not itself enforce tool restrictions, match direct/tool training exposures or
budgets, or close all 80 participant cells. A future comparison must separately
qualify those conditions, keep all original cases and score against the same
protected targets. Do not infer native understanding from this exporter.

Treat the output as participant observation material, not public repository
content. It contains the full query observations and IDs. Authentic taxonomy,
image/EEG alignment, runtime qualification and reference execution remain absent.
Public-corpus exposure, released session MVNN and stimulus overlap remain the
registered scientific limitations.

The source basis is the local registered `campaign.py` query-view producer,
`features.py` panel extraction, `splits.py` windows, `taxonomy.py` roster and
`SCIENTIFIC_METHODS.md`. Their exact identities are recorded in `SOURCE_PINS.json`.
Generated controls exercise delivery and refusals only:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
```
