# FIND032: construct a native reference host

This directory now supplies a concrete **source recipe** for the direct Linux
reference route. It builds CPython at its final host prefix, installs the accepted
scientific dependency closure and emits the interpreter/path fields required by
the existing reference request. It does not extract or relocate an OCI image.

**No host build, package installation, import check, native process check or
scientific run has been performed for this delivery.** The original ten-file
container recipe remains byte-for-byte unchanged. Its older README statement
that the reference CLI/host setup is not implemented describes that original
recipe: the separately supplied reference source and this host builder are later
additions. Source completeness is distinct from demonstrated deployment.

## Supported host and source identities

Use a dedicated, otherwise unused Debian 12/bookworm **x86-64** machine or VM,
with Linux UID 0, the normal Debian package tools, GNU `timeout`, and the Debian
system Python 3.11 available to bootstrap construction. The system interpreter
runs the installer only; the scientific command uses the new exact CPython
3.11.11 executable. No other distribution, architecture, Python patch version,
or existing production host is selected.

The builder refuses a preexisting `/opt/find032-host`, foreign package
architectures, incomplete package state, modified packaged files, ambient global
pip configuration and preexisting local R packages. Every initially installed
package/version must occur in one of the three authenticated Debian snapshots.
For example, a newer Debian kernel or runtime package outside those indexes
causes refusal before package installation. A generic current Debian installation
is not assumed compatible. Provisioning the machine, its boot image and kernel
remains an administrator operation; this recipe does not claim a reproducible
machine-image identity.

`host-build.lock.json` binds all ten original recipe files and adds these primary
source identities:

