# NEURAL-054 frozen namespace capture successor

This additive source package repairs output capture from the participant's `/work` and supervisor's `/observed` tmpfs. Docker `cp` cannot capture those direct tmpfs mounts. The original `registered-runtime` package and its historical evidence remain unchanged.

The launcher keeps the original owned container paused, verifies the same-host cgroup freeze, and copies through a held `/proc/<original PID>/root` descriptor. Original PID/starttime/cgroup/root and Docker container identity must match before and after each bounded copy. Participant-controlled links, hardlinks, special files, path replacement and quota violations are rejected. Partial output costs remain charged even if the supervisor receipt is never admitted.

This is source construction with generated tests only. It does not establish Linux host proc-root permission, Docker Desktop support, native isolation, scientific accuracy or benchmark completion. All original scientific populations, scoring and external qualification gates remain intact. `CAPTURE_REPAIR_SCOPE.json` states the exact boundary and limitations. `manifest.json` supplies inactive successor entrypoints; only the integrator may select them in the current registry.

Run generated capture controls with `python -I -B tests/test_frozen_capture.py`. The tests use temporary files and invented process metadata, never Docker or authentic data.


## Direct model observation transport

The offline D actor sends the controller's ordered label names, window, arm and
information profile with the complete serialized PCA8 payload. Numeric class
summaries and query coordinates retain their original values and order. Source
identities, other queries, controls and protected targets are not added. The
whole prompt counts toward the existing context limit; there is no truncation.
The actor accepts the existing explicit `{"status":"abstain"}` response without
inventing probabilities. The controller still records abstention as unscorable
and keeps protected targets closed for that selected incomplete campaign.

Run `python -I -B tests/test_model_actor_transport.py` for generated transport
controls. Tokenizer and model interfaces are stubs: these checks establish
message construction and response handling only. They do not qualify an actual
model, its no-tools execution boundary, scientific performance or full-cohort
execution. Direct PCA8 E06 remains separate from full-core P/I comparisons.
