# Source attribution and licenses

The benchmark's own source contribution is distributed under the repository's [MIT license](../../../LICENSE). The original ZuCo reader material and the reader-derived mapping retain their upstream attribution and CC-BY-4.0 terms; they are not represented as newly MIT-licensed upstream code.

ZuCo 2.0 was created by Nora Hollenstein, Marius Troendle, Ce Zhang and Nicolas Langer. Source: [ZuCo 2.0 project](https://osf.io/2urht/); citation: [ZuCo 2.0: A Dataset of Physiological Recordings During Natural Reading and Annotation, LREC 2020, pp. 138–146](https://aclanthology.org/2020.lrec-1.18/).

The project's [OSF metadata](https://api.osf.io/v2/nodes/2urht/) associates it with [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). The complete retained license text is in LICENSES/CC-BY-4.0.txt. Public reader sources are [data_loading_helpers.py, version 1](https://osf.io/hbt7s) and [read_matlab_files.py, version 1](https://osf.io/dvfsc). Their exact source identities appear in normative/PUBLIC_SOURCE_PROVENANCE.json.

The current zuco/extract.py mapping is modified and derived from those original reader conventions. It adds explicit source/axis bindings, complete original-slot accounting, qualified geometry requirements and guarded reads; it does not implement missing original cleaning, interpolation, ICA/MARA, Hilbert, FRP or fixation-segmentation operators. The two original reader files are not copied into this package. Historical source provenance is retained as described in normative/PUBLIC_SOURCE_PROVENANCE.json.

No upstream endorsement is implied. CC-BY-4.0 attribution, modification and license notices continue to apply to the upstream-derived material. The repository MIT license does not replace them. The paper, data, stimuli, trained models and separate native tools have distinct terms and are not redistributed here. G26 remains unresolved for complete benchmark qualification.

NumPy, SciPy, h5py, scikit-learn and PyTorch are external imports; their distributions, binary dependencies and model weights are not bundled. This source-only package supplies no qualified native environment or universal dependency license.