- [CPython 3.11.11 source](https://www.python.org/ftp/python/3.11.11/Python-3.11.11.tar.xz):
  20,085,792 bytes, SHA256
  `2a9920c7a0cd236de33644ed980a13cbbc21058bfdc528febb6081575ed73be3`.
  The extent is recorded by the official Python directory listing. The digest is
  recorded in its official Sigstore bundle and the immutable build recipe below.
  The archive was not downloaded, and Sigstore signature verification was not
  performed during authoring; the builder verifies the selected archive digest.
- [docker-library/python recipe at
  ded42cf92d68bb878c8a1a9a4f3c86bad6023f4e](https://github.com/docker-library/python/blob/ded42cf92d68bb878c8a1a9a4f3c86bad6023f4e/3.11/slim-bookworm/Dockerfile):
  4,045 bytes, SHA256
  `7203d6da0c6edcd8bb4c5a6f9a75f05e11f753d47fd36d5c3737f62b8fa1bbd1`.
  The host build keeps its loadable SQLite extensions, optimization, strict
  option checking, shared libpython, LTO and ensurepip choices. It adds a fixed
  final prefix and explicit selected job count. It retains upstream's executable
  relink with `$ORIGIN/../lib`, avoiding a runtime dependency on an extra
  `LD_LIBRARY_PATH` entry for libpython.
- The existing Debian, bookworm-updates and Debian-security snapshots at
  `20250409T000000Z`, with the original three Release hashes; the existing 35
  exact Python artifacts; R 4.2.2 / Debian `4.2.2.20221110-2`; rpy2 3.5.11 in
  `RPY2_CFFI_MODE=API`; and BayesFactor 0.9.12-4.6 from CRAN's mirror commit
  `fd79157d60179efc68b36ea7b88ae7833ccedfd3`.

Compiler and development packages are the immutable upstream recipe's package
names plus the existing numerical recipe's packages. Their exact versions are
selected from the authenticated indexes by the future builder, **before** any
installation. Per-package versions are not fabricated here. The builder records
the original complete dpkg vector, rejects entries outside those indexes,
resolves the direct exact-version operands, retains the solver output, makes the
whole resulting package vector explicit, simulates that exact vector again and
requires the actual post-install dpkg vector to match. Unchanged transitive
packages therefore have explicit recorded versions too. The initial compatible
package vector can differ between hosts; byte-identical host builds are not
claimed.

APT uses a private configuration/list/cache directory beneath the new build
root. It does not overwrite `/etc/apt/sources.list`, delete the host's repository
files, use ambient extra repositories or disable signature checking. Only the
original historical Valid-Until exception remains. The Debian archive keyring
is the sole configured trust input. The builder's small cleartext/index adapter
checks the same pinned Release bodies inside its private APT lists; the original
`verify_apt_snapshot.py --mode apt-cache` intentionally remains unchanged and
continues to describe `/var/lib/apt/lists` for the original container recipe.

## Explicit future construction

Keep `build_host.py`, `verify_host.py`, `host-build.lock.json`, this guide and
`UPSTREAM_DOCKER_PYTHON_LICENSE.txt` beside the original ten recipe files. The
authenticated source directory must remain under actual exclusive writer
custody, or a read-only mount, for the entire construction and verification.
In particular, the unchanged accepted `verify_environment.py` later rereads its
lock by pathname. The new bounded FD captures authenticate their own reads;
they do not remove that inherited later-pathname race or replace source custody
with a boolean report. Do not edit or concurrently replace these files while
the build is using them.

The
root operator selects actual compute, storage and network resources first. From
that directory, on the selected disposable host, the construction shape is:

```text
/usr/bin/python3 -I -S -B /absolute/environment/build_host.py \
  --fresh-dedicated-host \
  --jobs SELECTED_BUILD_JOBS \
  --command-seconds SELECTED_PER_COMMAND_SECONDS \
  --total-seconds SELECTED_TOTAL_SECONDS \
  --log-bytes SELECTED_BYTES_PER_ORIGINAL_COMMAND_LOG \
  --download-bytes SELECTED_CPYTHON_AND_PYTHON_DOWNLOAD_BYTES \
  --minimum-free-bytes SELECTED_INITIAL_FREE_STORAGE
```

Replace the capitalized operands with positive integer selections, not copied
defaults. These examples have not been issued. CPython plus the 35 Python
artifacts total **112,165,797 download bytes**. APT downloads, the fixed Git
checkout, compiler/R build intermediates, installed files and logs are additional.
The `--download-bytes` counter covers the CPython/Python artifact downloader only;
it is not a total network quota. `--minimum-free-bytes` is an admission check,
not an enforced disk-size cap. A host-level build enclosure must separately
bound total disk, RAM, CPU and network expense. The recipe's command timeout and
log limits do not establish native scientific process qualification.

The builder invokes third-party compilation and installation, including CPython
optimization's build-time workload and R/rpy2 compilation. This is environment
construction, not a neural-data or benchmark run. It uses only fixed software
sources, no credentials, manuscripts, recordings, model weights or reference
answers. It retains the CPython archive/source and fixed BayesFactor checkout.
Python wheels and the rpy2 source archive are downloaded to private files and
checked by exact extent/hash, then installed from local files with no resolver
or isolated-build dependency fetch. The original requirements files are preserved;
the host creates local-file requirements for the exact same locked artifacts.

Every subprocess, including Debian version comparisons, has a retained command
record, merged original stdout/stderr log and result record. The parent captures
at most the selected log extent plus one overrun probe byte; it does not impose
that log limit on compiler-created artifacts. GNU `timeout` bounds the command
group; the parent can kill its unreaped owned group and uses an original
five-second retirement allowance inside the selected total interval. Blocking
software download operations also use finite socket timeouts and cooperative
checks of that interval; an external host enclosure supplies a hard whole-build
deadline. A
failure leaves the original partial source, downloads, package state and logs
in place. The builder does not retry, delete its tree, roll back APT or claim a
partial host is ready. Inspect the original failure and provision a separately
selected fresh host for another attempt. Package installation deliberately
changes this dedicated host; it is not a transaction over an arbitrary host.

## Runtime fields and concrete caller

The installed executable is the ordinary file
`/opt/find032-host/python-3.11.11/bin/python3.11`. The numerical root is
`/opt/find032-host/python-3.11.11/lib/python3.11/site-packages`. Construction
does not copy an image's `/usr/local` tree, create a venv activation dependency,
or substitute Debian's bootstrap interpreter for the scientific interpreter.

The final build invokes the **unchanged** `verify_environment.py` first with the
installed site's normal discovery and then through `verify_host.py` under the
real reference import shape `-I -S -B`. The latter appends only the explicit
numerical root and executes the exact digest-bound original verifier source.
Both paths check all 35 distributions and active requirements, the six numerical
imports, R 4.2.2, normalized exact BayesFactor version, its two API exports and R
dependencies. No data, fit or native owner is invoked by those checks.

On successful future construction, `logs/host-verification.log` includes the
actual interpreter byte/hash/mode pin and these request fields:

```json
{
  "python": "/opt/find032-host/python-3.11.11/bin/python3.11",
  "numerical_search_roots": [
    "/opt/find032-host/python-3.11.11/lib/python3.11/site-packages"
  ],
  "runtime_environment": {
    "R_HOME": "/usr/lib/R",
    "LD_LIBRARY_PATH": "/usr/lib/R/lib",
    "TZ": "UTC"
  }
}
```

`python_pin` must come from that actual constructed executable; no example pin
is supplied. An environment manifest is configuration evidence, not authority
to claim a native or scientific pass.

The actual caller is `source/find032_reference/process.py:run_owned`, through
`source/find032_reference/entry.py --mode run` and the production adapter. It
captures the selected executable, request and source graph, then runs its fixed
`--mode worker` command with `-I -S -B` and a fresh root-owned read-only cache
prefix. `worker.run` explicitly extends `numerical_search_roots` before the
unchanged full `find032.controller.reference_campaign` call. `PYTHONPATH`,
shell activation and site configuration are not replacements for those fields.
`schema.validate` requires `LD_LIBRARY_PATH == R_HOME/lib`; the built executable's
upstream-derived RUNPATH supplies its own libpython lookup. The accepted source
controls the rest of the child's environment and one-thread numerical settings.

## Native host preparation and remaining evidence

The direct reference route uses `NativeOwner`, not the participant Docker
transport. An administrator must supply a writable, real cgroup-v2 parent on
the selected host, with CPU, memory and PID controllers enabled for child
groups. The exact source creates two fresh sibling groups named
`GROUP_PREFIX-controller` and `GROUP_PREFIX-recovery`, writes their limits,
stops its own child before attaching it to `cgroup.procs`, then activates it.
The parent must support `memory.max`, `memory.swap.max`, `memory.peak`,
`memory.current`, `memory.events`, `pids.max`, `pids.current`, `cpu.max`,
`cpu.stat`, `cgroup.events`, `cgroup.procs` and `cgroup.kill` as actually used by
the source. No minimum kernel version is guessed in place of those interfaces.
`NativeOwner.prepare` does not mount cgroupfs, enable ancestor controllers,
move unrelated processes or create a systemd delegation. This builder also does
none of those actions. A delegated empty parent is a concrete runtime operand,
not a boolean supplied by a setup report.

Before the separately selected scientific invocation, prepare the root-owned
0700 protected output parent and a separate root-owned 0550 empty outer cache
directory; provide disjoint source, authentic-input and protected-output roots,
fresh run/final names, the exact complete input manifest, the captured source
manifest, and explicit normal/recovery capacities and original phase deadlines.
The public reference adapter supplies the source-bound outer invocation. The
request's `host_selection` retains the existing schema
`find032_original_host_owner_v1`; no new supervisor or readiness token is added.

Native qualification still requires observing the actual Linux owner lifecycle,
process and descendant retirement, stream EOF, failures and accounting on the
chosen host. Scientific qualification still requires eligible authentic inputs,
full reference competence, reviewed tolerances and numerical/method validation.
The full scope remains 33 participants, 132 recordings, 990 products, 52
comparison dispositions, three BF10 dispositions, six figures and the complete
1,087-file reference protocol. No subset, model call, paper-method change or
historical-environment parity claim is introduced by constructing dependencies.

## Notices

The adapted CPython build sequence is MIT-licensed upstream; retain
`UPSTREAM_DOCKER_PYTHON_LICENSE.txt`. No Python archive, R package, wheel or
image is distributed in this source addition. A later constructed host contains
dependencies with their own licenses, including GPL-licensed R/rpy2/BayesFactor;
retain their source and notices. The project's license does not relicense those
dependencies or establish image redistribution clearance.

The final log capture and final BUILD_COMPLETE publication are each followed by a check of the same original total endpoint. A late publication can leave a visible record before that check fails; the invoking caller must observe the actual command's natural-zero exit. A file alone is not evidence that the selected build completed within its interval. No clock is renewed and failed partial records are not removed.
