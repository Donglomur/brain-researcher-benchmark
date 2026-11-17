# Publication-route recovery

The publication tree at `e3796c13fe7afe7a84854cd5a02c36de268e88f4` contains
distinct cross-time paths. Inspecting only `processSession_crossTimeDecoding.m`
misses the full-population path. The following distinctions are material to
the registered five-mouse Figure 2h/4d/e endpoint.

| Source | Behavior | Consequence |
|---|---|---|
| `CrossTimeDecodingAnalysis.m` | Enumerates the five original session tags; retains full-contrast 573-dot motion, normal state criteria, first minimum available trials per condition and the quality/rate-filtered units. Trains on every retained unit (`:`), with five random half-split permutations shared between states. Produces `session(isession).stat/run.perm.perf` on 20 training × 20 testing windows. | A source-native full-population route is recovered. Do not reconstruct it by selecting a smaller `popSize` entry. |
| `analyseTrainTestDecoding.m` | Loads `rLDA_trainTest_withConsensus.mat`; averages permutations per mouse; computes above-chance ratio-of-sums across MATLAB windows `3:12`; averages the five mouse ratios and selects training window `4` for the early comparison. | This is the implemented ratio reduction. The loaded MAT result has not been recovered or inspected. |
| `processSession_crossTimeDecoding.m` | Uses population sizes 10, 20, 40 and 80 with repeated unit subsamples; the append of all units is commented out. Saves `session.popSize(ipop).rep`. | This source is insufficient by itself to prove a complete full-population rerun. |
| `analyse_CrossTimeDecodingMultPopsize.m` | Averages permutations per subsample, computes ratios, concatenates subsamples across sessions, caps ratios above one and uses median/median CI summaries. Includes shuffled controls. | These population-size summaries have different weights and statistics. They cannot replace the main five-mouse mean/SEM endpoint. |
| `analyseDiscriminantAnalysis_spikeCounts.m` and `do_cvDA.m` | For the diagonal-covariance route, average held-fold accuracies, then five permutation curves within a mouse, then mice. | Pooling prediction counts across unequal folds changes the source metric. |
| `GenericFunctions/sem.m` | Uses `std(x,[],dim)/sqrt(size(x,dim))`, with MATLAB sample standard deviation. | SEM is computed over five biological units after within-mouse averaging. |

The full-population script references `nTrials` when constructing train/test
sizes, but contains no assignment to it. It loads source MAT files and also
depends on the surrounding MATLAB workspace. This is an unresolved clean-run
dependency, not proof that the published analysis was invalid. No guessed
value, new split, or automatic repair was introduced here.

The source ratio section does not clip relative values at one; another section
clips *pointwise* ratios for a different plot, and the population-size analysis
also clips ratios. The reducer deliberately implements only the identified
ratio-of-sums route and preserves raw accuracies and its denominator. It does
not claim the separate clipped routes are equivalent.

Eight code files are pinned in [SOURCES.json](SOURCES.json). Five were reused
from the existing source cache. Three missing files were recovered from their
GitHub blob endpoints (21,179 response bytes); the first raw-host TLS attempt
returned zero response bytes. Code stayed outside Git. No source recording,
accuracy matrix, trained model or private target was opened. These findings
resolve code-path and aggregation questions, while the original numerical
baseline, exact saved/run configuration and empirical qualification remain
unresolved.
