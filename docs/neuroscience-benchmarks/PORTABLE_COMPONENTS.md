# Portable source packages

These packages supply reviewed source, generated correctness checks and operator
interfaces. They do not supply a qualified native environment, authentic neural
datasets or new agent results. The checks below run on POSIX systems such as
Linux/macOS; Windows-native execution is not claimed. Hosted source CI uses Ubuntu.

| Package | Preserved scope | Required beyond source checks |
| --- | --- | --- |
| [NEURAL-061](../../benchmarks/neuroscience/neural061-persistent-state/README.md) | 423 source sessions, 29 evaluation sessions, six references, ten seeds and both BR/BC arms; persistent fitted state remains in its isolated child | Authentic inputs/targets, qualified native environment, provider/capture/allocation provenance and independent outside observation |
| [CBraMod / PAPER-paper-method-024](../../benchmarks/neuroscience/cbramod-paired-program/README.md) | 12 datasets; 800 reproduction artifacts, 60 improvement cases and 420 comparator slots per condition | All 65 exact external official-code files, authentic data/reference lineage, native execution and 8GB output capacity qualification |

The source checks preserve the complete declared populations using generated
controls. They do not establish broad paper reproduction, neural understanding,
scientific improvement or a higher finished-benchmark count.

## Run the generated source checks

Use a reviewed checkout. The release's trusted verifier pins are:

| Verifier | Bytes | SHA-256 |
| --- | ---: | --- |
| NEURAL-061 verify_source.py | 13111 | caef56e76cee96dde96c960e414f49b9e9b36a9f6f381c1c5f8c31f9d35c6fd0 |
| CBraMod verify_source.py | 10037 | 7cff2ade21783c057c68459d60f1a6453e2ba5ef3fe9e83612a763f32e680b77 |

Authenticate the verifier against that independently trusted release before
executing it; a verifier cannot authenticate its own bootstrap. The
[CI workflow](../../.github/workflows/portable-benchmark-source.yml) authenticates
and executes captured verifier bytes, then verifies the package before tests.
From the repository root:

```sh
python3 -I -S -B benchmarks/neuroscience/neural061-persistent-state/verify_source.py   --manifest-bytes 7808   --manifest-sha256 a9ad5d89c13cd5c9fb1789848329fc9ce7895a2f9b4765fb1e0f3fb042b6bcfb --check

python3 -I -S -B benchmarks/neuroscience/cbramod-paired-program/verify_source.py check-package   --manifest-bytes 9771   --manifest-sha256 5f4414b4e7569e299edb718bbca49f21049947ac2fc514aded3aa04da71204dd
```

NEURAL-061 runs 26 generated methods. CBraMod's public-only command runs eight
packaging methods. Its full 24-method generated executor check additionally needs
the pinned external official-code checkout and NumPy; see its package guide.
The offline importer verifies all 65 official files before writing a fresh complete
103-role runtime. It performs no automatic downloads. The official code remains
external because file-level license headers differ from its top-level license.

No dataset, Docker image or model is downloaded by these source-check commands.
Failure or a missing prerequisite is not permission to bypass an admission check.
