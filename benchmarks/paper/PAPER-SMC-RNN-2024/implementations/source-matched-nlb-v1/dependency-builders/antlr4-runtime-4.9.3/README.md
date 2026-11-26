# ANTLR 4.9.3 source-wheel builder

This component builds the `antlr4-python3-runtime==4.9.3` dependency from its
authenticated source archive. OmegaConf 2.3.0 requires ANTLR 4.9.*, and the
inspected official release inventory supplied source distributions for that
range. The builder supplies a reproducible wheel-construction step for that gap.

The recorded experiment produced two byte-identical, 144,591-byte
`antlr4_python3_runtime-4.9.3-py3-none-any.whl` files:

```text
sha256:29502b806f612f7921d029d31144a2ac1a67cd9013829bcf7b1b46707a965fb9
```

This is standalone dependency-construction evidence. ANTLR was not imported or
installed into the neuroscience inference environment. Scientific runtime
dependency consistency, paper results and the Linux amd64 deployment remain
separate qualification work. The Python 3.9 preparation environment is unchanged.

## Inputs and checks

`SOURCE.json` identifies the exact 117,034-byte upstream source archive and its
SHA256. `TOOL_LOCK.json` identifies the three acquired build-tool wheels:
setuptools 75.8.0, wheel 0.45.1 and packaging 24.2, including their actual hashes,
wheel metadata and Python 3.11 no-extras dependency checks. Downloaded archives
and wheels remain external to this repository.

Create a dedicated input directory containing exactly:

```text
source.tar.gz
TOOL_LOCK.json
setuptools-75.8.0-py3-none-any.whl
wheel-0.45.1-py3-none-any.whl
packaging-24.2-py3-none-any.whl
```

Use the artifact URLs and hashes in the two JSON descriptors. Rename the source
archive to `source.tar.gz`, and copy `TOOL_LOCK.json` unchanged. The builder
checks input hashes before execution, checks every tool wheel's outer `RECORD`,
and keeps vendored metadata distinct from the outer distribution metadata.
It performs no network acquisition or dependency resolution.

## Run the two builds

The recorded builder was Linux arm64 with CPython 3.11.18. Its immutable image ID
was `sha256:04f230affa8877281a7d7351193a85323e4263c0df2d3c8d93033ed46a8d8e00`;
the corresponding repository digest is recorded in `SOURCE.json`. The following
command requires that image to be available locally. The image is deliberately
separate from the unresolved Linux amd64 scientific image.

Set these three absolute paths to your component checkout, dedicated inputs and
a new output directory. The output directory must be empty and writable by the
container's non-root user.

```sh
component_dir=/absolute/path/to/antlr4-runtime-4.9.3
input_dir=/absolute/path/to/antlr-inputs
output_dir=/absolute/path/to/new-antlr-output
mkdir "$output_dir"
chmod 0777 "$output_dir"

docker run --rm --pull=never --platform linux/arm64 \
  --network=none --read-only --user 65534:65534 \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --cpus=1 --memory=256m --memory-swap=256m --pids-limit=64 \
  --ulimit nofile=128:128 --ipc=none --log-driver=none \
  --tmpfs /work:rw,nosuid,nodev,noexec,size=67108864,mode=1777 \
  --mount "type=bind,src=$component_dir/build_antlr.py,dst=/harness/build_antlr.py,readonly" \
  --mount "type=bind,src=$input_dir,dst=/inputs,readonly" \
  --mount "type=bind,src=$output_dir,dst=/output" \
  --workdir /work --entrypoint python3 \
  sha256:04f230affa8877281a7d7351193a85323e4263c0df2d3c8d93033ed46a8d8e00 \
  -I -S -B /harness/build_antlr.py --inputs /inputs --output /output
```

The driver extracts each source tree independently and executes the reviewed
literal `setup.py` with only the pinned build tools. `SOURCE_DATE_EPOCH` is fixed
to 315532800. Python runs with isolated startup, so its hash seed is explicitly
reported as uncontrolled; no fixed-seed claim is made.

`first/` and `second/` each contain one wheel and a build log. `RESULT.json`
requires equal wheel bytes, the expected name/version and runtime marker,
`py3-none-any`, all `RECORD` hashes, and absence of native output. It also records
the actual environment. A failure preserves its logs and does not trigger a
retry. The saved experiment additionally used a bounded external supervisor
and verified removal of its owned container.

## Offline integrity controls

```sh
python3 -I -S -B "$component_dir/test_build_antlr.py"
```

These four generated-fixture controls cover vendored versus outer metadata,
`RECORD` corruption, native content hidden behind a pure-wheel tag, and path
traversal. They require no downloaded packages, container, backend build or
scientific data. Hosted CI runs these controls only; it does not acquire or
build packages. `SOFTWARE_BUILD.json` records the accepted two-build evidence
and its precise scope.
