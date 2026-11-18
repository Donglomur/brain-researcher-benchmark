# NEURAL-079 source-map staging

`render_source_maps.py` implements the previously manual source-map portion of
the adjacent `full-natural-video-encoding-v1/RECONSTRUCTION.md`. It authenticates
the exact public projection and historical installed manifest, verifies all101
published source members, then renders the55-module effective map and72-member
runtime closure for a new absolute destination. It does not import or execute
any archived Python, shell or scientific code.

The closure receives the actual new effective-manifest identity and the588-byte
public site-script template identity. It cannot retain the historical537-byte
job-script identity or the old path-dependent manifest hash. All98 unchanged
algorithm/source bodies retain their original bytes; both original manifests
remain unchanged in a separate provenance directory. The site script is kept
as an unexecuted template requiring `N079_SITE_HOME`; its Slurm resources,
environment and native numerical compatibility remain unqualified.

Run an in-memory construction check:

```sh
python3 -I -S -B render_source_maps.py \
  --archive /absolute/path/full-natural-video-encoding-v1 \
  --destination /absolute/private/new-neural079-stage
```

The default authenticates and renders without writing a staging tree. Add
`--materialize` only when an operator has selected that source construction.
The destination must be fresh, outside the original archive, with an existing
ordinary parent. This writes a source-only tree with at most2MiB of file bodies;
it neither downloads data nor configures a benchmark run. Input source reads
are limited to2MiB and individual members to128KiB. Roots/ancestors and source
members must not be symlinks. Duplicate/case-colliding/traversing paths and
changed, omitted or extra source identities fail closed.

`SOURCE_PACKAGE.json` is published last: its complete bytes are written,
flushed and fsynced under a private temporary name, then atomically linked to
the final name without replacement. Failure before that link leaves no new
final marker; partial source files may remain. The link is the commit point.
Cleanup failure after the link returns an explicit warning while retaining
the complete marker and completed status; an owned `.pending` name may remain.
An interruption after the commit point can likewise leave a complete marker.
The helper never removes or overwrites an existing destination. The marker
identifies construction completion only, not scientific qualification. This
is ordinary trusted-operator filesystem handling, not protection against an
adversary concurrently replacing directories or a power-loss durability claim.

## Remaining work

This component addresses map rendering and records actual source identities.
It does **not** regenerate every consuming module/source/qualification/registry
binding, resolve the ten deferred cross-task exposure dependencies, configure
the central source selector or establish Linux isolation/provider/observer
roles. Those dependencies are explicit in the staging receipt and must be
resolved before execution. No packaging, execution, scientific or submission
readiness field is promoted by this component.

NEURAL-079 retains its original video-to-EEG encoding target: six known people,
48 sessions,1000 training videos,102 held videos,127 channels by1800 time
samples and all17 S3D outputs. This is not direct neural-waveform interpretation;
showing held EEG would expose the target. The full programme and scorer remain
unchanged, as do the separation of literal whole-session native normalization
from prospective fit-only grading and all authentic-data/reference gates.

## Validation

`test_render_source_maps.py` authenticates the actual public source archive
once and renders maps only in memory, then exercises malformed markers, path
escape/collision, changed module pins/bodies, missing/duplicate closure members,
source symlinks, deterministic relocation, fresh output and interrupted output
with tiny generated files. It never loads EEG, features, targets or model
weights. These checks establish software/source-map behavior only.

After publication, the test discovers the archive as its adjacent sibling.
Private construction checks may set `N079_TEST_ARCHIVE` to that same existing
archive's absolute path; this does not weaken its hard-coded manifest pins.
The integrator must enroll the command as a task component test. No existing
central workflow or registry is modified by this private package.
