#!/usr/bin/env python3
"""Create only a generated four-image engineering control; never authentic data."""
import argparse
import copy
import json
from pathlib import Path
from grounding import TASK, SUBJECTS, ROLES, BRAINHUB_REVISION, IMAGE_TENSOR_SHA256, file_sha256


def build(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=False)
    annotations = {"0": {"person": [[0, 0, 1, 1]], "car": [[0, 0, .25, .25], [.5, .5, 1, 1]]},
                   "1": {"bottle": [[0, 0, 1, 1]]}, "2": {}, "3": {"cat": [[.5, .5, 1, 1]]}}
    image_order = {str(i): f"generated-stimulus-{i}" for i in range(4)}
    def write(name, obj):
        path = directory / name
        path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
        return path
    annotation_path = write("annotations.json", annotations)
    order_path = write("image_order.json", image_order)
    exposure = {"training_neural_sha256": "1" * 64, "pretrained_language_sha256": "2" * 64,
                "pretrained_image_sha256": "3" * 64, "prompt_sha256": "4" * 64,
                "training_subjects": list(SUBJECTS), "training_stimulus_ids": ["generated-training-only"],
                "training_presentations": 4}
    contract = {"task_id": TASK, "profile": "engineering_controls", "subject_design": "shared_subjects_1_2_5_7",
                "brainhub_revision": BRAINHUB_REVISION, "all_images_sha256": IMAGE_TENSOR_SHA256,
                "annotations_sha256": file_sha256(annotation_path), "image_order_sha256": file_sha256(order_path),
                "exposure": exposure, "runs": {}}
    for role in ROLES:
        responses = {"0": {"person": [], "car": []}, "1": {"bottle": []}, "3": {"cat": []}}
        if role == "candidate":
            responses = {image: {cat: [[boxes[0]]] for cat, boxes in cats.items()} for image, cats in annotations.items()}
            responses["0"]["person"] = [[[0, 0, 1, .5]]]
        elif role == "official_baseline":
            responses["1"]["bottle"] = [[[0, 0, 1, 1]]]
        run = {"model_id": f"generated-{role}", "exposure": copy.deepcopy(exposure), "responses": {},
               "neural_condition": "none" if role == "neural_free" else "permuted" if role == "shuffled_neural" else "observed"}
        run["checkpoint_sha256"] = ("6" if role == "official_baseline" else "5") * 64
        if role in ("neural_free", "shuffled_neural"):
            run["control_of"] = "candidate"
        for subject in SUBJECTS:
            name = f"{role}_{subject}.json"
            write(name, responses)
            run["responses"][subject] = name
        if role == "shuffled_neural":
            run["source_image_by_target"] = {s: {str(i): str((i + 1) % 4) for i in range(4)} for s in SUBJECTS}
        contract["runs"][role] = run
    return write("contract.json", contract)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(build(args.directory))
