# Complete ABR native source preparation

This original standard-library implementation converts the exact three source
archives into an operator preparation bundle: every native waveform value,
every target animal×stimulus stack, both complete support labs, private
annotations and source provenance. It fixes two real native-format failures in
the earlier generic census: repeated unnamed CSV metadata columns are legal,
and CFTS files contain several tab-separated metadata fields on each header line.
It does not copy unlicensed author code.

**The output is not an admitted benchmark packet or a scoring-ready reference.**
The scientific holds below remain. The existing series evaluator still refuses
authentic aggregate scoring. No candidate, model, training or author baseline is
executed by this component.

## Complete sources and observations

| Lab | Exact release | Archive | Compressed bytes | Waveform tables / level records / stored values per record |
| --- | --- | --- | ---: | --- |
| Manor | Zenodo 17584961 | Manor_Lab_Cleaned.zip | 14,131,356 | 110 / 6,737 / 244 |
| Liberman | Zenodo 17584961 | ABR_Data_Liberman.zip | 12,392,618 | 748 / 7,293 / 426 |
| Marcotti | Zenodo 15619100 | MouseABRs.zip | 138,620,782 | 104 / 16,226 / 1,953 |

The immutable SHA-256 pins, complete archive member counts and expanded sizes
are embedded in `PINS`. All 2,173 members and 406,584,009 expanded bytes are
accounted for, including resource-fork sidecars and evaluator-only annotations.
The source files are opened read-only; nothing is extracted to a source path.
There is no network path or alternate-source override in the CLI.

Target labels join to all 104 animals, including both published genetic
backgrounds (54 and 50 animals). A case contains all recorded traces for one
animal and stimulus. Cases are constructed from observed records and then joined
to the complete annotation table. The native release has 936 such cases. This
is an observed result, not a guessed Cartesian case generator. All 104 separate
wave1 annotation files remain private; peaks never substitute for thresholds.

The source has 20 click levels from 0–95 dB, usually 17 tone levels from 15–95 dB,
and two additional 18-kHz observations at 5 and 10 dB. A global 15–95 filter
would discard real observations. There is no dropping of all-zero traces,
repeated levels, mice or low-count groups, and no interpolation or normalization.
Source target frequency `100` means **click**, never a 100-Hz tone. The rule is
specific to this target release and is not imposed on another laboratory.

## Physical calibration is explicit

