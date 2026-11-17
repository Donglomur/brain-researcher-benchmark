# Versioned public metadata publisher

This additive package preserves the historical `../program/vendor_transport` bytes. New consumers can explicitly select the repaired publisher without invalidating older source pins.

The eight files in `vendor_transport/` exactly match the reviewed package from commit `003ee416c1e9d432ebfe241d3d6a1e65071d0613`. Only `bounds.py` differs from the predecessor: requested public files receive mode `0444` on their exclusively owned file descriptor before `fsync`, including under umask `077`. Private files/directories remain `0600`/`0700`.

Consumers must authenticate `ADOPTION.json`'s manifest identity and all seven module identities, then load this package under a distinct explicit importlib package name. The manifest and relative imports are package-local. The existing programme bootstrap and existing consumers still use their historical selection; adding this package does not switch them. The finite workflow owns its own explicit source bindings and runtime admission.

From repository root, in fresh processes:

```sh
python -I -S -B benchmarks/neural/NEURAL-007/implementations/whole-night-programme/provider-public-mode-v2/test_package_binding.py
python -I -S -B benchmarks/neural/NEURAL-007/implementations/whole-night-programme/provider-public-mode-v2/test_publication_modes.py
```

The two binding methods check exact package closure and coexistence with the historical publisher. The predecessor `0400` observation under `077` deliberately demonstrates its preserved behavior. The four publication tests retain the previously reviewed control bodies, changing only their import path. These generated tests do not launch Docker.

`ENGINEERING_RECEIPT.json` records one actual fixed trusted producer through the original Provider execute/archive/cleanup path and fresh recovery under the same original clock: exit0 in6.392seconds, all five owned Docker resources closed. All eight source files match the retained actual stage. This is an engineering observation for that exact role, image and command. It establishes no neural-data result, AI performance, arbitrary participant isolation or full benchmark readiness. The raw evidence remains external and is identified by size/hash; its recorded limitations and conservative accounting remain part of the receipt.
