# Original scientific-judgment examples

These three Harbor-format tasks come from the original benchmark repository.
Their prompts, reference solutions, scorers and task IDs are preserved unchanged.
They are worked examples of scientific judgment and are separate from the newer
[paper and neural-data construction programme](../../benchmarks/README.md).

| Example | Scientific question |
| --- | --- |
| [GRADIENT-001](GRADIENT-001/) | How robust is an interpretation of the principal connectivity gradient? |
| [SOCIALBRAIN-001](SOCIALBRAIN-001/) | How does global-signal regression affect a reported social-brain anticorrelation? |
| [DEVCONN-001](DEVCONN-001/) | How does head motion affect a developmental connectivity finding? |

The reference solutions and evaluation criteria are public. Treat these examples
as exposed methods demonstrations, not fresh held-out tests. The inherited
[reported results and their limitations](upstream-history/RESULTS.md) do not measure performance on
the newer construction suite. Moving these folders adds no benchmark or result. Their
[historical task board, queue and authoring guide](upstream-history/README.md)
are archived alongside the reported results; they are not the current programme tracker.

## Use an example

From the repository root, print the oracle command without running it:

```sh
./tools/run_task.sh DEVCONN-001 oracle
```

The helper accepts the three original task IDs or an explicit task-directory
path. Its default is to print commands; adding `--run` executes them. See
[original contribution and environment instructions](../../docs/original-examples-contributing.md) for Harbor
setup and agent authentication. These examples fetch their public data at runtime.

With Harbor installed, the equivalent direct oracle invocation is:

```sh
harbor run -p examples/original-three/DEVCONN-001 -a oracle -o jobs -k 1 -y
```

Each example keeps its original `task.toml`, `instruction.md`, environment,
`solution/` and `tests/` layout. Its `proposal.md` records the original rationale.
