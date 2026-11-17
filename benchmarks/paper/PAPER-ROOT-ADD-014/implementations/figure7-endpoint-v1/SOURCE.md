# Source recovery and scope

The inspected author repository is `KenYMB/ECoG_alphaPRF` at
`4321eb4374db782d09f3f43362836f234a4e4f9b`. This work reused cached source and
downloaded zero bytes. MATLAB bodies, recordings, saved fitted parameters,
reference arrays and private solver answers are not redistributed or used in
the generated controls. Exact verified file identities appear in SOURCE_LOCK.

The publication is [Yuasa et al., eLife 90387](https://elifesciences.org/articles/90387).
The existing improvement contract and independently reviewed source audit bind
its 366-electrode/nine-participant source population, 31-electrode Figure 7 panel
and rounded 43% versus 10% median claim. Those counts are admission expectations,
not measurements produced by this new component.

The consequential new source facts are:

1. [makeFigure7_7S1.m](https://github.com/KenYMB/ECoG_alphaPRF/blob/4321eb4374db782d09f3f43362836f234a4e4f9b/makeFigures/makeFigure7_7S1.m),
   lines 11–19: the publication entrypoint sets `issaveplot=false`, invokes
   `ecog_APRFF_10k1e_checkalpha_bothgaind`, and exports `hF(1)` for Figure 7.
2. [The invoked script](https://github.com/KenYMB/ECoG_alphaPRF/blob/4321eb4374db782d09f3f43362836f234a4e4f9b/scripts/ecog_APRFF_10k1e_checkalpha_bothgaind.m),
   lines 38–85: average runs, decimate by three, linear GS, wangprobchs, no lag,
   no full-timecourse R2 replacement; both alpha models load `prfbidirgain`.
   Model-based alpha allows subject-specific beta/wide variants; raw alpha does
   not. Lines 102–103 flip fitted alpha gains for display after loading, which
   does not restrict the signed fitting branch or change its saved xval scores.
3. The same script, lines 127–134: each broadband selection uses its own source
   xval threshold and eccentricity limit. Line 271 sets `ispltall=true`.
   The first unconditional simple summary, lines 859–937, uses V1/V2/V3 and
   the intersection of both broadband selections for the xval violin. There
   is no alpha threshold, alpha eccentricity limit, gain-sign subset or
   candidate-dependent selection in that active primary branch. Lines 985–987
   use the same mask for the response-gain companion.
4. [INITd_threshold](https://github.com/KenYMB/ECoG_alphaPRF/blob/4321eb4374db782d09f3f43362836f234a4e4f9b/scripts/ecog_APRFF_INITd_threshold.m),
   final lines: the percentile is 0.95 and eccentricity limit is 50 pixels.
   [ecog_prf_getthreshold](https://github.com/KenYMB/ECoG_alphaPRF/blob/4321eb4374db782d09f3f43362836f234a4e4f9b/functions/files/ecog_prf_getthreshold.m)
   flattens broadband permutation results, takes their 95th percentile and
   rounds the result. It returns NaN if the file is missing. Therefore the
   rounded 31% diagnostic in the older code is not sufficient evidence of
   these exact two source threshold artifacts.
5. [INITa_loaddata](https://github.com/KenYMB/ECoG_alphaPRF/blob/4321eb4374db782d09f3f43362836f234a4e4f9b/scripts/ecog_APRFF_INITa_loaddata.m),
   lines 58–60, sets the wangprobchs threshold to 0.05 and excludes FEF by
   default. INITb passes the normalisation option into the merged atlas label
   path. This new component consumes those already-resolved labels; it does
   not pretend that raw atlas strings or the 433 released rows recover the
   historical 366-row population.

The source MATLAB uses negated comparisons so NaN can pass a threshold test.
The new selector deliberately refuses nonfinite operands for operator
reconciliation. It implements the exact finite-domain predicate and does not
silently declare a different nonfinite cohort equivalent to the paper.

The reviewed `alpha-programme/spatial/vendor/metrics.py` already separates
source fold-projected COD from literal uncentered paper Eq.6. The new scorer
reuses it through its existing source lock. The source path is
`ecog_prf_analyzePRF` → `analyzePRFdog` → `fitnonlinearmodel`/helper → `calccod`.
The captured analyzePRF companion's historical execution version remains
unverified, so source-formula arithmetic is not a native MATLAB parity claim.

For integration, retain `source_unresolved` and the existing historical
implementation. Propose adding this component as the original Figure7 scoring
path, correcting the active comparator's alpha branch to signed gain only
after authentic native qualification, and binding the 366/31 source identities
and permutation cutoffs through an operator-only preparation protocol. The
candidate may improve its method freely while preserving the original cohort,
permitted observations, split, point estimand and companion conditions.
