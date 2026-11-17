# Current-layout full runtime source

The retained full programme's `bootstrap.roster()` opens a removed
`authoring/delivery-20261105/neural060/REQUIRED_SOURCES.json` path. Its original
entrypoint therefore cannot capture the roster from the current repository
layout. The exact roster bytes are available in this task's `contracts/delivery`.

`materialize.py` repairs that locator in a newly materialized external runtime.
It authenticates the original 18-file runtime and the current roster before
writing anything, changes that one string in `bootstrap.py`, and emits a fresh
`SOURCE_MANIFEST.json` plus `RELOCATION.json`. The remaining 17 runtime source
files are byte-identical, including preparation, scorer, references, scheduling,
entrypoint, target-last admission, and process controls. The predecessor and
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
