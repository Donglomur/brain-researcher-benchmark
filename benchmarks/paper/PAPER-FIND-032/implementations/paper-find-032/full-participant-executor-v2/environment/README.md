# FIND032 numerical environment construction

This source recipe supplies the numerical environment for the existing complete
FIND032 paper-reproduction executor. It preserves NumPy1.23.5, SciPy1.10.1,
scikit-learn1.2.1, MNE1.5.1, matplotlib3.7.0 and BayesFactor0.9.12-4.6.
The prospective corrected-methods runtime selects CPython3.11.11, Debian bookworm,
R4.2.2 and rpy2 3.5.11. These latter choices do not recover the original paper's
historical environment.

**The recipe has not been built or executed.** The package includes concrete
build and import checks; no passing check, image digest, native qualification or
scientific result is claimed. Original benchmark source is unchanged.

## What is supplied

- `Dockerfile` builds two named targets from one numerical environment:
  `candidate` and `reference-environment`. Both candidate arms must use the exact
  same built candidate image identity. The reference target supplies dependencies
  for a separately selected trusted reference command.
- Three requirements files select35 exact Python artifacts:34 Linux CPython3.11
  or universal wheels and the hash-locked rpy2 source distribution. Bootstrap
  tooling is installed first, runtime wheels second and rpy2 last. No unresolved
  pip dependency or isolated build dependency is fetched by a resolver.
- `environment.lock.json` records artifact SHA256 values, complete declared
  Python dependency requirements,37 selected active dependency edges,251 excluded
  optional/platform requirements, the exact base-image digest and Debian Release
  metadata identities. The five existing Python scientific versions remain exact.
- `verify_apt_snapshot.py` checks all three repository Release hashes and then
  checks the actual APT-cached signed index cleartext against those same hashes.
  APT signature verification remains enabled. The dated snapshot's expired
  Valid-Until field is deliberately disabled in `sources.list`.
- `verify_environment.py` checks the actual installed35-distribution closure,
  active dependency constraints, interpreter and architecture, imports of all six
  numerical modules, R4.2.2, the normalized exact BayesFactor version, required R
  package minimums and the two BayesFactor API exports. It performs no fitting or
  neural-data operation. Its report explicitly leaves qualification false.

The source metadata reports92,080,005 bytes of selected future Python package
downloads. That figure excludes the base image, APT packages, Git source, native
build intermediates and installed size. It is not a build-resource estimate.

## Dependency provenance and lock semantics

The base is the official Python image's exact Linux/amd64 manifest
`sha256:a8e0a3090316aed0b11037aac613aef32fb1747dcc1dcb5c0f6c727a0113a07f`,
observed for `3.11.11-slim-bookworm`. The [Docker Hub tag metadata](https://hub.docker.com/v2/repositories/library/python/tags/3.11.11-slim-bookworm)
also identifies the index digest; the Dockerfile uses the platform digest so it
cannot silently select another architecture.

Python hashes and release requirements come from version-specific
[PyPI JSON metadata](https://docs.pypi.org/api/json/) and the selected files'
PEP658 metadata. Where release JSON omitted dependency fields, the actual wheel
metadata supplied them. No wheel or source archive was downloaded for authoring.
The [rpy2 3.5.11 release](https://pypi.org/project/rpy2/3.5.11/) supplies the exact
sdist hash; its [release build metadata](https://github.com/rpy2/rpy2/blob/RELEASE_3_5_11/pyproject.toml)
requires setuptools>=61, wheel and cffi>=1.10.0 on this platform. The selected
bootstrap and runtime locks satisfy those requirements. `RPY2_CFFI_MODE=API`
makes the R native bridge build explicit.

APT and distro R dependencies use a **repository snapshot lock**: the immutable
base plus the exact dated Debian, bookworm-updates and Debian-security index
identities determine the available package graph. The recipe installs R's exact
Debian package version and the complete named BayesFactor dependencies from those
indexes, with recommendations disabled. It records the actual full installed
Debian and R package manifests during a future build. This package does not
invent unobserved per-package R/OS version or binary hashes. The signed indexes
carry package hashes; their own SHA256 identities are in the lock. See the
[Debian snapshot service](https://snapshot.debian.org/) and the captured
[R source-package version metadata](https://snapshot.debian.org/mr/package/r-base/4.2.2.20221110-2/binpackages).

BayesFactor uses CRAN's Git mirror commit
`fd79157d60179efc68b36ea7b88ae7833ccedfd3`, with the
[exact release DESCRIPTION](https://github.com/cran/BayesFactor/blob/fd79157d60179efc68b36ea7b88ae7833ccedfd3/DESCRIPTION)
declaring0.9.12-4.6. The Dockerfile fetches that commit, verifies FETCH_HEAD,
checks it out and invokes `R CMD INSTALL`; it does not select a floating tag or
run an online R dependency resolver. The source checkout remains in the image.
The selected identity is that Git source tree, not a claim of byte equality with
CRAN's compressed tarball.

All software source identities are fixed. A future image build must still be
observed: compiler output, installation timestamps and build-system behavior
have not been measured, so byte-identical images across builds are unestablished.

## Future build and handoff

After the enclosing operator selects a build host, storage, network and build
resource limits, use this directory as the build context on Linux/amd64:

```text
docker build --platform linux/amd64 --target candidate --tag <selected-local-tag> .
docker build --platform linux/amd64 --target reference-environment --tag <selected-reference-tag> .
```

These are example future invocations; neither command was issued here. Building
executes third-party installers, compilers and the included import checks and
downloads software from the fixed sources. It reads no benchmark data. The
`.dockerignore` admits only the finite recipe, lock and check files; no parent
workspace, dataset, answer, participant programme or benchmark implementation is
included in either image. No image is pushed by these commands.

Retain the original build output and nonzero failures. On a successful build,
retain `/opt/find032-environment/{apt-remote.json,apt-cache.json,dpkg-installed.txt,environment-imports.json}`
and measure the actual image identity. Supply that actual pinned image identity
to the complete executor, together with its separately selected runtime limits.
The source-proposed digest in this package is the base image, not the unbuilt
candidate image. Do not put it into the candidate-image field as a substitute.

The image explicitly installs the timezone database and defaults to UTC, the
noninteractive Agg plotting backend and one
BLAS/OpenMP thread. These are explicit prospective environment choices; they are
not evidence of historical numerical parity. Both arms share them. No health
check, implicit volume, task-specific entrypoint, credentials or hidden answer
is added. The container transport still supplies the participant command and
the authorized paper/code/data views under its existing isolation rules.

This recipe does not implement the remaining trusted reference-production CLI,
reference process ownership or Linux host setup. The internal full producer
`find032.controller.reference_campaign` already exists; connecting it to a
protected production command is a separate implementation task. Docker/cgroup
host admission, authentic input eligibility, exposure rights, independent
reference competence, numerical parity and grading tolerances remain explicit
requirements. None is replaced by an image import-check report.

## Rights

This recipe distributes no upstream wheel, R package archive, image layer,
manuscript or dataset. A future built image contains software with its own
licenses: the project's license does not relicense those dependencies. In
particular, R/rpy2 and BayesFactor have GPL terms. Keep their notices and the
retained source/provenance when reviewing any image redistribution. No overall
redistribution clearance or scientific-readiness claim is made here.
