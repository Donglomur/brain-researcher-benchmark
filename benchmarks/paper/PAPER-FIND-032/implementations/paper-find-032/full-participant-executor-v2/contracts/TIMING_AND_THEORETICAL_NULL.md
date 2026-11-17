# FIND-032 observed-support theoretical endpoint

Status: prospective corrected_methods_v1 source specification. Historical reproduction remains the primary paper-parity profile and is not replaced by this endpoint. No scientific run, empirical support, native qualification, or numerical parity has been observed.

## Identities and orientation

The four stimulus classes are 1–4. Omission triggers 10/20/30/40 retain the intended class identity but are not treated as observed sounds. The complete protected stimulus chain retains both sound and omission events in actual onset order, removes only separately recorded non-stimulus markers, and uses actual recording sample coordinates. Each original or reordered epoch retains the union of all underlying released-recording sample intervals, including copied padding.

T[i,j] is P(S[n+1]=j | S[n]=i): row is previous class, column is next class. The four matrices are exactly the qmd/paper condition matrices. Their names are random, midminus, midplus, ordered. The transposed representation used in author base.py is explicitly a representation difference. The corrected source uses the qmd row convention consistently. Confusion C[c,f,u,v,i,j] is the out-of-fold probability of predicted class j given actual class i, at observed training time u and context-relative test time v. For each condition c and fold f, it is produced from the same fitted model on real held-out random-block predictions, not an input receipt or a supplied precomputed answer.

## Protected observed timing producer

For each retained actual sound target n and every requested integer offset k in -70,...,+70 at the actual 100 Hz release rate, let a = onset[n]+k. Find q, the last stimulus onset at or before a. Require both q and q+1 to exist and bracket a. Set d=n-q and v=a-onset[q]. Both the bracketing events and v come from the actual event chain. No 33-sample regular lattice, synthetic future onset, 135-to-141 extension, interpolation, or inferred timestamp from array shape is allowed.

The event/lag map is produced in the protected analysis tail after the predictive results exist. It is not a participant prediction feature or a training label. Future sensory measurements, future labels, and these future context identities must never enter model.predict. The reference classifier receives only the test MEG channel vector at its fixed test time. Training labels and stratification are handled by the protected reference composition. Access to experimental stimulus labels in the original paper/data analysis problem is not evidence of a deployed target-isolation mechanism.

## Probability calculation

The paper explicitly assumes marginally equiprobable classes, pi=(1/4,...,1/4), and a time-homogeneous first-order transition model. The four fixed matrices are doubly stochastic. This is the selected theoretical model, not a claim that a finite observed sequence is empirically stationary.

If d>0 (context precedes target), A[u,k,n] = (1/4) sum_i sum_j C[u,v,i,j] (T^d)[i,j]. If d=0, A is trace(C[u,v])/4. If d<0 (context follows target), Bayes under the stated uniform marginal gives P(target=j | context=i)=(T^(-d))[j,i], hence A=(1/4) sum_i sum_j C[u,v,i,j] (T^(-d))[j,i]. This uses transpose orientation, never a matrix inverse. A different initial/nonuniform marginal would require a different explicitly selected conditional model and is not silently estimated from held labels.

Require v to be an exact observed confusion time coordinate. Require the context event to be a sound. An omission response cannot be manufactured from a sound confusion matrix. Require every fold/true-class confusion row to be finite and nonempty. All requested participant/condition/time cells are planned. Any absent bracketing event, omitted context, missing offset, missing class, or unavailable confusion producer makes the whole named theoretical endpoint unavailable. No subset average, missing-cell zero, crop, extrapolation, or denominator change is accepted. When all cells exist, use the confusion tensor for the exact condition/fold model, average A over that fold’s preselected target events, then average the five folds equally within participant. Treat the 33 participants equally at group level. The formulas above suppress the fixed c/f indices for readability.

This is a complete producer specification with a deliberately possible unavailable outcome. It does not establish that full ±.7 s theoretical evaluation is empirically available. Omission contexts in actual sequences may prevent completion. The source marks the full named theoretical endpoint and dependent group maps unavailable when any required participant endpoint is unavailable. Independently completed empirical, omission and most-likely pipelines continue to group inference and their outputs remain useful. Structural omission-context support failure is distinct from a missing input file. Deterministic per-target/fold reason records and all planned-cell counts are retained; no failed cell is hidden.

## Physical support and fitting

Stratified five-fold plans are fixed after matching the source-selected trial denominator. All evaluation trials remain fixed. Training epochs that share any released-recording sample with the applicable test epochs are removed. Each condition's paired original/reordered and random-OOF branches share one purged training set and fitted models; most-likely-label scoring uses the same predictions. Different conditions are distinct fit jobs because their physical test support differs. This prospective condition-dependent training-support convention is not an assertion about the unknown exact historical producer. Training with fewer than all four classes refuses the endpoint. There is no fallback to unpurged folds.

The sample exclusion concerns the released preprocessed recording. It does not prove independence of original continuous-filter or MaxFilter contributions. That residual preprocessing limitation remains disclosed. Omission comparisons use random sound training, purged against their fixed paired omission test support. Shared neural arrays and fit states are internal to one participant; no cross-participant training occurs.

## Historical route remains separate

The current qmd takes confusion indices 71:103 for train and 71:104 for test, constructs four 34-column blocks (T squared, T, identity, reversed T), then removes its first column to obtain 135. It uses nominal 10 ms indexing and a 670 ms offset. That literal route and its input expectation are retained in the pinned source projection. They are not relabelled as the corrected 141-axis observed-support endpoint. No compatible producer for its expected rd_to_rd_confmats.npz has been recovered. The earlier e6156 source fixes missing omission helper names but does not supply the required confusion producer or align the current sound/qmd conventions.
