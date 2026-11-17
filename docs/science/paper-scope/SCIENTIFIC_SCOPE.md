# What the 100 paper candidates actually cover

This catalogue contains 100 paper-linked benchmark candidates. A source review found narrative evidence of broad relevance to computational or systems neuroscience, or methods for real neural data, for 97 of them. Three final-paper narratives remain missing from the reviewed evidence: **PAPER-FIND-003**, **PAPER-FIND-013** and **PAPER-ROOT-ADD-021**. Their code, deposit and task descriptions support more limited statements, not a completed assessment of the final papers.

The [100-row assessment](PAPER_SCOPES.json) identifies each paper, its public reference, examined edition, reported contribution, biological units, selected benchmark endpoint and remaining evidence gaps. It contains original assessment prose and bibliographic facts. It does not contain article excerpts, figures, recordings, participant records, answer keys or model outputs.

This is a scientific-scope summary, not a ranking of paper quality or novelty. It adds **zero qualified benchmarks, scientific runs or verified performance results**. Reading a reported result does not reproduce it; identifying a relevant paper does not establish that its code, data and every published analysis can be replayed.

## The paper and the selected task can ask different questions

Three selected endpoints use behavior alone, although their associated papers also analyze neural measurements:

- **PAPER-FIND-037:** a 25-person behavioral model comparison.
- **PAPER-FIND-REP-003:** the Figure 1H joint-angle trajectories.
- **PAPER-paper-signal-add-021:** a 15-person memory-guided-saccade table.

**PAPER-paper-method-add-004**, the iSTTC task, estimates timescales for 100,000 released simulated Hawkes units. The paper also evaluates real neural recordings, but those recordings are not the selected known-truth endpoint. This task can test scientific numerical reasoning; it cannot be counted as a direct evaluation on measured neural data.

Two endpoints concern measured neural structure: **PAPER-FIND-NEW-003** uses adult-fly connectomics and **PAPER-FIND-REP-013** uses dendritic morphology. Another 91 selected scopes declare neural or neural-derived measurements. The three missing-final cases separately declare neural-derived endpoints. These categories sum to 100; they describe selected scope, not completed empirical evaluations. Structural anatomy, physiological estimates and dynamic recordings remain distinguishable in the rows.

A candidate task also need not reproduce the whole paper. Current examples include a four-dataset MINT decoding-artifact comparison within a larger study; a posterior-conditioned reconstruction task for an interaction model; and the released 433-electrode visual-alpha panel, whose relationship to the paper's 366-electrode selection remains unresolved. Conversely, CBraMod's selected primary roster covers all 12 downstream datasets; remaining pretraining, cohort and native-comparison gaps must not be misstated as a smaller downstream selection.

## Details that change the meaning of a result

Biological units and exclusions matter. The EEG finger-control study analyzes 21 experienced responders from 49 recruits, with separate extension and feedback requirements. Its reported performance does not describe all recruits or a clinical population. GCaMP8's 117 released neuron files are not 117 independent animals, and they differ from the paper's 105-neuron selection.

Ground truth has limits. Spinal CASCADE has paired spike measurements in its ex-vivo evaluation; its in-vivo application does not supply the same paired truth. BOLD/CMRO2 comparisons use physiological estimates and modeling assumptions rather than direct firing measurements. Cross-session pseudopopulations cannot be treated as simultaneous recordings.

Information available to a model also matters. The interaction model observes the complete target trial in its encoder, so its reconstruction endpoint is not a forecast of hidden spikes. Visual-alpha's archived initialization uses the full series; corrected training-only half fits form a separate prospective condition. A native reference comparison remains unavailable where its gain-sign provenance is missing.

ICNet models **inferior-colliculus, auditory-midbrain** population responses from anesthetized gerbils. It is not an auditory-cortex study. Its main nine-animal analysis, broader protocol and seven-animal released selection are distinct. Other retained differences include DeepCaImX's paper-versus-donor counts and Kilosort's catalogue-versus-selected code revision; the summary does not silently reconcile them.

Reported answers can depend on an analysis choice. The EEG event study finds five events in its main setting and three under an appendix setting. In the reward/emotion EEG study, the direct P3b coefficient comparisons are nonsignificant; different individual significance patterns do not establish complete neural separation. Benchmark scoring must retain such qualifications rather than reward a desired count, sign or significance claim.

## Recent publication does not necessarily mean recent first appearance

The associated publications fall in the catalogue's 2024–2026 window at varying evidence levels. This is not evidence that all 100 works first became public in that interval. The free-energy and visual-alpha papers explicitly record preprint postings in 2023. The motor-MINT and osl-dynamics records contain reviewed versions from 2023. The language-network narrative examined by the audit is a 2023 preprint associated historically with a 2024 journal paper.

The JSON separates the associated publication date from the examined edition and any explicit first-posted or prior-version observation. For example, ROOT-ADD-010 uses a reviewed preprint from 2025 while its recorded Version of Record is from 2026. Osl-dynamics has an active Version of Record dated 2025-06-25 and an earlier one dated 2024-01-29. An observed arXiv v1 date for MindBridge does not prove earliest availability everywhere or exact equivalence to the conference edition.

Online publication, issue dates, conference years, acceptance dates, copyright labels and manuscript revisions are different evidence. A date-like DOI token is not a posting date. GCaMP8 and ICNet PDFs have unfilled online-date fields; their separately recorded historical publisher dates remain explicitly historical. Unknown first appearance is reported as unknown, while observed first-posted statements remain visible. No row claims an exhaustive earliest-publication search.

## How to use these assessments

Use the rows to choose a scientifically meaningful reproduction target, preserve the full selected support and biological hierarchy, and distinguish published-method reconstruction from a prospective improvement condition. Keep behavioral, simulated, structural and measured-signal endpoints visible when reporting coverage. Resolve the named paper-edition, code/data, preprocessing, cohort and metric gaps before claiming native paper parity.

The public references provide attribution and a route to the papers. This summary conveys no license to redistribute the papers, their code or their datasets. Publication of these assessment files does not change benchmark readiness or authorize scientific execution.
