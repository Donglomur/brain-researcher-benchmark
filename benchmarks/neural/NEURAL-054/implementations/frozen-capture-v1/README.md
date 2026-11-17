# NEURAL-054 frozen namespace capture successor

This additive source package repairs output capture from the participant's `/work` and supervisor's `/observed` tmpfs. Docker `cp` cannot capture those direct tmpfs mounts. The original `registered-runtime` package and its historical evidence remain unchanged.

The launcher keeps the original owned container paused, verifies the same-host cgroup freeze, and copies through a held `/proc/<original PID>/root` descriptor. Original PID/starttime/cgroup/root and Docker container identity must match before and after each bounded copy. Participant-controlled links, hardlinks, special files, path replacement and quota violations are rejected. Partial output costs remain charged even if the supervisor receipt is never admitted.

This is source construction with generated tests only. It does not establish Linux host proc-root permission, Docker Desktop support, native isolation, scientific accuracy or benchmark completion. All original scientific populations, scoring and external qualification gates remain intact. `CAPTURE_REPAIR_SCOPE.json` states the exact boundary and limitations. `manifest.json` supplies inactive successor entrypoints; only the integrator may select them in the current registry.

Run generated capture controls with `python -I -B tests/test_frozen_capture.py`. The tests use temporary files and invented process metadata, never Docker or authentic data.
