# PFC independent analytical baseline

This standard-library Python component reconstructs observed counts and exact
conditional moments for a supplied fixed map of categories and ROI memberships.
It is a method-assisted mathematical reconstruction baseline, with the method
specified in advance. Its scope is downstream of learning the map and selecting
the representations. Whole-animal deletions measure sensitivity to the supplied
cohort; they are not confidence intervals.

This component makes no full-paper reproduction, state-of-the-art, LLM
performance, or measured code-assistance claim. It includes no authentic data,
reference outputs, benchmark scores, or third-party implementation. The tests
contain invented fixtures only. This component is separate from the conditional
null kernel component and does not import it.

## Computation

Each family has its own eligible population: a unit is included exactly when its
label slot for that family is nonnegative. Eligible units are stratified by their
effective-task string. Within a stratum, independently and uniformly permuting
ROI and category labels while preserving both margins gives a hypergeometric
cell overlap. With population size `n`, ROI margin `r`, and category margin `c`:

```text
mean     = r*c/n
variance = r*c*(n-r)*(n-c) / (n*n*(n-1))
```

An empty stratum contributes zero. Singleton strata and empty or complete
margins have zero variance. The independent strata contribute additive means
and variances. The calculation uses integer counts and `fractions.Fraction`;
it generates no random permutations and assumes no independence between cells,
families, or deletion cases.

The full case is followed by one case deleting each entire animal, including
all of its recordings and every family. The remaining margins determine new
conditional moments. Every original family row and all eight category columns
remain present, including unsupported rows and all-zero deletion contexts.

## Runtime and invocation

Use Python 3.11 or 3.12 with only the standard library. From this directory:

```sh
python3 -I -B solution.py --packet participant-packet.json --output submission.jsonl
```

The ordinary-file mode creates the output exclusively and refuses an existing
destination. To emit the same JSONL on standard output:

```sh
python3 -I -B solution.py --packet participant-packet.json --output -
```

Diagnostics go to standard error. The program limits emitted output to 128 MiB
and retains at most one complete case and its serialized line. An error after
writing begins can leave a partial stream or file; such output is incomplete.
The program reads the one named input packet and writes the selected output.

## Input contract

The executable requires a UTF-8 JSON object with schema
`PFC_FULL99_FIXED_MAP_PACKET_V1` and these fields:

| Field | Contract |
| --- | --- |
| `animals` | Ordered array of 68 unique fitting-animal strings. |
| `families` | Ordered array of 12 objects, each with unique string `key` and an ordered array of unique string `labels`. |
| `records` | Array of 99 recording objects with unique string `id`, nonempty string `animal`, and string effective `task`. Recordings with zero fitting units may name animals outside `animals`. |
| `units` | Array of 19,186 fitting-unit objects as described below. |
| `contexts` | Array of 16 fixed context descriptors. The cell computation does not consume their contents. |
| `historical_diagnostics` | Optional provenance metadata; unused by the computation. |

Each unit has a unique string `id`, a declared `recording`, an `animal` from the
fitting roster, an effective `task` string, an integer `category` from 0 through
7, and exactly 12 integer `labels` slots. A label is `-1` for ineligibility or a
zero-based row index in the corresponding family's label array. Its animal and
task must exactly match its recording descriptor. All units have weight one.

The executable validates the fixed cohort dimensions. The invented tests use
the same computation with smaller fixtures through an internal validation
option; that option is not exposed on the command line. No authentic packet
is distributed with this component.

## Output contract

The UTF-8 JSONL contains one header followed by exactly 69 complete case lines.
The header has exactly these fields:

```text
schema:        PFC_CONDITIONAL_CASES_V1
packet_sha256: SHA-256 of the exact original input bytes
cases:         ["full", "without:<first animal>", ..., "without:<last animal>"]
```

Each case has exactly `case` and `families`. Its 12 family objects retain the
input order and have exactly `key`, `counts`, `mean`, and `variance`. Each matrix
has one row per declared family label and eight category columns. `counts`
contains nonnegative integers; each mean and variance is a reduced rational
`[numerator, denominator]` with positive denominator. Zero is `[0, 1]`.

## Invented-data tests

Run the complete 12-test suite from this directory:

```sh
python3 -I -S -B -c 'import sys, unittest; sys.flags.optimize == 0 or sys.exit("Tests require optimization disabled"); sys.path.insert(0, "."); suite = unittest.defaultTestLoader.loadTestsFromName("test_invented"); suite.countTestCases() == 12 or sys.exit("Expected exactly 12 tests"); result = unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())'
```

The explicit local import path allows the isolated interpreter to load the
copied `solution.py` and `test_invented.py` together. The fixtures are embedded
in the test module; no data files, installations, network access, or numerical
libraries are needed.
The command requires optimization to be disabled and exactly 12 discovered
tests. The tests use `unittest` checks rather than Python `assert` statements.

The tests enumerate finite overlaps for populations of size zero through six,
check additive stratum moments and family eligibility, and exercise animal
deletions, unsupported axes, empty populations, zero-fitting recordings outside
the roster, stdout dispatch, exclusive file creation, and the output byte cap.
The source was projected without executing these tests; the included tests do
not constitute a reported pass or scientific benchmark result.

The included path-filtered GitHub Actions workflow is configured to run this
same command with a 35-second timeout and a three-minute job limit. It retains
complete stdout, stderr, and exit status for seven days and propagates test
failure. The workflow uses pinned actions and read-only repository permission.
