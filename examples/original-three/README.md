# Original scientific-judgment examples

These three Harbor-format tasks come from the original benchmark repository.
Their task IDs, scientific prompts, reference solutions and scorers are preserved.
They are separate from the newer [paper and neural tracks](../../benchmarks/README.md).

| Example | Scientific question |
| --- | --- |
| [GRADIENT-001](GRADIENT-001/) | How robust is an interpretation of the principal connectivity gradient? |
| [SOCIALBRAIN-001](SOCIALBRAIN-001/) | How does global-signal regression affect a reported social-brain anticorrelation? |
| [DEVCONN-001](DEVCONN-001/) | How does head motion affect a developmental connectivity finding? |

Their reference solutions and evaluation criteria are public, so these are exposed
methods demonstrations. [Reported results](results/README.md) retain their original
scope and do not measure performance on the newer task inventory. Earlier task
boards, queues and design decisions remain in [upstream history](upstream-history/README.md).

## Use an example

From the repository root, print the oracle command:

```sh
./examples/original-three/scripts/run_task.sh DEVCONN-001 oracle
```

The helper accepts an original task ID or an explicit task directory. By default it
prints commands; adding `--run` executes them. See the [example contribution guide](CONTRIBUTING.md)
for the original environment and authentication instructions. Runtime execution can
fetch the examples' public data.

With Harbor installed, the direct oracle command is:

```sh
harbor run -p examples/original-three/DEVCONN-001 -a oracle -o jobs -k 1 -y
```

Each example keeps `task.toml`, `instruction.md`, `environment/`, `solution/` and
`tests/`. Its `proposal.md` records the original scientific rationale; saved
reported results now live in its own `results/` folder.