Manor CSV columns `Samp. Per.`, `O.S. Time`, and `Data(uv)...` have documented
meanings in the [TDT BioSigRZ CSV manual](https://www.tdt.com/docs/biosigrz/data-analysis/):
period in microseconds, first-point offset in milliseconds, and output waveform
units selected at export. For the complete native records, period 40.96 µs,
offset 0 ms and 244 samples yield last coordinate 9.95328 ms. This is not a
244-point linspace ending at 10 ms and does not authenticate acoustic onset.

Liberman CFTS headers give a 40 µs sample-period field, and the complete
retained census contains 426 stored values per level. **Their physical layout
is unresolved; these values must not be treated as an authenticated continuous
17 ms waveform.** All 748 tables use legacy CFTS V2.37.1 (R3164) headers. The
[EPL-maintained legacy reader](https://github.com/EPL-Engineering/abr-peak-analysis/blob/a6b8068ba9177f78ef5c9655728278007776573c/Source/datafile.py)
splits each stored row into equal average-polarity and polarity-difference
blocks; for this shape, its interpretation would be 213 + 213 values. The
published ABRA [Supplementary Table S1](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13018588/supplementaryFiles?includeInlineImage=false)
instead describes Lab C as 426 samples over 17 ms. Compatible headers and
shape do not establish which writer/export transformation produced the release.
Neither interpretation is adopted as a qualified physical representation.

The paper-named [preprocessing notebook](https://github.com/ucsdmanorlab/abranalysis/blob/0369a215b429002c115af2ac1f0922bb190d5c1f/notebooks/ABR_Preprocessing.ipynb)
uses its own Liberman parser, selects 250 columns and interpolates to 244 values,
without the inspected EPL split. This is a source-code observation, not proof
that an historical execution consumed the deposited values in that exact order.
A release-applicable acquisition/export specification must reconcile these
paths before a support baseline or physiological interpretation is admitted.

The complete original values and order remain preserved. The existing loader's
uniform-axis metadata is an unqualified header projection, not proof of
continuity across all 426 stored entries. No channel split, cropping, filtering,
polarity conversion or resampling is applied here. Voltage units and the
first-sample/acoustic reference remain null. Ear headers and source filenames
remain private; a filename/header `L`/`R` conflict does not establish an ear or
biological repeat identity. This correction changes no Marcotti target-only
annotation-code packet, source count, label or readiness flag.

Source pins for this unresolved layout join: EPL July 2023 reader 12,628 bytes,
SHA256 `b404bcbd90dd669d3ecf2584260fb8ad8ce69050b21fa2aab80bc0043a6b8531`;
published supplement PDF 1,897,226 bytes, SHA256
`268f252074b84d1aef74c903def4b17c4dc953a851395add16ee551a3a80a83b`;
paper-named notebook 91,611 bytes, SHA256
`77665f148075e595ffdb2a04383cc3bc77cc05561712b357be3cf763ad02ff6f`.
The supplement's authenticated text was inspected; separate visual verification
did not complete and is not claimed. The previous 17.00 ms statement remains
in repository history; it is superseded by this explicit qualification.

Marcotti waveform CSVs contain 1,953 indexed samples without embedded physical
period or voltage unit. The associated analysis code's acquisition-rate
convention alone has not yet authenticated the exact release conversion.
Target axes therefore remain sample-index axes with null physical units.
The waveform arrays are preserved completely so later evidence can establish
physical coordinates without re-fetching or silently truncating data.

## Annotation projection and admission holds

The complete target threshold table is projected onto the observed cases as
**raw source annotations**, including source column and row, observed level
range, and private biological grouping. It is not converted into the existing
evaluator's exact/censored annotation schema. Three literal values of 100 exceed
the largest recorded level of 95. Neither treating 100 as an exact threshold nor
replacing it with a right-censored 95 bound is supported by an applicable source
convention yet. This raw projection does not replace the earlier applicability review supporting
933 on-grid released expert annotations. The complete 936-case reference remains
unadmitted while the three exceptions are unresolved; this implementation cannot
silently turn finite numbers into qualified labels.

Manor cursor slots lack an authenticated complete expert-threshold mapping.
Liberman thresholds are preserved as raw fields, and source animal/ear/repeat
identity still requires evidence. A full-support source-only comparator, grouped
splits, four matched source stacks, common direct-observation representation,
protected candidate transport and condition state isolation remain unqualified.
File separation and opaque IDs alone do not establish holdout protection: these
are publicly released data with preserved historical exposure.

## Bundle layout and use

`observations/target/` contains one gzip binary float64 sample stream, a gzip
JSONL trace index and a gzip JSONL case index. `observations/support/manor/` and
`observations/support/liberman/` contain complete waveform streams and indices.
Offsets count samples in the decompressed stream; byte offset is `8*sample_offset`.
No samples are discarded or rounded beyond parsing native decimal tokens into
IEEE 754 binary64. Trace index fields are selected explicitly; source filenames,
animal IDs, genotypes, threshold columns and wave1 labels are omitted.

`private/` contains source-member hashes, trace provenance, raw threshold
projection, all wave1 tables, the opaque-ID key and the preparation manifest.
The entire output root is mode 0700 and files are mode 0600. A `COMPLETE.json`
seal is written only after all exact denominators, roster/case joins and output
hashes pass. Failed output directories are retained without this seal. A new
run refuses an existing output directory. The operator must not expose this
bundle directly to candidates.

```sh
python3 native_inputs.py \
  --manor /read-only/Manor_Lab_Cleaned.zip \
  --liberman /read-only/ABR_Data_Liberman.zip \
  --marcotti /read-only/MouseABRs.zip \
  --key-file /private/32-byte-binary-key \
  --output /private/new-abr-preparation
```

Only the pinned complete authentic archives are accepted by the CLI; generated
unit tests exercise the readers directly. Authentic preparation requires a
separately admitted resource protocol. Maximum member size is 8 MiB and maximum
serialized uncompressed output is 512 MiB. The implementation uses Python 3.11
standard-library modules only. Test with `python3 -m unittest discover -s tests`.

Primary release documentation: [target](https://zenodo.org/records/15619100),
[support](https://zenodo.org/records/17584961),
[ABRA paper](https://www.nature.com/articles/s41598-026-38045-1), and the
[target collection paper](https://doi.org/10.1016/j.heares.2025.109328).

## Executed validation

The root-reviewed complete cached-source preparation ran once on 2026-11-17:
13.212 seconds, 214,089,728 bytes peak child RSS, zero downloads and zero model
runs. It produced 117 private files containing 271,631,813 logical bytes. A
separate audit verified every file hash, complete decompression of all 36,440,024
stored values, all 30,256 traces, the 104-animal/936-case target join, all 104
private wave1 tables and observation-field separation. All three above-range
threshold annotations remain unresolved. There were no candidate attempts.

[Machine-readable validation receipt](validation.json) records the exact source,
control, execution, completion and independent-audit hashes. Fifteen generated
controls cover complete archive-to-bundle transport, binary sample transport and
complete sample counts, repeated levels, source hash rejection, path safety, missing cases, private
annotation projection and duplicate wave1 animal aliases. Authentic data and the
opaque-ID key remain outside the repository. This evidence closes complete
native preparation; it does not close the scientific admission holds above.
