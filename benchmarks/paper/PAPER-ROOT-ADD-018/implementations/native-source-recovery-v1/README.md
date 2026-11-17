# Native hLDS source follow-through

The original held-neuron prediction endpoint remains unresolved. This component records a new, specific source lead and distinguishes the accepted manuscript from the earlier preprint. It supplies no numerical evaluator, alternative split, reconstructed spike stream, or qualified baseline.

Paper reproduction and same-task improvement are separate first-class outcomes. This source finding supports their common provenance requirements; it establishes neither outcome. The matched paper-plus-data and paper-plus-data-plus-author-code conditions retain their existing exposure boundaries.

## New lead and its limits

The [Savin lab GitHub organization](https://github.com/Savin-Lab-Code) lists a public repository named [HierarchicalKF](https://github.com/Savin-Lab-Code/HierarchicalKF). GitHub's repository page reports that it is empty. The bounded API capture and its response-body identities are in `SOURCE_FINDINGS.json`. This is a plausible method-source lead because of the laboratory and repository name; no README, paper citation, or code body establishes that it is the implementation used for this paper. An empty public repository does not establish that no implementation exists elsewhere.

This extends the previous source search, which inspected the Constantinople publication tree and related preprocessing sources. That earlier search recovered useful code from other studies but did not authenticate the original continuous count/event constructor. Shared field names and related code remain insufficient to reconstruct the original observations or admit a model comparison.

## Original endpoint anchors

The retained [accepted author manuscript, PMC12638016](https://pmc.ncbi.nlm.nih.gov/articles/PMC12638016/), identifies DOI `10.1016/j.neuron.2025.10.024`, PMID `41253149`, and manuscript `NIHMS2123006`. Its exact XML identity is recorded in `SOURCE_FINDINGS.json`. This is the accepted manuscript, not the publisher's version of record. The earlier [PMC11565993 preprint](https://pmc.ncbi.nlm.nih.gov/articles/PMC11565993/) remains a distinct version.

The accepted manuscript's hierarchical-model Methods establish square-root transformed binned counts, session-specific maximum-likelihood EM, one slow and ten fast latent dimensions, and learned observation loadings. For a test neuron, fitting includes its training observations; test inference removes its observation and loading row, infers latents from the other neurons, then projects those latents through the removed loading row. Its test observations belong to data withheld from fitting. These facts support conditional reconstruction on held-out data; they do not identify a neuron never observed in training or a future-time forecast.

The inspected manuscript describes smoothing for the fitting E-step and filtering when investigating latent coding properties. That wording does not independently settle every held-neuron validation inference clock. The 50 ms firing-rate description elsewhere in Methods also does not supply a complete native hLDS binning, normalization, scoring, or support contract.

## What remains necessary

The original held-time partition, evaluation-unit roster, hLDS/ordinary-LDS producers, ordinary-LDS dimensionality convention, loss and its normalization, aggregation, and numerical comparison are not recovered. Figure S8 is cited by the manuscript, but the linked complete supplement is absent from the retained XML; its metric cannot be inferred from the main-text comparison or imported from the cited general latent-model literature. The original count/event constructor and complete cohort/identity joins remain unqualified.

No new split, MSE objective, rat weighting, or 60/20/20 policy is selected here. The canonical task and improvement contract remain unchanged. Integration may narrow their article-version wording to acknowledge the authenticated accepted manuscript while preserving unresolved publisher/supplement and native-scoring requirements. Source evidence does not qualify the existing prospective runtime as the original paper endpoint.

## Verification and qualification

Only public repository metadata and retained source text were inspected. No authentic observations, historical private solver targets, model weights, training, fitting, author inference, or candidate evaluation were accessed or run. No generated software tests are needed for this evidence-only component; metadata inspection is not a test pass or scientific performance result. Raw responses, source extraction, resource receipts and the exact handoff remain in external operator evidence. This component is a bounded negative source finding, not a completed or runnable benchmark.
