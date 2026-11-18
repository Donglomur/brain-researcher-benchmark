# NEURAL-019: DejaVu presentation profile

This separate component defines `n019-dejavu-sans-mono-12-rgb-v1`. It uses the exact bundled, unmodified DejaVu Sans Mono font and complete notice from the retained NEURAL-021 package. It preserves NEURAL-019's 12 px RGB/BASIC layout; NEURAL-021's 13 px/grayscale settings are not used. The existing Monaco component, source, outcomes and stimulus identity remain intact.

Changing a font changes the visual stimuli and can change text extents, refusals and perceptual difficulty. Do not pool Monaco and DejaVu outcomes as identical stimuli. This is a trusted operator library and a generated compatibility target, not an admitted participant environment, native-understanding result or benchmark readiness claim.

## Selected package and operator boundary

An external operator selection must pin this entry point and the exact `PACKAGE.json` digest. The package manifest pins the renderer, preflight, `PROFILE.json`, font and complete notice. `PROFILE.json` pins the source and viewer identities and rendering settings. Neither source file embeds the digest of a manifest which hashes that source, so this is an acyclic trust structure.

Pass the expected digest from the external selection receipt, not by hashing an unselected directory and trusting the result. `runtime_preflight.verify_package(manifest_path, expected_digest, viewer_path)` verifies all selected bytes, including its own source, before dynamic component execution. It uses bounded ordinary-file reads with leaf-symlink/hardlink refusal and stability checks. This is not a claim of hermetic libraries, hostile-process isolation or custody of arbitrary ancestor paths.

`runtime_preflight.load_selected(...)` verifies the package, observes dependencies, compiles the same checked renderer/viewer bytes into private modules, and constructs the renderer. It returns operator-owned `transport`, `viewer`, `renderer`, `binding` and `observation` attributes. Create the original collector and transport with explicit action/frame/deadline budgets. Never pass these Python objects, source files or filesystem access to a participant.

The selected loader injects the manifest/profile/source/font/notice identity into only its own renderer module. Each operator render record and final receipt retains that binding, observed runtime and separate source-SVG/PNG/stimulus hashes. In-process mutable objects are not a security boundary. The low-level `Renderer(font_bytes)` interface remains available for trusted mechanical compatibility tests but explicitly reports `selected_package=false` and `package_binding=null`; it cannot silently inherit the selected loader's lineage. Such a call is not selected-package admission.

The participant frame still contains only PNG base64 and navigation metadata. Raw numbers/SVG, source identity and targets are not added to the participant response. There is no raw/text fallback after a refusal.

## Exact presentation and preserved scientific support

The font is 340,240 bytes, SHA-256 `602ec86b8948cfcd956482fe64f94c36c867770149ef2f791d4613f443bcecb3`. `assets/LICENSE_DEJAVU` is the complete 4,816-byte notice, SHA-256 `d75938dec098f06f0ac3c00853065d94f020be1c3c62ef1dc2975ba15b4d9b0e`. Preserve the notice with the exact asset. Its copyright/trademark/permission, modification-name, font-only-sale and promotional-name conditions remain in that file. No other font or fallback is admitted.

The renderer retains 12 px/BASIC/anchor `ls`, RGB, black text, white background, zero/nonzero cell colors, 53x23 cells on a 54x24 step, maximum 16-unit by 20-bin crops and 1180x928 canvas. Every printable non-space ASCII glyph must be nonmissing and decimal glyph masks distinct. Every text box must fit its own cell, row/header and canvas; unsupported glyphs and overflow refuse without clipping, shrinking or truncating. PNG settings remain optimize=false/compression=9; PNG and frame caps remain 262,144 and 393,216 bytes.

The unchanged viewer binds all 1,340 calibration and 126 assessment trials, 137 units, 140 bins and 35,280 signed x/y velocity response values. Neural clock -250..445 ms and velocity clock -150..545 ms retain their 5 ms step and retrospective +100 ms alignment. Data, calibration, splits/folds, collector, targets, metric and comparators do not change. Assessment maze identities remain private. These are numerical spike-count panels, not EEG waveforms or proof of biological latent-state understanding.

## Runtime and CI seam

Pillow 12.3.0 remains an explicit renderer requirement. NumPy is needed by the viewer. FreeType is observed, not a universal renderer or scientific gate. Preflight reports whether the observed Pillow/FreeType/NumPy distribution matches the prospective reference 12.3.0/2.14.3/2.4.6; a match is not binary, hosted-runtime, readability or scientific admission. A FreeType mismatch is reported for later scoped software qualification, rather than silently turned into a scientific exclusion.

The existing hosted scientific group uses Pillow 11.1.0. It is incompatible with this renderer. A separate task-local route may use Python 3.11.18, Pillow 12.3.0 and NumPy 2.4.6 after actual Linux availability/profile reconciliation. This package does not install or provision that route or change the shared dependency group. The local Python/runtime observations in saved results must stay separate from those future hosted requirements.

From this component directory, on a separately selected, already provisioned runner, with `SELECTED_PACKAGE_SHA256` obtained from the external receipt:

```sh
python3 -I -S -B runtime_preflight.py --manifest-sha256 "$SELECTED_PACKAGE_SHA256" --viewer ../typed-count-viewer-v1/viewer.py --verify-only &&
python3 -I -B runtime_preflight.py --manifest-sha256 "$SELECTED_PACKAGE_SHA256" --viewer ../typed-count-viewer-v1/viewer.py --font assets/DejaVuSansMono.ttf &&
python3 -I -B test_png_transport.py --viewer ../typed-count-viewer-v1/viewer.py --font assets/DejaVuSansMono.ttf &&
python3 -I -B test_profile_successor.py --manifest-sha256 "$SELECTED_PACKAGE_SHA256" --viewer ../typed-count-viewer-v1/viewer.py --temp-root /explicit/bounded/private/scratch
```

These commands require exact selected source identities before use. The verify-only route uses the standard library and reads selected package bytes; it imports no renderer/viewer/Pillow/NumPy. A full preflight must succeed before PNG controls. Original 12-method controls are byte-identical and adjacent to the successor because their `__file__` import resolves the sibling renderer. Their low-level results are mechanical evidence; the new focused suite separately exercises the selected loader, per-frame/collector lineage, tamper refusal before execution, all 137x140 geometry via generated tiling, boundary glyphs, deadlines and software-profile distinctions.

Run generated controls only through the selected two-slot pool, one thread, declared <=1 GiB, <=180 seconds including <=30 seconds queued, and combined logs strictly below 16 KiB per call. PNGs remain in memory; all scratch writes and deleted or overwritten bytes count against the operation allocation. Old 12 PNG, 3 deadline, 8 stdlib and later Monaco successor outcomes remain separately retained and do not qualify this profile.

Authentic complete-support renderability, actual label/velocity readability, human/model perception, provider image delivery, process/filesystem/network isolation and direct/viewer versus tool/program scientific mode selection still require separate evidence. No authentic source arrays/images, models, fits or scoring are exercised by these generated controls.
