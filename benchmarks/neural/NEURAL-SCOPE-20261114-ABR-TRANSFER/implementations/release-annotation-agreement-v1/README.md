# ABR release-annotation code agreement source

This is source construction for a separately named zero-labelled-support assay. It implements numeric release-annotation agreement scoring for the complete observed 936 cases and 104 animals; no empirical prediction result is claimed. It does not reinterpret source code 100 as a physiological threshold or a censored observation, and it does not admit the original calibrated/expert benchmark for scoring.

`abr_release.py` adapts the existing `native-inputs-v1` target bundle, authenticating its fixed completion seal and target files. It draws complete stacks with the maintained, pinned N077 `visual-viewer-v1/raster.py` Canvas/font/line implementation. The new axes are sample indices and native raw amplitudes; the stored field named `level_db` is presented as `release_level_code`. No old physical-threshold scorer or generated-data bypass flag is used.

The candidate receives the full numeric case packet, identical common instructions, and optional complete plot pages in both arms. Every trace, repeated/zero level, and native sample is preserved. All 1,953 samples are drawn, although neighboring samples may share pixels. The numeric packet preserves the underlying precision. Plot-only delivery would introduce an additional representation confound. This library does not establish that a particular model can accept a complete packet within its context limit.

## Operator interface

The package expects `COMMON_DOCUMENTATION.txt` alongside `abr_release.py` after integration. In the present external evidence layout, pass its exact path in the sibling `delivery` directory explicitly. The production factory checks the fixed document hash; arbitrary common documents do not qualify.

```python
native = abr_release.NativeTarget(canonical_preparation_directory)
try:
    pair = native.new_pair(fresh_operator_output_directory, frozen_programme_bytes,
                           documentation_path=exact_common_documentation_path)
    raster = abr_release.load_raster(canonical_repository_root)
    # The operator supplies one fresh isolated candidate invocation per case.
    # No provider call or sandbox is implemented or implied by this library.
    for arm in ('direct', 'programme'):
        for case_id in native.roster.ids:
            packet_bytes = pair.expose(arm)
            packet = abr_release.decode(packet_bytes)
            viewer = abr_release.Viewer(packet, raster)
            # viewer.action({'type': 'pages'}) enumerates complete stack pages.
            # viewer.action({'type': 'page', 'page': i}) returns a PNG and coverage.
            # viewer.action({'type': 'numeric'}) returns the identical full packet.
            response_bytes = obtain_one_first_final_from_fresh_candidate(packet_bytes, viewer)
            pair.submit(arm, case_id, response_bytes)
    pair.seal()
    operator_result = native.score_sealed(pair)
finally:
    native.close()
```

`obtain_one_first_final_from_fresh_candidate` is an explicit missing integration boundary, not a supplied function. A real provider/executor must enforce process isolation, network prohibition, fixed resources, fresh case state, unchanged frozen programme, and target exclusion. Operator file permissions and an in-process collector do not establish those properties. The current authentic input and scoring flags remain false.

`Pair` freezes the programme and common document bytes before exposure. Both arms follow the same observed roster order. A case must receive its first response before the next case can be exposed. Malformed and oversized responses consume the slot without correctness feedback. Both complete sets of 936 first finals are required before the native adapter opens, hashes, or decompresses the protected annotation projection. File replacement, changed roster metadata, mismatched numeric packets, substituted native readers, and revised first submissions are rejected. This is an ordinary operator API integrity boundary, not protection against malicious Python code running inside the same process or same-account filesystem access.

Source labels, animal crosswalks, backgrounds, raw filenames, and wave1 tables are never included in packet projection. The fixed private projection is joined by observed opaque case IDs and unique animal/stimulus pairs. All 104 animals and both 54/50 background strata must remain complete. The original source `score_admission: false` and unresolved threshold semantics are preserved.

## Results and failures

The primary is equal-animal exact numeric-code agreement. Secondary outputs are equal-animal code MAE and agreement within five/ten code units, plus descriptive background, stimulus, and source-code-100 strata. They are never dB error. Decimal comparison preserves numeric distinctions without hidden rounding/tolerance. The documented universal prediction representation bound is finite binary64 magnitude; it is not derived from target values. Invalid responses retain all 936 required cases and withhold that arm's aggregate metrics. The other complete arm may still have an operator result.

The direct `Pair.score` method is explicitly unverified operator arithmetic. Only the native-owned pair factory and reader may label inputs as fixed-release operator inputs. That descriptive identity does not change delivery, original scoring, scientific-qualification, or benchmark-count holds. No empirical model performance is included here.

## Generated control campaign

`test_abr_release.py` is a finite selected control suite, executable with isolated Python:

```text
PYTHONDONTWRITEBYTECODE=1 python -I -S -B test_abr_release.py --repository /canonical/repository/root
```

The parent coordinator owns the single reviewed campaign selection and its resource limit. No test was executed during source authoring. The suite uses two complete generated 936-case/104-animal pairs with compact four-sample structural fixtures; these cannot pass the fixed native completion pin. Separate real-renderer controls draw 21 traces of all 1,953 samples over seven pages, including repeated and zero levels. Controls also cover unequal animal weighting, exact numeric formatting, finite extremes, source100 inclusion, native-provider/document rejection seams, immutable malformed responses, target-last refusal, and changed-file detection. Generated control file writes are bounded below 2 MiB and reported by the suite; PNGs are decoded and checked in memory, not retained as files. No original data, target bodies, models, network calls, or authentic provider receipts are involved.

The single independently reviewed generated campaign passed all **16 controls** in 2.301172 seconds. Exact source, saved-result and review identities are in [validation.json](validation.json). This result does not establish authentic full-cohort delivery, context capacity, participant confinement or model performance.

## Portable integration

Suggested destination: existing task `implementations/release-annotation-agreement-v1/`. Co-locate `abr_release.py`, `test_abr_release.py`, this README, and the reviewed candidate `COMMON_DOCUMENTATION.txt`. Keep companion `EXISTING_PREPARATION.json`, `ASSAY_SCOPE.md`, and validation/review metadata out of candidate inputs. The benchmark owner retains the separately reviewed scientific decision; its identity is recorded in `validation.json`. Preserve the existing `native-inputs-v1`, `initial-evaluator-v1`, and `series-evaluator-v2` sources and their holds. Root registration, source pins, registry/CI edits, and any publication remain separate integration work.
