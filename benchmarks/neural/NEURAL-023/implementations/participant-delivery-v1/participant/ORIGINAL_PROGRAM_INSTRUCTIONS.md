# NEURAL-023: fixed-program, across-day hand-velocity reconstruction

Write one Python file accepting `--input /input --out /output`. The program runs in a fresh offline container and must write `/output/predictions.npz`. The four read-only input files are `source.npz`, `calibration.npz`, `assessment.npz` and `manifest.json`. Source and calibration contain observed spike-count bins and their training velocity targets. Assessment contains counts, time-bin edges and required endpoint IDs, with no velocity targets. Read the manifest's channel/clock conventions. All 96 observed channels remain available; this is one animal across two recording days.

The target is retrospective hand velocity in metres per second averaged over the trailing 20 ms bin at each assessment endpoint. It is **not a future-velocity prediction or an enforced online task**. The fixed reference uses the ten count bins before each endpoint, but an arbitrary submitted program can inspect the complete assessment batch, including later assessment bins. Report any such use honestly. No assessment targets or earlier reference predictions are supplied.

Submit exactly these arrays in the NPZ:

- `case_id`: 22,091 unique integer endpoint IDs, exactly 3,010 through 25,100, in any order.
- `velocity_m_s`: finite real floating-point values, shape `(22091, 2)`, paired with those IDs in x/y order.

The existing scorer accepts its documented NPZ/NPY representations, including compressed archives, with a 1,000,000-byte file cap and 600,000-byte expanded payload cap. It validates the complete public schema and ID set before loading private targets. Do not output object arrays. Negative R² is a valid outcome; there is no scientific pass floor. Numerically extreme finite submissions may receive an explicit unsupported-arithmetic status.

The primary metric is the unweighted mean of the x-axis and y-axis R² values. Secondary outputs include MSE, MAE, descriptive clock-block metrics, and signed comparisons against all seven fixed reference streams. Those streams include source-only, calibration-only and balanced pooled ridge models. The strongest pooled control was selected from already exposed development references; it is not an independent new baseline choice. This panel provides no independent-animal generalization estimate.

Execution permits a single source file up to 64 KiB, 20 seconds from the start request, 1.75 CPUs, 3 GiB memory, two numerical threads, and a bounded 8 MiB output volume. An additional holder uses 0.25 CPU and 128 MiB. The only externally supplied data are the four declared public files. No network, repository, host socket, private target or operator reference mount is supplied. Runtime packages are those in the existing pinned scientific image; no installation is available. Only the required output is captured, with bounded regular diagnostics permitted by the shared collector. Your program is never imported on the host.

This is an exposed local development contract. Program removal before grading provides an execution boundary; it does not certify that a scientific interpretation is correct, that a program learned neural structure, or that access was blind. A constant-output control checks valid negative-score acceptance. The named-path probe checks only its 16 paths and declared schema, not exhaustive information noninterference.
