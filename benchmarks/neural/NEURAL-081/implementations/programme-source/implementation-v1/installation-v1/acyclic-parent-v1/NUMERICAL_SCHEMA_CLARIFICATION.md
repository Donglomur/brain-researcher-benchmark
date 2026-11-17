# Numerical ABI record clarification v1

Additive to the frozen API/NUMERICAL_ABI; no scientific change.

`select` returns exactly its declared five keys. `setting_scores` is an ordered list of records with exactly configuration_id,family,balanced_accuracy,nll,per_person, in configuration_grid order. `selected_per_family` is an ordered list (BP_LDA,TM_LDA,RBF_KRR) with exactly family,configuration_id,balanced_accuracy,nll. `temperature_scores` is an ordered family-major, declared-temperature-minor list with exactly family,configuration_id,temperature,balanced_accuracy,nll,per_person. `selected_temperatures` is a list in family order with exactly family,configuration_id,temperature,balanced_accuracy,nll. `strongest_family` is the selected family string. Scores in selected_per_family use T=1; selected_temperatures uses actual calibrated probabilities. per_person has the exact metrics ABI rows.

Label vectors are exact primitive NumPy integer ndarrays, never bool/object/subclasses. Their values are the canonical class IDs, not zero-based offsets. Metadata IDs/person sequences are plain lists of strings. people_order is the complete permitted biological subset in the original canonical PEOPLE order. Every OOF configuration/person record shares the identical canonical-ID-to-label support with the other configurations for that person; IDs are unique and person support disjoint. Numeric source does not open private metadata to infer this mapping. Owner authenticates lineage separately.

These written schemas are supplied identically to both independent numerical authors. No implementation/results are shared before both freezes.
