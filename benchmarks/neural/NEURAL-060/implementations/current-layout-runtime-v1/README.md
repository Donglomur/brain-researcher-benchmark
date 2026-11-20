# Current-layout full runtime source

The retained full programme's `bootstrap.roster()` opens a removed
`authoring/delivery-20261105/neural060/REQUIRED_SOURCES.json` path. Its original
entrypoint therefore cannot capture the roster from the current repository
layout. The exact roster bytes are available in this task's `contracts/delivery`.

`materialize.py` repairs that locator in a newly materialized external runtime.
It authenticates the original 18-file runtime and the current roster before
writing anything, changes that one string in `bootstrap.py`, and repairs one exact inspect comparison
in `engine.py`. Docker can report the enabled security option as
`["no-new-privileges:true"]` even when creation requested `["no-new-privileges"]`.
The materialized validator admits those two one-element representations; missing,
false, malformed, duplicate and extra options remain refused. In particular,
`label=disable` is not added to this runtime's allowed options. All other host
configuration, resource, namespace, image and process checks remain unchanged.

It emits a fresh `SOURCE_MANIFEST.json` plus a version-2 `RELOCATION.json` that
records both changed source pins and the explicit inspect compatibility change.
The remaining 16 runtime source files are byte-identical, including preparation,
scorer, references, scheduling, entrypoint and target-last admission. The predecessor and
its historical receipts remain unchanged.

```sh
python3 materialize.py --repo /absolute/current/repository --output /absolute/external/fresh-runtime
```

Both arguments must be canonical absolute paths with ordinary directory
ancestry. The output must be fresh and outside the repository. A failed write
may leave a partial source tree requiring inspection; the tool neither
overwrites output nor retries. The output is a complete source tree that the
unchanged `entry.py` can authenticate using the **new** manifest and bootstrap
pins in `RELOCATION.json`. The new pins require independent selection before
any execution; historical qualifications do not transfer. The roster itself
keeps its original identity.

This component only reads source code and the public source roster. It does not
prepare recordings, run estimators, contact providers, expose private targets,
install a central route, or create execution authority. The retained central
integration still contains historical bindings and requires its own reviewed
successor. Full 29-session data preparation, environment and process custody,
reference competence, and all scientific execution remain unqualified.

The original target remains all 50 measured absolute-speed samples for every
eligible movement in all 29 evaluation sessions, with all native units, official
within-session splits, 13-mouse weighting, and unchanged nuisance/joint/shift
conditions. This repair cannot establish direct or viewer interpretation.

`test_materialize.py` exercises the actual predecessor failure, successor roster
admission and captured imports, complete source identity, deterministic output,
entrypoint help and inactive-authority refusal, drift rejection, and path/overwrite failures. All fixtures are
copies of public source files, with no recordings or scientific calculations.
Run it through the coordinator's reviewed lightweight test pool.

The focused source-only inspect regression command is:

```sh
python3 -I -B test_inspect_security.py --repository /absolute/current/repository
```

Run it through the coordinator's reviewed lightweight test pool. It materializes
one source closure, calls the actual predecessor and successor inspection
functions on invented configuration objects, demonstrates the original refusal,
and checks invalid security settings plus unchanged configuration refusals. It
compares all 18 source members against the predecessor and reports the emitted
engine/manifest pins. No Docker daemon, data, model or numerical dependency is
used. These source controls do not qualify an actual daemon or scientific run.
