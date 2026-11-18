# SBIND: historical code-tree correspondence

The publisher identifies the [SBIND author repository](https://github.com/ShanechiLab/SBIND/) as related software for [Hosseini and Shanechi, ICML 2025](https://proceedings.mlr.press/v267/hosseini25a.html). The paper link is unversioned. This note connects the registered code snapshot to earlier repository trees; it does not identify the exact execution that produced the paper tables.

The observed Git history is one complete 18-commit parent chain ending at the registered commit `c00e006dd298cb8c51d1543641fb3be77cc585ae`. We compared three untruncated recursive trees:

| Role | Commit | Git-reported committer date | Tree |
| --- | --- | --- | --- |
| Initial commit | `d2985a6679b072fbe4711e6deb39566012455b35` | 2025-05-27 | `1fbb251f326cc9eb6a840efda11a314c569d6e41` |
| Conference-period commit | `b1223a582cb2cdc56aed7412d22afe236fdb9bfe` | 2025-07-14 | `22dc806727a6e1aa2a3faf24a238218b8cde7c23` |
| Current registered commit | `c00e006dd298cb8c51d1543641fb3be77cc585ae` | 2026-06-24 | `90e407c58b159b1b6f12f85e75bd1231fd6d570f` |

All 44 original entries agree across these trees by path, mode, object ID and declared blob size. They include 34 blobs: 23 Python files (including the Python tutorial), requirements, the notebook, eight bytecode files and checkpoint metadata. The conference-period tree adds `README.md` and `LICENSE.md` to the initial tree. The registered tree changes only `README.md` from that conference-period tree. The [machine-readable comparison](historical-code-tree-identity.v1.json) records each entry and source-response identity.

This resolves a limited source-history question: the registered Python implementation is identical by Git blob identity to both inspected earlier trees. It therefore does not require inventing an older implementation merely because the registered commit is dated 2026. Git-reported dates alone do not prove when code became public, and endpoint comparisons do not assert that every intervening tree was unchanged.

The checkpoint remains an uninspected 22,709,873-byte Git blob in this inquiry. Its identical object ID is not evidence that it was trained on a particular original dataset or generated a paper table. No package installation, model execution, checkpoint loading or neural-data acquisition occurred.

Scientific admission remains unresolved. A complete same-task comparison still needs the original two widefield acquisition identities, all thirteen fUS session mappings, original folds, full preprocessing/aggregation and the paper's executable result-to-code connection. The unversioned software link and unchanged source cannot supply those missing records. The published full task, both information conditions, reproduction and improvement requirements, and existing readiness flags are unchanged.
