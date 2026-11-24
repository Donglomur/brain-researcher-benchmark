"""Authenticate and extract pinned author notebook code without executing cells.

The generated text contains upstream syntax errors intentionally. This is source
provenance, not a model loader, training recipe repair or scientific qualification.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

REVISION = "305a4827929b2c6e82e44c5c69b2ea9d410e20a4"
SOURCES = (
    {"name": "testing", "path": "Demo (full-version)/DeepCaImX_testing_demo.ipynb",
     "bytes": 603568, "git_blob_sha1": "a89bc94b08ef4f3d2d745c94891b4e29500a5db5",
     "sha256": "17614fa17b799e04599e64517e21c302e119eb8623c02b1e3ef97ff6b9675c43",
     "export_sha256": "d53f1bdd30fb34fbfcc911c76c96321e69a89083cb25ed80a8bbd3516955fddb"},
    {"name": "training", "path": "Demo (full-version)/DeepCaImX_training_demo.ipynb",
     "bytes": 47339, "git_blob_sha1": "438bdc0e9282a0913ae4736689eb3dbcb832ec4f",
     "sha256": "d1e5af9dc0dea01333248d55a3b62ac2e32d7f4e4f3d1a864f1b415d91280632",
     "export_sha256": "457f5d26b6545534b4ac3744218a1a84a1249343bf3798d93c55e5fef9d46193"},
    {"name": "preprocessing", "path": "Preprocessing of Experimental Samples/Prepro_Exp_Sample.ipynb",
     "bytes": 74142, "git_blob_sha1": "532bee61e1e974d36c5f2f7e493fdccaf27f78d5",
     "sha256": "7c089110142aeba5c0ed18a657c3afdc677f55ed97c549109448fbe6127351de",
     "export_sha256": "84045db91852626b0eb3ddaa36860d35397d92be4508e1fa9b9454c6d2d57584"},
)


def extract(source: bytes, expected: dict) -> tuple[bytes, dict]:
    """Authenticate original bytes before JSON parsing; retain literal code only."""
    git_blob = hashlib.sha1(b"blob " + str(len(source)).encode("ascii") + b"\0" + source).hexdigest()
    if (len(source) != expected["bytes"]
            or hashlib.sha256(source).hexdigest() != expected["sha256"]
            or git_blob != expected["git_blob_sha1"]):
        raise ValueError("author notebook source identity mismatch")
    notebook = json.loads(source)
    fragments, cells = [], []
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        code = "".join(cell["source"])
        fragments.append(f"# Original code cell {index}\n" + code)
        finding = {"notebook_cell_index": index,
                   "source_utf8_bytes": len(code.encode("utf-8")),
                   "source_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest()}
        try:
            ast.parse(code)
        except SyntaxError as error:
            finding.update({"ast_parseable": False, "error_type": "SyntaxError",
                            "line_in_cell": error.lineno, "offset": error.offset,
                            "message": error.msg})
        else:
            finding["ast_parseable"] = True
        cells.append(finding)
    exported = ("\n\n".join(fragments) + "\n").encode("utf-8")
    digest = hashlib.sha256(exported).hexdigest()
    if digest != expected["export_sha256"]:
        raise ValueError("literal code export identity mismatch")
    receipt = {"name": expected["name"], "author_path": expected["path"],
               "source_bytes": len(source), "source_sha256": expected["sha256"],
               "source_git_blob_sha1": git_blob,
               "export_file": expected["name"] + ".source.py.txt",
               "export_bytes": len(exported), "export_sha256": digest,
               "code_cells": cells}
    return exported, receipt


def export_all(input_dir: Path, output_dir: Path) -> dict:
    """Require all three exact sources before creating a fresh output directory."""
    prepared = []
    for expected in SOURCES:
        path = input_dir / (expected["name"] + ".ipynb")
        with path.open("rb") as stream:
            original = stream.read(expected["bytes"] + 1)
        prepared.append(extract(original, expected))
    manifest = {"schema": "deepcaimx-authenticated-notebook-code/v1",
                "task_id": "PAPER-paper-method-013",
                "author_repository": "https://github.com/KangningZhang/DeepCaImX",
                "author_revision": REVISION,
                "extraction": "Code cells only, in notebook order; prefix each with '# Original code cell INDEX\n'; join with two newlines and append one final newline. Cell source characters are unchanged.",
                "ast_scope": "Static Python AST parsing only; no cell evaluation, imports, model loading or syntax repair. Parseability does not establish executable training or scientific equivalence.",
                "notebooks": [receipt for _, receipt in prepared],
                "notebook_outputs_included": False,
                "notebook_code_executed": False,
                "source_mapping_authenticated": False,
                "paper_checkpoint_equivalence": False,
                "native_model_execution": False,
                "scientific_qualification": "unestablished"}
    output_dir.mkdir(parents=False, exist_ok=False)
    for exported, receipt in prepared:
        (output_dir / receipt["export_file"]).write_bytes(exported)
    (output_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="External directory containing testing.ipynb, training.ipynb and preprocessing.ipynb")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="Fresh child directory whose parent already exists")
    args = parser.parse_args()
    manifest = export_all(args.input_dir, args.output_dir)
    print(json.dumps({"notebooks": len(manifest["notebooks"]), "executed": False}))


if __name__ == "__main__":
    main()
