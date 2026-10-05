# Source-keyed offline sleep-staging repair

The twelve original PSG/hypnogram EDFs were freshly downloaded from the official
public S3 mirror and verified against primary-host PhysioNet SHA256SUMS retrieved
before download. The manifest pins exact subjects/night/roles, hashes, file sizes,
source/transport URLs and attribution. Runtime internet is disabled.

The oracle and instruction now share an explicit annotation crop, channel order,
30-second epoch, Welch, normalized-bin feature, seeded RF and LOSO contract.
The new reference retains original EDF epoch samples, source classes and actual
held-out predictions. Complete confusion tables and all subject/pooled metrics
are recomputed; class relabeling or score-preserving prediction fabrication does
not satisfy these checks. Prose keywords and arbitrary performance/variability
gates are removed.

Scientific role: a modern six-recording R&K-collapsed five-class method control,
not AASM rescoring, Kemp's original slow-wave finding or clinical validation.
The committed builder reopens raw sources; independent checks use separate manual
epoch construction and SciPy Welch, sharing MNE EDF readers and sklearn RF.

The repaired native offline oracle measured 5,828 epochs, accuracy
0.7752230610844201 and pooled kappa 0.6827459107932206. Independent epoch selection
and source classes match all rows; feature maximum absolute difference is
1.67e-16 and all 5,828 RF predictions agree. The actual-output authoring matrix
passes 69 tests (29 helpers, 15 staging, 6 positive and 19 negative output cases).

Execution receipts in tracking/pr_repairs_2026-10-01/pr-141/ determine validation
status. This description alone is not an oracle result. No model calibration,
push, merge or acceptance is implied.
