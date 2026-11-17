# Source interpretation and comparison boundary

The source is Schmidt et al., [Age-related changes in “cortical” 1/f dynamics
are linked to cardiac activity](https://doi.org/10.7554/eLife.100605.3), its
Figure 4 supplement and Statistical inference section, with the pinned
[Salzburg notebook](https://github.com/schmidtfa/cardiac_1_f/blob/4562c0dc318930c46b77732b73d85504b2b471c4/notebooks/%20c_1_f_age_sbg.ipynb).
The processed CSV is [OSF revision 1](https://osf.io/download/a5tb3/?revision=1).
Data/article attribution is CC BY 4.0 in the retained source records; the
separate official-code bundle retains its BSD-3-Clause notice. This source-only
repository does not redistribute the empirical table, paper text or code capture.

| Released CSV response | Author notebook variable | Meaning |
| --- | --- | --- |
| `ECG_not_rejected` | `no_ica_slope_avg` | Magnetometer spectral slope with ECG components retained |
| `ECG_rejected` | `brain_slope_avg` | Magnetometer spectral slope after ECG component removal |
| `ECG_components` | `heart_slope_avg` | Spectral slope of the removed cardiac components in the magnetometers |

In particular, `ECG_components` is not the separate ECG-electrode `heart_slope`
variable. The pinned notebook's `all_df.append` construction distinguishes them;
its raw Bambi `family='t'` fits use the three averaged variables above. The
`cur_df_z = zscore(cur_df_cmb[[...]], axis=0)` block feeds three fresh standardized fits.
All 655 released people are retained; no filter or selected easy subset is added.

The paper directs readers to code for exact priors. The inherited common
`instructions.md` declares the audited Bambi 0.9.1 source-model priors, and the
inherited `MATH_SPEC.md` declares summary conventions. These resolve interface
ambiguities openly for **both** arms. Neither these common source-informed rules
nor benchmark-control seeds are represented as paper-only discovery. This wave
adds no fitted values or solver recipe; it preserves the existing endpoint.

B receives the complete 27-code-cell capture authenticated to notebook blob
`6d6531af64d75b4f1ce3160625293e85751637d5`, plus `pymc_utils.py`, the original
`environment.yml`, source provenance and license. The capture excludes saved
notebook outputs. It still contains historical paths/IPython syntax and expects
upstream inputs outside this processed-table endpoint: readable official code
assistance is not an admitted executable author environment.

The fixed existing summary scorer compares beta means using each reference
posterior SD, with all parameter/HDI/SD and raw location diagnostics retained.
The source-only submission route does not select, read or accept a reference.
A saved historical target and its hash alone cannot establish six competent fits,
convergence, independent reference agreement or a qualified oracle.
