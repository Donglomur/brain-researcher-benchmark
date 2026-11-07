# Current local release status

The NEURAL-017 **candidate handoff bundle is assembled and independently reviewed**. Its six public files total 113,615,924 bytes. Start with the [candidate guide](../../../artifacts-build/neural017-public-author-001/public/CANDIDATE.md); the same folder contains numerical instructions, schema, licenses and `public.npz`. This local artifact folder is not stored in Git.

The [bundle results](../../../authoring/nlb-cosmoothing/author-bundle-recovery-v2/RESULTS.md) preserve both failed final-rename attempts and the successful reviewed recovery. Only two instruction documents were clarified; data, metrics and qualified execution code are unchanged. No new model or program run occurred for packaging.

The existing **same-machine clean-copy rehearsal passed**: the unchanged qualified program runner and scorer worked from an exact enumerated workspace, retained the established numerical result, and removed all owned resources. See [completed execution evidence](../../../authoring/nlb-cosmoothing/clean-copy-v1/RESULTS.md) and the [operator setup](../../../authoring/nlb-cosmoothing/local-release-v1/OPERATOR_SETUP.md). Historical source guides remain preserved; use the materialized candidate guide for the current prose clarification.

The common entry point remains `python3 tools/neurobench.py run NEURAL-017 --program PROGRAM --output FRESH_OUTPUT --dry-run`. Its historical reservation is not an evergreen allocation. Each new execution needs current reservations and the qualified wrapper described in the setup guide.

Deliver only the public folder through a restricted author workspace or mount. Its readonly modes and public-only contents do not prevent browsing parent directories; this page and operator evidence are not candidate inputs.

This remains one exposed, retrospective, single-session development task. No new runner/reference is counted, and no independent author attempt, general-host portability, protected final test, broad capability or full research qualification is claimed.
