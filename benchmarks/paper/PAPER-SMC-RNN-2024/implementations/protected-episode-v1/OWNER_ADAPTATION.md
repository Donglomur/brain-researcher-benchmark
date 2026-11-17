# Remaining active-owner integration — proposal, not an implemented runtime

`episode.active_owner_journal()` deliberately refuses every authentic execution.
There is no configuration flag that removes this refusal. The normal Provider
composition is source code covered with a mocked owner/container boundary, not
evidence of a protected episode. The following identifies the precise existing
APIs that a separately reviewed successor would need to connect.

1. **Reuse the existing launch-barrier owner rather than extending a global
   timeout.** `benchmarks/shared/program-execution/ownership-v4/process_owner.py`
   exposes `launch(argv, folder, seconds, controller)` and
   `stop(folder, end, proc=None)`; its paired `group_bootstrap.py` enforces the
   same 300-second cap. The NEURAL-024
   `ownership_long_v2/{process_owner,group_bootstrap}.py` variant permits 760
   seconds. Both record the initialized leader and write the owner journal before
   activating the trusted controller. Neither cap can accommodate SMC. A future
   task-specific reviewed owner profile must preserve this launch barrier and
   source descriptor, enforce the original overall deadline, and qualify actual
   Linux process identity and interruption behavior. Merely changing one constant
   or supplying a historical qualification boolean does not implement this.

2. **Bind the actual invocation and enclosing clock.** Reproduction permits
   86,400 producer wall seconds per condition; the present two-phase composition
   requires at most 173,760 seconds including its explicit 60/300/60-second
   setup/capture/cleanup per condition and 120-second orchestration allowance.
   Improvement analogously requires 22,560 seconds. These are prospective
   engineering ceilings, not allocated time or observed costs. The owner must
   bind the exact protocol/program/source pins, actual leader birth, output roots
   and one enclosing monotonic deadline before activation. Signal paths and
   recovery cannot refresh the scientific producer budgets or the owner clock.

3. **Route the unchanged Provider's real journal callback to that owner.** The
   pinned Sleep `vendor_transport.Provider.execute_phase(request, mounts,
   original_deadline, journal)` publishes an `OWNERSHIP` event and resource
   intent/attempt/acknowledgement records. A future owner callback must durably
   retain and acknowledge the exact request, source, ownership and resource pins
   before creation is released. The active-owner adapter must join those records
   to its already owned controller; local journals alone do not prove atomic
   birth custody. The current `execute` composition now passes the future owner
   callback through without discarding these events.

4. **Use the existing recovery API only after verified controller closure.**
   `Provider.recover(phase_id, request_pin, ownership_pin, original_deadline,
   journal, limits, controller_closed_proof)` already requires parent-owned
   closure evidence and has explicit metadata/CLI/read/write budgets. The future
   owner must stop only the exact owned controller, prove it cannot create more
   resources, then call recovery for its pinned resource intent within the
   retained deadline. Unknown create outcomes, failed cleanup or unreaped CLI
   processes must remain failures. Actual forced-stop tests must independently
   observe host and daemon state, including interruption between intent,
   acknowledgement and capture. This source change has run none of those tests.

5. **Qualify the exact image and the restricted producer profile separately.**
   The unchanged Provider requires Linux `pidfd_open`/`pidfd_send_signal`; it
   rejects network, writable host binds, implicit image volumes/health processes
   and mismatched mount/resource configuration. The same image must contain only
   generic dependencies and none of either task arm's restricted contents. A
   separately admitted generated runtime check must verify hard CPU enforcement,
   `pids=1`, `--init=false`, the `-S` entry, 4 GiB memory and full HDF5 capture.
   Original author/library compatibility remains unproven. Generic primary
   execution permitting subprocesses would additionally need real aggregate CPU
   enforcement across all descendants; this restricted route cannot stand in
   for it.

No existing owner implementation, task, runtime image or canonical registry was
modified here. Authentic data, inference, training, scoring, Docker and paid API
execution remain unattempted. Completing these integrations would require a new
reviewed source successor and separate runtime admission; it is not achieved by
the current generated composition controls.
