# N055 role environments

These are concrete source recipes for the existing ten-person study. No image was built, package installed or imported, model loaded, feature computed or benchmark run while authoring them.

| Profile | Actual use | Interpreter and core packages |
|---|---|---|
| `ingestion` | Trusted original archive conversion, isolated from candidates, models and secrets | CPython 3.12.8; NumPy 2.4.6 |
| `controller` | Trusted controller, setup and host reference code; qualification-signature verification | CPython 3.12.8; NumPy 2.4.6; cryptography 44.0.2 with its cffi/pycparser closure |
| `campaign` | The existing shared campaign image: actor, holder, native reference, scientific tool and local text-model provider | CPython 3.12.8; NumPy 1.26.4; CPU Torch 2.5.1; Transformers 4.46.3 and the complete declared support roster |
| `../feature` | The unchanged AlexNet ReLU7 image-feature producer | Its separate CPython 3.9.18 / Torch 1.10.1 / torchvision 0.11.2 recipe |

The campaign has one `native_profile.image`. `DockerHost.argv_for` supplies it to the actor and holder and passes the same closure into `NativeProviders`. A model-provider setting does not select another image. Use the `campaign` image for this route; the smaller controller image is not a substitute for it. Postscore's separately owned daemon/profile can use the same campaign image identity with its own independently selected deployment and cache.

This separation also follows real compatibility constraints. Trusted ingestion directly uses NumPy 2's `_core` API. The fixed feature producer keeps its older Torch ABI. The model adapter uses CPU float32, local-only files and `trust_remote_code=False`. These new environment selections do not establish original-author environment parity or numerical agreement.

Each directory contains `ENVIRONMENT_LOCK.json`, an exact direct-URL acquisition lock and an offline `requirements.lock`. Wheel hashes and available byte counts come from captured primary release metadata. All three profiles contain concrete package selections: one, four and 24 distributions respectively. The campaign includes setuptools 75.6.0 because the Torch 2.5.1 source declares it for Python 3.12. Extras are not requested. The selected model must be supported by this Transformers version and have a complete locally usable tokenizer/chat-template and model namespace. Additional model-specific dependencies require a newly reviewed profile; they are not silently installed.

The CPU Torch index supplies its exact wheel hash but no size or wheel `Requires-Dist`. The attempted inferred metadata endpoint returned HTTP 404. That is not evidence that the wheel is absent. The source declaration supports the proposed dependency roster; the actual wheel's installed dependency checks and native imports remain mandatory during provisioning. Its acquisition bound is explicit rather than an invented observed byte count.

## Provisioning inputs and commands

Supply an immutable Linux x86_64 base reference, such as a separately selected `python@sha256:...` repository manifest digest, with CPython 3.12.8. No usable base image, digest or host interpreter is asserted by this package. The exact base/archive identity, build engine and output image identity are recorded as deployment operands. A provided base must supply the required system libraries; native API inspection below refuses if the selected packages cannot load. Rebuilding the package set is not a promise of byte-identical Docker config timestamps.

Run provisioning only in its separately selected resource envelope. The following are future operator commands, not commands executed in this source delivery. Run the acquisition command on a selected Linux x86_64 CPython 3.12.8 build host so pip validates the selected wheel ABI. Use a fresh context and an empty wheelhouse. `ROLE` is one of `ingestion`, `controller` or `campaign`; `ENVIRONMENT_ROOT` is the installed `environment-v1` directory; `CONTEXT` is a fresh absolute directory.

```sh
mkdir "$CONTEXT"
mkdir "$CONTEXT/wheelhouse"
cp "$ENVIRONMENT_ROOT/roles/Dockerfile" "$CONTEXT/"
cp "$ENVIRONMENT_ROOT/roles/inspect_environment.py" "$CONTEXT/"
cp "$ENVIRONMENT_ROOT/roles/verify_wheels.py" "$CONTEXT/"
cp "$ENVIRONMENT_ROOT/feature/feature_environment.py" "$CONTEXT/"
cp "$ENVIRONMENT_ROOT/roles/$ROLE/ENVIRONMENT_LOCK.json" "$CONTEXT/"
cp "$ENVIRONMENT_ROOT/roles/$ROLE/requirements.lock" "$CONTEXT/"
PIP_DISABLE_PIP_VERSION_CHECK=1 python -I -B -m pip download \
  --no-index --no-deps --only-binary=:all: --require-hashes \
  -r "$ENVIRONMENT_ROOT/roles/$ROLE/requirements-artifacts.lock" \
  -d "$CONTEXT/wheelhouse"
docker build --platform linux/amd64 --pull=false --network=none \
  --build-arg BASE_IMAGE="$BASE_REFERENCE" --tag "$OUTPUT_TAG" "$CONTEXT"
docker image inspect --format '{{json .Id}}' "$OUTPUT_TAG"
```

Direct artifact acquisition is the only network step shown. Its transfer/storage/deadline envelope is an operator responsibility; `pip download` is not presented as a hard byte-capped transport. No dataset, model weight or feature checkpoint is included. Inside the build, `verify_wheels.py` checks the exact namespace and complete hashes before offline installation, `pip check` verifies installed dependencies, and `inspect_environment.py --capabilities` checks package versions and actual required APIs without loading a model or data. Failure at any step leaves provisioning incomplete.

`verify_wheels.py` captures the exact reviewed feature helper source and uses only its ordinary-file ownership/hash functions. It does not use that helper's feature-version constants or import native feature packages. The 2 GiB limit applies to explicit wheel hashes, with growth detection; it is not a bound on Docker, pip, interpreter, ZIP or native-library internal I/O or memory. Provisioning is subject to its own complete process/resource envelope.

Docker's `.Id` is the image config identity consumed by the existing native profile. A repository manifest digest is a different identity and must not be substituted into `native_profile.image`. Retain base and output observations separately. Cache the admitted output in the exact selected native daemon/cache before execution; runtime remains `--pull never` and network-disabled.

For a trusted host environment, the same controller lock can be installed into a separately selected isolated CPython 3.12.8 environment, with actual executable identity captured. Do not use a dependency recipe to invent a host/cgroup qualification. The original `postscore_gated_clone.c` remains the only launcher source: compile it in the selected Linux environment using the existing `cc -std=c11 -O2 -Wall -Wextra -Werror` command and bind the actual compiler/source/binary identities. This package adds no launcher or daemon controller.

## Bind the resulting operands

The original operator, campaign and role-host schemas still require source identity, actual interpreter and Docker binaries, image config identity, resource policy, deployment/cgroup ownership, complete local model namespace/configuration and independent qualification. `inspect_environment.py` produces an environment observation, not a qualification receipt. It does not manufacture signatures, reserve compute, activate a benchmark or admit a model artifact.

The fixed-feature guide separately binds the exact original extractor and torchvision AlexNet source identities, the selected eight wheels, and the Python 3.9 bootstrap compatibility successor. Full checkpoint SHA-256/size, selected base images, actual installed artifacts and genuine independent qualifications remain provisioning operands. All numerical definitions, image order, cohort, reference methods, learning splits, protected-target barriers and scientific task bodies remain unchanged.
