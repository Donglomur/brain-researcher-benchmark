# One causal neonatal EEG case

Use only the current case's permitted waveform pages and visible metadata. The
window contains 30 seconds of the original 18 bipolar EEG channels. Estimate the
fraction of three expert scorers who would mark seizure activity in its final
second, the interval [29,30). Return one probability between zero and one. This
is recognition of that interval using its signal, not forecasting a later event.

The first stdin line is the typed raster description. Send one JSON object per
newline on stdout; stdout is reserved for protocol actions. You may request
`{"action":"describe"}` or a waveform page with exactly `action`, `start_sample`,
`stop_sample`, `channels` and `units_per_division`, where action is `view`. Stop
indices are exclusive. Respect the description's sample/channel page bounds and
original channel indices. Time, units, positive gain, clipping counts and original
quality flags are explicit; quality flags are not verified missingness labels.
All original samples and channels remain addressable. A page is a PNG, not a
numeric signal export; changing gain can reveal clipped portions.

To finish, send exactly `action`, `case_id`, `input_sha256` and `probability`, with
action `answer` and the current description's case/input identifiers. After the
accepted answer receipt, exit successfully without further stdout output. There
is one final answer; no correctness feedback or second attempt is supplied.

Do not access other cases, source files, expert labels, participant memory from
earlier cases, future signal, or unadmitted tools. This instruction is a task
description, not enforcement of a sandbox. Process/filesystem/provider isolation
and any model-specific adapter require separate operator qualification. The
fixture used to verify the protocol is not a trained neuroscience reference.
