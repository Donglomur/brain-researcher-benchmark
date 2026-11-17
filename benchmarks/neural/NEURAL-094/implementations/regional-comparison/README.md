# NEURAL-094 portable regional comparison source

This component preserves one full neural-data assignment: 39 sessions, 10 mice,
73 regional labels, 2,628 pairs and five seeds, with the whole-population primary
and frozen-program versus investigator-policy comparison. It supplies source,
not study inputs, fitted references, model credentials or scientific results.
All execution and scientific qualification remains unavailable.

Read complete_regional/README.md for the scientific contract and
complete_regional/INSTALLED_INTERFACE.md for the exact source and caller layout.
The 35-file component is deliberately closed. Keep this README, attribution,
license and test outside that directory; extra files inside cause inspection to
refuse. All28 Python bodies, including eight numerical modules, are unchanged.
Only six documentation/provenance/inventory bodies were projected for public use.

From this directory, a source-only inspection uses these release operands:

```sh
python3 -I -B complete_regional/operator.py inspect \
  --source-bytes 5851 \
  --source-sha256 e3595f43bafff2400788ca62bddd30c7763ee7a9a7a83f35f4b92afdaa79d6be \
  --read-bytes 378528 --write-bytes 4096 --seconds 30
```

This reads all source bodies without importing scientific modules. The expected
manifest pin must come from a trusted release; computing it from an untrusted
local manifest is not independent authentication. Historical installed state
names in the output do not certify registry installation.

Portable engineering controls use only the standard library:

```sh
python3 -I -B test_portable_source.py
```

They exercise the complete source inspector, actual29-to33 source materialization,
three fixed capsules, early authentication refusals, transport-copy parity and
namespace restoration using invented module bodies. No numerical/native module,
candidate program, container, provider or estimator is executed. The numeric
allowances in this test are invented source-control limits, not full-study
resource recommendations. Refer to ATTRIBUTION.md and LICENSE for provenance
and source terms; the original data and private admission inputs remain external.
