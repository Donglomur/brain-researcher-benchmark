"""Synthetic complete-support operands for one software-control campaign.

No original recording, reference prediction, source split realization, or
biological observation is read.  The signs of a deterministic generated signal
give analytical Pearson values -1 and +1.  These are software fixtures, never
scientific evidence, policy authority, or an eligible benchmark submission.
"""

import copy
import hashlib
import json


def generated_retinal_operands():
    """Return 147 sites, 232 ROI identities, and a complete 15,360-row split."""
    sites = []
    extra_roi_sites_remaining = 85
    for field in range(1, 16):
        next_roi = 1
        for local_site in range(10 if field <= 12 else 9):
            roi_count = 2 if extra_roi_sites_remaining else 1
            if extra_roi_sites_remaining:
                extra_roi_sites_remaining -= 1
            raw_roi_ids = list(range(next_roi, next_roi + roi_count))
            next_roi += roi_count
            sites.append({"field": field, "branch": local_site, "bin": 0,
                          "raw_roi_ids": raw_roi_ids})

    # Eight observations in each field, plus one in eight fields: 128 rows.
    test_rows = [1024 * (field - 1) + time_index
                 for field in range(1, 16)
                 for time_index in range(9 if field <= 8 else 8)]
    test_set = set(test_rows)
    remaining = [row for row in range(15360) if row not in test_set]
    splits = {"train": remaining[:12185], "val": remaining[12185:],
              "test": test_rows}
    site_keys = [[site["field"], site["branch"], site["bin"]]
                 for site in sites]
    masks, labels, author_predictions, candidate_predictions = [], [], [], []
    for row in test_rows:
        field = row // 1024 + 1
        value = float(row % 1024 + 1)
        observed = [int(site["field"] == field) for site in sites]
        masks.append(observed)
        labels.append([value if flag else None for flag in observed])
        # Unobserved predictions remain finite; their values are not scored.
        author_predictions.append([-value] * len(sites))
        candidate_predictions.append([value] * len(sites))

    operator = {"schema": "jaxley-retinal-target-v1", "cell_id": "20161028_1",
                "sites": sites, "splits": splits, "labels": labels,
                "mask": masks}
    author = {"schema": "jaxley-retinal-prediction-v1", "cell_id": "20161028_1",
              "test_row_ids": test_rows.copy(), "site_keys": copy.deepcopy(site_keys),
              "predictions": author_predictions}
    # Deliberately reorder both axes, so the real legacy identity alignment runs.
    candidate = {"schema": "jaxley-retinal-prediction-v1", "cell_id": "20161028_1",
                 "test_row_ids": list(reversed(test_rows)),
                 "site_keys": list(reversed(copy.deepcopy(site_keys))),
                 "predictions": [list(reversed(values))
                                 for values in reversed(candidate_predictions)]}
    return operator, author, candidate


def replace_candidate_site_with_constant(candidate, site_key, value=0.0):
    """Generated finite-but-undefined correlation; preserve packet identities."""
    altered = copy.deepcopy(candidate)
    column = altered["site_keys"].index(list(site_key))
    for row in altered["predictions"]:
        row[column] = value
    return altered


def generated_private_binding(np):
    """Full-size generated release fixture; NumPy is supplied only by the test.

    uint8 images and one current column keep the complete-shape fixture modest.
    This is a release-function check, not a valid model fit or source recording.
    """
    operator, _, _ = generated_retinal_operands()
    sites = copy.deepcopy(operator["sites"])
    splits = copy.deepcopy(operator["splits"])
    field = np.arange(15360) // 1024 + 1
    site_field = np.asarray([site["field"] for site in sites])
    mask = (field[:, None] == site_field[None, :]).astype(np.float64)
    labels = mask * (np.arange(15360) % 1024 + 1)[:, None]
    identity = {"sites": sites, "splits": splits}
    identity_sha256 = hashlib.sha256(json.dumps(
        identity, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()
    return {
        "schema": "jaxley-original-model-binding-v1",
        "noise": np.zeros((15360, 15, 20), dtype=np.uint8),
        "currents": np.zeros((15360, 1), dtype=np.float64),
        "labels": labels,
        "mask": mask,
        "sites": sites,
        "splits": splits,
        "identity_sha256": identity_sha256,
        "preprocessing_access": "whole cropped traces/all ROI delay selection before downstream split",
    }


def generated_validation_access_declaration():
    """A synthetic logical declaration; it is not physical execution authority."""
    body = b"generated-validation-target-access-declaration"
    return {
        "schema": "jaxley-retinal-validation-access-v2",
        "mode": "targets-visible-to-both",
        "approval": {"logical_name": "generated-validation-access-approval",
                     "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()},
        "author_validation_checkpoints": 21,
        "candidate_validation_query_limit": None,
    }
