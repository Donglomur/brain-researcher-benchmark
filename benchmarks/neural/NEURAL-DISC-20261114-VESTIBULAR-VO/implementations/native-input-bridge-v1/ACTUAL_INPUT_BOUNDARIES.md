The authenticated original contains waveform-level arrays that can support a
native input bridge, but its complete biological mapping is not yet admitted.
The census receipt establishes structural completeness. The following findings
come from the complete saved metadata, without another original MAT read or
inspection of numerical signal values.

There are 48 top-level structs: 47 condition-parent structs and one standalone
numeric block. The parents contain 139 numeric blocks, and the standalone block
brings the total to 140. The nested condition fields are `base` (47), `nat` (41),
`sine` (42), `natHighFreq` (2) and `natLowFreq` (7). These are source field labels,
not yet an admission of the benchmark's condition identities or frequencies.
The additional naturalistic-labelled fields must remain in the source census;
they cannot silently disappear from preparation.

Each of the 140 blocks has matching N-by-1 arrays labelled `ua` and `stimulus`,
a 1-by-N array labelled `indecies` (the original spelling), and a scalar
`samplingrate` equal to 1000. Their labels, orientation and compatible lengths
are useful exact adapter constraints. They do not establish whether `ua` is a
binary spike train, what `indecies` means, whether `stimulus` is the measured
motion trace, or where complete acquired repeats begin and end. No transpose,
sample origin, unit conversion or repeat segmentation is inferred here.

The full primary paper's Methods describe gyroscope measurement of angular
velocity, a 125-Hz low-pass filter and 1,000-Hz sampling; extracellular recordings
were sampled at 30 kHz, while analysed binary neural activity used 1,000 Hz.
Naturalistic stimulation used a 60-second horizontal-velocity waveform with at
least four repetitions. Sinusoidal recordings included at least ten cycles that
were subsequently concatenated into four or five analysis trials. Acquisition
rates and analysis rates are distinct. Analysis-trial concatenation also does
not establish the original presentation boundaries required by this benchmark.
Source: [PLOS Biology primary article, Materials and methods](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3002623).

The stored rate of 1000 is compatible with the documented analysis rate, but a
complete binding still needs the physical interpretation of each array and its
alignment. In particular, using a signal named `stimulus` as measured angular
velocity would require documentary evidence connecting that field to the
acquired gyroscope signal, including units, axis, sign and calibration.

Filename metadata supplies 128 nonempty entries with 103 unique strings.
Repeated strings are candidate acquisition joins; they do not prove stable
neuron identities, shared clocks or genuine simultaneous pairs. Likewise,
47 condition parents plus one standalone block is not a biological neuron
count. The declared full source target remains 49 neurons, 35 genuinely
simultaneous pairs and three animals. No smaller substitute panel is selected.

The remaining admission requirements are the source-to-biological identity and
pair map; animal/session membership; measured-target and spike semantics;
`indecies`, clock origin and alignment; complete presentation/repeat boundaries;
condition frequencies and extra-condition identities; and any explicit
eligibility or exclusion rules. Private node paths and candidate joins are
retained in operator evidence. None is filled by guessing from a field name or
from the intended cohort size.

The current source can load and resolve every original member, project a fully
specified complete preparation into separate public/protected materials, and
join a separately supplied prior to the unchanged condition evaluator. Those
components do not supply the missing biological bindings. Authentic repeat
preparation, participant isolation, training-only prior qualification and
scientific model evaluation remain separate steps.
