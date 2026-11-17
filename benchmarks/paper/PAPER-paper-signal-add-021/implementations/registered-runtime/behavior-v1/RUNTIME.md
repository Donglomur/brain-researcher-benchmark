# Exact runtime and remaining deployment requirements

The accepted TMS runtime is **CPython 3.12.16, Linux arm64/v8**, from `docker.io/library/python:3.12.16-slim-bookworm`, with exact local image/config ID:

`sha256:4703adf8fdd93b1441114e4f87ce2c62f7373fc5f88bda6a546c551625bcc71c`

The pinned upstream architecture leaf is:

`docker.io/library/python@sha256:df540bfd30bd380e89a349611ce42aa67bcb542d58c047706616eb6ba2f86a1b`

The reviewed upstream [Dockerfile revision](https://github.com/docker-library/python/blob/3d7e95597e56a415d9e4abc0f15877e005d2cb2e/3.12/slim-bookworm/Dockerfile) identifies the recipe. Obtaining an image is a separate explicitly selected provisioning operation; none of the exported commands pulls or builds it. An upstream digest, an image ID, and an accepted runtime-evidence record are separate requirements. A local build is not assumed to reproduce the exact upstream image ID.

The public PFC/DMFC runtime work concerns a different image and software stack. Its availability or qualification does not satisfy this TMS image commitment. Changing IMAGE, the catalog, host executable pin, convention fingerprints or runtime evidence is a new reviewed runtime change, not relocation. The owner uses `--pull=never` and refuses a different image.

The inherited host contract is Darwin and exact **CPython 3.11.6** with the executable identity in the owner source, `/usr/local/bin/docker`, and candidate user `501:20`. The user setting is an inherited sandbox constraint, not an exported identity of an operator. Actual socket path/device/inode/owner/mode/link-count values are absent from this package and supplied in private configuration. An arbitrary Python 3.11 patch or another host platform is not admitted automatically.

Before any candidate execution, the inherited owner checks capacity, source closure, complete asset pins, exact daemon identity and image admission; it then runs a complete invented convention fixture in the admitted candidate image. This preserves the explicit host 3.11.6 versus candidate 3.12.16 distinction. The fixture checks the complete 315/18/270 construction and declared random/arithmetic conventions. It does not prove universal floating-point parity or authenticate an unobserved runtime.

The package does not include the image, protected reference, authentic files, inherited image receipt/review, official-code review, behavior reference review/acceptance or source-origin binding records. Their opaque commitments are in the catalog. A custodian must supply the exact authorized records privately, plus a fresh independently accepted rendered-source and selected-runtime record. Fabricating records or changing their commitments is not a supported setup step. Public acquisition of the CSV alone therefore does not make this package externally runnable.

These are the remaining provisioning gaps, not missing implementation of the task, scorer or owner. `plan`, `build` and `select` read source/metadata, emit a private package and exact invocation, and never launch it. Source control success and the historical selected-host construction do not admit a fresh host or make a submission ready.
