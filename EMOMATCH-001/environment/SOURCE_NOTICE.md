# Source provenance and interpretation

This task retains released source files, not a synthetic cohort or a shipped
numerical answer bank.

- AOMIC PIOP2, OpenNeuro ds002790, release 2.0.0:
  https://doi.org/10.18112/openneuro.ds002790.v2.0.0
- Dataset Git commit: `81c3294a906d03d41952a06df94c83746c2d7509`.
- TemplateFlow MNI152NLin2009cAsym Git commit:
  `15d7c02160f79f5218d2545b4febebeecc11531d`.
- The atlas is the released res-02 Schaefer2018 100Parcels7Networks label image
  in that template, with its original label table, template description and
  license. It is not the legacy FSL-MNI-space Schaefer image silently treated as
  an identical template.

The manifest lists 131 exact files totaling 2,197,402,958 bytes. These include
twenty preprocessed BOLD runs, events and confounds; their original sidecars;
the 226-row participant table and dataset documents; and the four atlas
documents/image. The fixed analysis participants are sub-0002–sub-0009 and
sub-0011–sub-0022. Other participant rows are provenance, not analyzed people.
The original relative directory layout is retained under `/app/data/emomatch`;
the manifest is outside that closed inventory at `/app/source_manifest.json`.

Every file is authenticated with size and measured SHA256. Regular Git files
also retain content-blob SHA1; annex payloads retain their published MD5 and
separate pointer Git identity. An annex pointer digest or S3 ETag is not
substituted for a payload checksum. Exact source URLs are in the manifest.
Downloads occur only during image preparation; task execution is offline.
A changed or unavailable original fails preparation rather than selecting a
different participant or silently regenerating the data.

The dataset root declares CC0. The derivative dataset description contains
placeholder source/license fields and reports fMRIPrep version `0+unknown`.
These original limitations are preserved: this task does not invent a precise
exporter version or imply independent clearance beyond the released documents.
The original participants.json contains two identical NEO_A definitions. The
source bytes remain unchanged; documentary inspection preserves both entries.
This personality-scale description is not used by the analysis. Source timing
documents and the task contracts must still have unambiguous unique JSON keys.
The original TemplateFlow license and notices remain at
`/app/data/emomatch/atlas/LICENSE`. Local capture is not a new public release.

Source timing documents report TR=2 seconds and two scanner-discarded volumes.
Inherited slice timings and literal image-header timing are retained separately.
The analysis uses frame0=0 as a computational convention, not a demonstrated
exporter slice-time reference, and does not discard two additional frames.

This is a fixed-subset duration-model sensitivity exercise. AOMIC's displays
ended on response or timeout, so response time is also related to exposure.
The original event duration is preserved independently of modeled duration;
median imputation for omissions is an assumption, not measured exposure.
The task does not reproduce the original Hariri sample, the full AOMIC sample,
or a named paper figure's numerical result. Coordinate spheres are operational
supports, not independently validated participant-specific anatomical masks.
Neither an attenuated coefficient nor a changed p-value proves a causal
reaction-time explanation or emotion-specific response.

Primary sources:
- Snoek et al. (2021): https://www.nature.com/articles/s41597-021-00870-6
- Grinband et al. (2008): https://pmc.ncbi.nlm.nih.gov/articles/PMC2654219/
- TemplateFlow matching-template atlas example:
  https://www.templateflow.org/python-client/master/notebooks/01_quickstart.html
