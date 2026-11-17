"""THINGS-MEG shared-image joins; metadata only, without category target values.

The existing per-person marginal counts do not identify the same source image
across people. This check binds image ID, concept ID and source image path before
any derivative extraction or feature issuer can use that join.
"""
from collections import Counter
import hashlib
import json


PEOPLE = tuple(f"BIGMEG{i}" for i in range(1, 5))


class IdentityError(ValueError):
    """A source roster cannot support the registered shared-image comparison."""


def require(condition, message):
    if not condition:
        raise IdentityError(message)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def validate_roster(rows, *, image_order=None, images=None):
    """Validate the full registered roster and return a target-free identity hash.

    ``image_order`` is the prepared visual-array row order. ``images`` is the
    original extraction image manifest. Either is optional for a roster-only
    check; adapters require the relevant one before passing to the predecessor.
    The digest commits ordered metadata, never measurements or category labels.
    """
    require(type(rows) is list and len(rows) == 108192,
            "All 108192 original trial dispositions are required")
    grouped = {person: [] for person in PEOPLE}
    for row in rows:
        require(type(row) is dict and row.get("person") in grouped,
                "Every source row must have an original person identity")
        require(integer(row.get("epoch_index"), 0, 27047), "Original epoch index")
        require(integer(row.get("session"), 1, 12), "Original session ordinal")
        require(integer(row.get("run"), 1, 10), "Original run ordinal")
        require(row.get("trial_type") in ("exp", "repeat", "catch"),
                "Original trial disposition")
        grouped[row["person"]].append(row)

    identities = {}
    path_ids = {}
    expected_images = None
    for person in PEOPLE:
        person_rows = grouped[person]
        require(len(person_rows) == 27048 and
                {row["epoch_index"] for row in person_rows} == set(range(27048)),
                "Each person must have every original epoch exactly once")
        require(Counter(row["trial_type"] for row in person_rows) ==
                Counter({"exp": 22248, "repeat": 2400, "catch": 2400}),
                "Complete original trial dispositions per person")
        require({(row["session"], row["run"]) for row in person_rows} ==
                {(session, run) for session in range(1, 13) for run in range(1, 11)},
                "All 12 sessions and 10 runs per person")
        experimental = [row for row in person_rows if row["trial_type"] == "exp"]
        person_images = set()
        for row in experimental:
            image = row.get("image")
            concept = row.get("concept")
            path = row.get("image_path")
            require(type(image) is int and image > 0, "Positive original image ID")
            require(integer(concept, 1, 1854), "Original concept ID")
            require(type(path) is str and bool(path.strip()), "Original image path")
            require(image not in person_images, "Duplicate experimental image within person")
            person_images.add(image)
            identity = (concept, path)
            require(image not in identities or identities[image] == identity,
                    "Shared image has inconsistent concept or source path across people")
            require(path not in path_ids or path_ids[path] == image,
                    "One source image path resolves to multiple image IDs")
            identities[image] = identity
            path_ids[path] = image
        require(Counter(row["concept"] for row in experimental) ==
                Counter({concept: 12 for concept in range(1, 1855)}),
                "Exactly 12 exemplars per concept and person")
        require(Counter((row["session"], row["concept"]) for row in experimental) ==
                Counter({(session, concept): 1 for session in range(1, 13)
                         for concept in range(1, 1855)}),
                "One experimental exemplar per concept in every session")
        if expected_images is None:
            expected_images = person_images
        require(person_images == expected_images,
                "All four people must share the exact 22248 source images")

    require(len(identities) == 22248, "Complete shared image bank")
    if image_order is not None:
        require(type(image_order) is list and len(image_order) == 22248 and
                all(type(image) is int for image in image_order) and
                len(set(image_order)) == 22248 and set(image_order) == expected_images,
                "Prepared visual row order must contain each shared image exactly once")
    if images is not None:
        require(type(images) is list and len(images) == 22248, "Complete extraction image manifest")
        seen = set()
        for record in images:
            require(type(record) is dict and type(record.get("image")) is int,
                    "Extraction image identity")
            image = record["image"]
            require(image in identities and image not in seen,
                    "Extraction image manifest must join each shared image exactly once")
            require(record.get("image_path") == identities[image][1],
                    "Extraction manifest source path differs from shared image identity")
            seen.add(image)

    canonical = [[image, *identities[image]] for image in sorted(identities)]
    body = (json.dumps(canonical, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
    return {"schema": "n054_shared_image_identity_v2", "people": 4,
            "recorded_rows": 108192, "experimental_rows": 88992,
            "shared_images": 22248, "concepts": 1854,
            "image_identity_sha256": hashlib.sha256(body).hexdigest()}
