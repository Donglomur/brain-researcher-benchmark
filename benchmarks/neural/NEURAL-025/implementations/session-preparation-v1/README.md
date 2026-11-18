# Prepare one NEURAL-025 calcium session

This command prepares the fixed cfa24 M1 source session for the existing NEURAL-025 stored-joint-angle condition. It preserves all 416 original records, pairs the 372 source-eligible trials and retains the 44 original exclusions. It does not fit a decoder, define a new benchmark endpoint, or qualify the complete ten-session/five-mouse task.

The public package contains source, a fixed recipe and aggregate evidence. Original MAT files, derived arrays and detailed trial manifests remain outside the checkout. No download, dependency installation or model/API call is performed.

## Existing dependencies and source check

Use an existing POSIX Python 3.11+ environment with NumPy and h5py. The recorded original execution used Python 3.11.6, NumPy 1.26.3, h5py 3.11.0 and HDF5 1.12.2. That observation does not establish execution on another runtime. The source check needs only the standard library:

```sh
python3 -I -B benchmarks/neural/NEURAL-025/implementations/session-preparation-v1/prepare.py check
```

The package verifies its closed source namespace and immutable mathematical dependencies. It reuses the existing sibling `locked-mat-admission-v2/admission.py` and `train-only-decoding-v2/source_condition.py` by exact hashes and relative paths. These siblings must exist in the checkout. `SOURCE.json` records the new adapter/CLI source identity; it does not defend against replacing the whole trusted checkout.

## Private preparation

Obtain [Figshare file 60332984](https://ndownloader.figshare.com/files/60332984), named `R,cfa24_20220727_160603,thresholded,DLC3.mat`, from the public release. `RECIPE.json` fixes its 980,063,226-byte size, provider MD5 and independently recorded SHA256. Keep the original filename. The command checks the entire file and header before reading the selected fields.

Choose an external directory and create the log parent before shell redirection. The output directory must not exist; earlier outputs are never overwritten.

```sh
CALCIUM_PRIVATE=/absolute/path/outside/the/checkout
mkdir -p "$CALCIUM_PRIVATE/logs"
mkdir "$CALCIUM_PRIVATE/logs/run-01"
python3 -I -B benchmarks/neural/NEURAL-025/implementations/session-preparation-v1/prepare.py prepare \
  --original "$CALCIUM_PRIVATE/originals/R,cfa24_20220727_160603,thresholded,DLC3.mat" \
  --output "$CALCIUM_PRIVATE/session-cfa24-run-01" \
  > "$CALCIUM_PRIVATE/logs/run-01/stdout.txt" \
  2> "$CALCIUM_PRIVATE/logs/run-01/stderr.txt"
```

The adapter derives the fixed metadata census from the original; no private cached receipt is required. It uses one authenticated file handle, the original first eligible camera clock, all ordered 565 ROI columns and all 24 stored joint columns. The unchanged numerical route preserves 115 padded neural rows, 101 preparation rows and the 51 evaluation rows at -100:10:400 ms. Full joint trajectories are smoothed before event locking. Every eligible trial is compared with the independent reference; intermediate arrays are hashed and released between trials.

Outputs include two NPY arrays shaped `(372,51,565)` and `(372,51,24)`, the complete private source/census/identity records and a completion receipt. Their payload is 89,396,064 bytes. A failed trial stops the collection and retains explicit paired, failed and unattempted records separately from source exclusions. File presence alone is not completion; require the successful complete receipt.

The recipe caps logical original reads at 2 GiB, callbacks at 8 MiB, arrays at 90 MiB and combined JSON at 4 MiB. The 750-second work checks are cooperative; this CLI does not provide an OS memory limit, native execution lease or process supervisor. Arrange external resource limits appropriate to the execution environment.

## Evidence and limits

`AUTHENTIC_EVIDENCE.json` records the accepted original session execution of the unchanged core: 372 pairs, all 44 exclusions, 2,604 stage comparisons, 744 independently verified trial hashes and all 11,174,508 exported values finite. The native run completed in 117.214 seconds. Its separate outer console publication failed because the capture directory was absent; saved arrays, controller/inner-owner receipts and cleanup were independently verified. The failure is retained. Creating the log directory before redirection is the prospective correction; no original run was repeated.

The portable adapter/CLI is a new composition. Its path and binding controls do not constitute a new authentic data run. Historical output hashes remain evidence for the recorded runtime and unchanged core; cross-runtime bitwise equivalence is not established.

The output propagates the exact existing `calcium_processed_input_source_condition_v2` for `smoothed_deconvolved_events`, with its canonical `upstream_exposure_sha256`. Unknown raw dependency and fitted-trial exposure remain unknown. This is offline, lift-conditioned processed-input preparation. There is no causal/online, upstream fold-safety, anatomical column verification, native MATLAB/toolbox/inverse-kinematics or model-performance claim. The other nine sessions, full v2 normalized-dataset/protocol admission, training-only feature selection/PCA/decoder fitting, fixed split and protected evaluation remain separate requirements.
