# Dependency recipe

CPython3.12 with `requirements.txt` gives the proposed projection/reference/
grading environment. NumPy2.2.6 and h5py3.13.0 were used only for authenticated
input preparation and generated fixtures. Future operator installation:

```
python3.12 -m venv ENV
ENV/bin/python -m pip install -r public/requirements.txt
```

Set OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. No GPU,
checkpoint, network, MATLAB, Caffe, sparse-regression toolbox or bdpy installation
is required by the new task implementation. Pinned BdPy source is retained for
layout provenance, not imported. This is a version-pinned recipe, not a built
portable image or hashlocked wheelhouse. BLAS/OS/runtime and numerical fit parity
are not qualified. No model has been fitted or downloaded during construction.
