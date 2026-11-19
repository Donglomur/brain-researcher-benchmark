# Viewer participant process ownership

This shared helper repairs a lifecycle hazard in the EEG and sleep transports:
reaping a child before signalling its numeric process-group ID can allow that ID
to be reused. The transport now observes exit without reaping, signals while it
still owns the unreaped leader, and only then waits for the exact child.

`preflight()` requires the default Python SIGCHLD disposition and Darwin kqueue
or Linux pidfd support. Construct `ExitObserver(child)` immediately after
`Popen(start_new_session=True)`. `wait(deadline)` observes exit without consuming
status. `stop_and_reap(child, observer, deadline)` performs bounded group cleanup,
the sole reap, and read-only group-presence probes. It records signal dispatch,
exit status, observed absence and failures separately.

The trusted parent must be the exclusive waiter and must not change SIGCHLD or
install native `SA_NOCLDWAIT`. Python's handler query does not establish the
absence of a native automatic-reap policy. No descendant containment is claimed
for a process that leaves the original group; `protocol_only` remains an operator
bridge. The existing macOS participant sandbox still denies forking and network
access. No viewer action, scientific input, image, label, score or provider
setting is changed by this helper.

The focused controls use mocked OS/process operations. They exercise ownership
ordering, exit-before-registration, reaped-handle refusal and failure cleanup;
they do not launch a participant, signal a process or qualify native containment.
Historical transport execution evidence belongs to its earlier source identity.

```sh
python3 -I -S -B -m unittest discover -s benchmarks/shared/viewer-process-ownership-v1 -p 'test_*.py' -v
```

Actual deployment still needs its ordinary native runtime and transport checks.
A cleanup receipt is an operator record, not evidence of AI neural understanding.
