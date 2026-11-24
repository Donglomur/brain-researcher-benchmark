# One complete causal neonatal EEG packet

Read one JSON object from the first stdin line. This is the existing
`helsinki-causal-packet-v1`: all 18 bipolar EEG channels, every native sample in
the 30-second causal window, units, exact relative sample clock, and the original
30 quality flags. Samples are sample-major. Sample i has time
`(first_tick + i * step_ticks) / ticks_per_second` seconds. There is no resampling,
padding, filtering, channel deletion or implicit unit conversion in this route.
Quality flags are input-quality indicators, not verified missingness labels.

Estimate the fraction of three expert scorers marking seizure in the final
interval [29,30), using only this packet and admitted immutable training-derived
artifacts. This is recognition of the final second, not prediction of future EEG.
Your single frozen program runs in a fresh process for each case. No labels,
infant identity, source filenames, absolute recording offset, case roster or
correctness feedback are supplied.

Write exactly one JSON object plus newline to stdout, with exactly `action`,
`case_id`, `input_sha256` and `probability`. Set `action` to `answer`, copy the
current packet identifiers, and return one finite probability in [0,1]. Read the
accepted-answer receipt from stdin, then exit successfully with no further
stdout bytes. There are no describe/view actions or second attempts in this
numeric route. Stdout is reserved for the answer protocol.

Do not access other cases, future EEG, expert labels, source files, unadmitted
tools, network resources, or memory from previous cases. These instructions and
fresh process creation do not establish filesystem/network/provider containment.
An operator must qualify those boundaries before using authentic inputs. The
generated fixture program is a software control, not a trained seizure detector.
