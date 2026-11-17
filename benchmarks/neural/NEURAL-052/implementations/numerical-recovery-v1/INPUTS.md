# Input identity and interpretation

`input/INPUTS.json` identifies all public payloads by byte size and SHA256. There are three float32 response matrices with1200 trial rows and5130,4962,4218 native union-voxel columns. Metadata joins each row to its exact source trial, concept, image, session, run and full-source within-run position; voxel metadata preserves native row and voxel IDs and independent V1/IT masks. Voxel indices have meaning only within their original participant.

The repeated-image panel contains100 concepts and the same image for each concept across12sessions. Both the neural responses and independent human property labels are inputs to this investigation. Any holdout in the analysis is internal and must follow TASK.md. Repeated-image evaluation is not new-exemplar or new-person generalization. No outcome-selected voxel subset, full-data response reliability estimate or learned image feature is supplied.

The full source shared with NEURAL051 contains all9840 native trials for the complete V1/IT union. This task packet includes all1200 author-designated repeated trials. The native HDF5 column labels were decoded by a nonexecuting symbolic grammar and exactly joined to trial IDs0..9839 before copying. Immutable object versions and exact byte ranges establish which native rows were acquired; the full15–17GB HDF5 objects were not downloaded or independently whole-file hashed. Selected raw ranges and local outputs have recorded SHA256 identities.

`FEATURE_PROTOCOL.md` defines15 image-only descriptors from exact100 source photographs. The descriptors are provided, so no image model or feature fitting is required. They control only the stated low-level statistics. They do not exhaust shape, texture, object category or acquisition confounds.
