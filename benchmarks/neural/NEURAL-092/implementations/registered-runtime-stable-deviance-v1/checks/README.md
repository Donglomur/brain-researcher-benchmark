# NEURAL-092 public boundary checks

Run these controls from an existing POSIX CPython environment, using only its
standard library:

```sh
python -I -S -B benchmarks/neural/NEURAL-092/implementations/registered-runtime-stable-deviance-v1/checks/test_public_contract.py --work-root /tmp/neural092-public-checks-unique
```

The work directory must not exist. Choose an owned fresh path for each run.
The default runtime is the enclosing implementation directory; `--runtime-root`
selects another complete installation. `--report` optionally writes a fresh
JSON report of at most 8 KiB. CI should supervise the entire process group with
a finite wall-time budget. Each of the three CLI children has a 20-second timeout.
The suite writes one 59-byte generated shadow-package initializer and no dataset.
The 8 KiB child-output threshold is checked after collection, so it is an
acceptance check, not a bounded capture or memory guarantee. The three frozen
CLI paths have finite metadata/error responses. A passing report describes only
its reported interpreter and platform; other combinations need their own run.

The six controls exercise inert central import, the real inspect CLI, refusal
of an unselected run, mutually exclusive CLI modes, refusal of an unregistered
instance of the original Selection class, and cleanup after an unselected
module import. A real raising regular package on the caller's search path
checks that the protected finder chooses the selected initializer-free
namespace first. It is an adversarial search-path fixture, not a replacement
scientific dependency. A Python call observer checks that the refusal reaches
neither the original issuer nor the native operator, and the authority registry
stays empty. Both successful context entry and failing nested calls must restore
the caller's search path and finder list.

These controls use the complete 50-role / 39-module runtime. They retain its
inactive flags and do not call the scientific `source/run.py` interface.
They require no NumPy, h5py, arrays, profile issuance, container, or neural data.
They do not replace numerical tests, qualify scientific dependencies or Linux
native execution, establish authentic 32-session resource bounds, or demonstrate
benchmark performance. POSIX portability is the supported contract; Windows is
outside this check.

An integrator must enroll the exact suite command against the complete runtime
and select its existing interpreter. Adding these files does not alter programme
source locks, the task's endpoint or metric, or any readiness authority.

