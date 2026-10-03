"""Retired historical answer-bank builder; never reads or writes evidence.

The v2 builder copied oracle arrays behind an unauthenticated receipt. The repaired
task instead reconstructs the original-source primitives and checks the public
numerical contract. Keeping this explicit refusal avoids silently regenerating
an obsolete bank when following an old authoring note.
"""


def main():
    raise SystemExit(
        "Reference banks are retired for GRADIENT-001. Validate pinned original "
        "sources and run the source-bound verifier; do not regenerate reference_v2.npz."
    )


if __name__ == "__main__":
    main()
