# Current executor source and input roles

The [cerebellar executor](../implementations/cerebellar-executor) checks its declared
file roles before capturing commitment, procedure, candidate source or public
input bodies. The request and authority records must first be authenticated to
learn those roles.

Candidate sources, public inputs, control records, private evaluator operands and
the fresh execution output tree must have distinct, non-nested locations. The
check normalizes paths, rejects symbolic links and checks existing filesystem
identities for hard-link aliases. A single ordinary source file may serve several
candidate phases. Its bytes still require the original pre-data commitment.

This prevents a malformed operator request from naming a protected target file
as candidate source and copying it into `/procedure`. It does not prove that
otherwise distinct source files lack copied answers, establish source provenance,
or protect against concurrent changes by an untrusted host. Authentic input
preparation, independent authority and native isolation remain prerequisites.

The historical package `SOURCE_MANIFEST.json` remains unchanged and authenticated.
The separate [current descriptor](../../../integrity/current-closures/trust-cerebellar/SOURCE_MANIFEST.json)
retains the same 15 members and binds the reviewed role-separation repairs,
transport permission repair and stable count-scorer adoption. The candidate view
builder, candidate contract and phase worker retain their original identities.
The scorer is byte-identical to `count-scorer-v3/score.py`; the historical
manifest continues to identify its predecessor. The new current source digest
must be selected in any future operator authority; an authority bound to the old
source digest does not authorize the changed implementation.

From the repository root, inspect the current source without reading a dataset or
running a candidate:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-030/implementations/cerebellar-executor/entry.py inspect
```

For a standalone package copy, also supply an unchanged copy of the current
descriptor. Its exact bytes remain pinned by the entry script:

```sh
python3 -I -S -B /ABSOLUTE/cerebellar-executor/entry.py inspect \
  --current-manifest /ABSOLUTE/current-cerebellar-source.json
```

The same optional `--current-manifest` locator applies to the existing `run`
command. It selects the location of already pinned metadata; it grants no run
authority and changes none of the required request, authority, resource or
qualification checks described in the retained package guide.

Generated role-separation, source-tamper, portable-copy and stale-bytecode controls
run with:

```sh
python3 -I -S -B -m unittest discover -s tests/benchmarks -p test_cerebellar_role_aliases.py -v
```

These controls use invented fixtures. They do not establish scientific or native
qualification, authentic-data agreement or a model result.
