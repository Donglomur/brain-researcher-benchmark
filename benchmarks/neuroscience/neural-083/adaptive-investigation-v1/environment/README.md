# Prospective NEURAL083 numerical environment

These source recipes supply a minimal numerical dependency closure for the real
preparation and Docker-tool paths: CPython 3.11.11, NumPy 1.23.5, SciPy 1.10.1,
scikit-learn 1.2.1, joblib 1.2.0, threadpoolctl 3.1.0, pip 23.1.2,
setuptools 67.6.1 and wheel 0.40.0. They are explicit prospective environment
choices derived from already authenticated project metadata. They are not a
recovery of the paper's historical environment or evidence of numerical parity.

The eight wheel artifacts total 64,263,147 bytes. Their exact URLs, extents and
SHA256 values are in the lock. The immutable official Python Linux/amd64 image
is selected by platform manifest digest. Debian libgomp/libstdc++ runtime packages
come from the same three exact signed snapshot indexes used by the accepted
environment source. APT signature verification remains enabled; only the
snapshot's historical Valid-Until expiration is disabled. Actual installed APT
versions are retained during a future image build. No wheel, image, package,
model or archive has been downloaded or installed for this source delivery.

## Build the numerical tool image

Select a Linux/amd64 Docker build host, storage/network allowance, compiler-free
wheel installation resources and a build observation deadline. In this directory:

```text
docker build --platform linux/amd64 --tag SELECTED_LOCAL_IMAGE_TAG .
docker image inspect SELECTED_LOCAL_IMAGE_TAG
```

These are future commands, not executed evidence. Retain the original complete
build output and any failure. The build runs hash-locked, dependency-resolver-free
wheel installation, `pip check` and the included actual import verifier. It does
not load neural data or fit a model. Record the resulting **image Id** and supply
that `sha256:...` value to the task's `image` field. The base-image digest is not
a substitute for this unbuilt final image identity.

The native transport requires a cached image, never pulls on demand, overrides
its entrypoint with `python`, and inspects the actual command, image, UID 65534,
readonly mounts, no network, resource limits, capabilities and container/volume
ownership. This Dockerfile adds no volumes, healthcheck, server, task source,
answer, recording or credential. `.dockerignore` includes only this finite
environment recipe. The same selected image is used across compared arms.

## Install the preparation interpreter environment

The inherited preparation parent launches its actual `sys.executable`; its child
deliberately removes `-S` to discover NumPy/SciPy. Thus an existing host Python
with only stdlib is insufficient. On a dedicated Linux/amd64 host, supply an
existing, separately installed CPython **3.11.11** interpreter and compatible OS
runtime libraries, then create a fresh venv with copies. This recipe installs
the numerical environment; it does not compile the host interpreter, change host
APT configuration or provision Docker. Those are concrete platform prerequisites.

With explicit absolute paths and an absent venv destination:

```text
/SELECTED/CPython3.11.11 -I -S -B /absolute/environment/verify_environment.py --bootstrap --lock /absolute/environment/environment.lock.json
/SELECTED/CPython3.11.11 -I -B -m venv --copies /FRESH/neural083-env
/FRESH/neural083-env/bin/python3.11 -I -B -m pip --isolated install --require-hashes --no-deps --only-binary=:all: -r /absolute/environment/requirements-bootstrap.txt
/FRESH/neural083-env/bin/python3.11 -I -B -m pip --isolated install --require-hashes --no-deps --only-binary=:all: -r /absolute/environment/requirements-runtime.txt
/FRESH/neural083-env/bin/python3.11 -I -B -m pip --isolated check
/FRESH/neural083-env/bin/python3.11 -I -B /absolute/environment/verify_environment.py --lock /absolute/environment/environment.lock.json
```

Run the metadata helper and inherited preparation operator using that venv's
actual executable. The generated command uses the invoking interpreter, and the
owned preparation child consequently discovers this exact environment. Do not
run setup under a different interpreter and assume shell activation will change
the emitted command later. `--bootstrap` checks version/platform only and does
not qualify dependencies; the final check requires the exact eight installed
distributions and imports the actual SciPy/NumPy/sklearn modules used by the
captured source. It performs no fitting. Global pip configuration or additional
installed distributions are unsupported for this fresh environment. Keep the
authenticated source/lock directory read-only or under exclusive writer custody
throughout installation and checks.

The host commands are explicit installer invocations, not an automatic benchmark
run. Select and retain their resource envelope and original logs. A failed or
partial installation is not a usable environment. No hard process/descendant or
whole-host resource guarantee is inferred from these commands or their import
output. The real task's native ownership and full scientific evidence remain to
be qualified separately.

## Model service is a separate dependency

This environment deliberately contains no LLM server or model weights. The real
`local_chat_provider.py` HTTP transport is provided; a compatible server's
implementation/version, model identity, weights, hardware and bounded lifetime
remain unselected software/deployment inputs. They cannot be replaced by a
Boolean admission file or by the numerical image. See the main setup guide for
the exact accepted protocol. Frozen-program and decoder-alone modes make no
model request and need no model server.

This source addition redistributes no upstream artifacts. A future image or venv
contains third-party software under its original licenses; retain their notices.
The project license does not relicense those dependencies.
