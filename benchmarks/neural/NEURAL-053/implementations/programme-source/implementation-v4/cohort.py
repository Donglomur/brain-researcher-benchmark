"""Complete THINGS-MEG support and equally available training-only groups.

This module does not open source data, private keys, query answers or model APIs.
The explicit engineering profile exists for invented controls; production entry
points require CANONICAL. Public training packets contain no source identities.
"""
from dataclasses import dataclass
import hashlib
import hmac
from collections import Counter, defaultdict


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


@dataclass(frozen=True)
class Profile:
    classes: int = 1854
    sessions: int = 12
    runs: int = 10
    images: int = 12
    query_images: int = 2
    people: tuple = ("BIGMEG1", "BIGMEG2", "BIGMEG3", "BIGMEG4")
    engineering: bool = False

    @property
    def train_rows(self):
        return 3 * self.classes * (self.images - self.query_images)

    @property
    def query_rows(self):
        return self.classes * self.query_images


CANONICAL = Profile()
ARMS = {"neural": 542, "ocular": 6, "joint": 548,
        "neural_availability": 271}
MODES = ("fixed_program", "training_investigation")


def canonical_profile(profile):
    require(profile == CANONICAL, "Production requires the complete canonical profile")


def partition_images(image_to_class, profile=CANONICAL):
    groups = defaultdict(list)
    for image, category in image_to_class.items():
        require(type(image) is int and image > 0, "Positive integer source image")
        require(type(category) is int, "Integer category")
        groups[category].append(image)
    require(set(groups) == set(range(1, profile.classes + 1)), "Complete classes")
    require(all(len(v) == 12 for v in groups.values()), "Twelve exemplars per class")
    query, blocks = set(), {}
    for images in groups.values():
        order = sorted(images, key=lambda i: (
            hashlib.sha256(f"neural053-v1:{i}".encode()).digest(), i))
        query.update(order[:2])
        training = sorted(order[2:], key=lambda i: (
            hashlib.sha256(f"neural053-inner-v2:{i}".encode()).digest(), i))
        for rank, image in enumerate(training):
            blocks[image] = rank // 2
    return query, blocks


def validate_roster(rows, profile=CANONICAL):
    require(len(profile.people) == 4 and profile.images == 12 and
            profile.query_images == 2, "Four-person twelve/two-image design")
    require(len(rows) == 4 * profile.classes * 12, "All experimental rows required")
    identity = {}
    seen = set()
    per_person = defaultdict(list)
    previous = None
    for row in rows:
        for name in ("epoch_index", "session", "run", "image_id", "category_id"):
            require(type(row[name]) is int, f"Integral roster {name}")
        person = row["person"]
        require(person in profile.people, "Known person")
        key = (person, row["epoch_index"])
        require(row["epoch_index"] >= 0 and key not in seen, "Unique nonnegative epoch")
        require(previous is None or previous < key, "Canonical person/epoch order")
        previous = key
        seen.add(key)
        require(1 <= row["session"] <= profile.sessions and
                1 <= row["run"] <= profile.runs, "Full source session/run domain")
        image, category = row["image_id"], row["category_id"]
        require(image not in identity or identity[image] == category, "One image/class")
        identity[image] = category
        per_person[person].append(row)
    query, blocks = partition_images(identity, profile)
    expected_runs = {(s, r) for s in range(1, profile.sessions + 1)
                     for r in range(1, profile.runs + 1)}
    for person in profile.people:
        owned = per_person[person]
        require(len(owned) == profile.classes * 12, "Every person's complete cohort")
        require({r["image_id"] for r in owned} == set(identity), "Same exact images per person")
        require(Counter(r["category_id"] for r in owned) ==
                {c: 12 for c in range(1, profile.classes + 1)}, "Balanced class exemplars")
        require({(r["session"], r["run"]) for r in owned} == expected_runs,
                "No session/run exclusion, including BIGMEG4 session02")
        for row in owned:
            require(row["partition"] == ("query" if row["image_id"] in query else "training"),
                    "Exact stimulus-only global outer partition")
    return {"image_to_class": identity, "query_images": query, "training_blocks": blocks}


def make_aliaser(secret):
    """Operator-only key injection; never reads or returns a key file/body.

    Engineering tests may pass an explicitly invented key. Real keys must remain
    inside the separately qualified trusted operator, outside author contexts.
    """
    require(isinstance(secret, bytes) and len(secret) >= 32, "Operator alias-key extent")

    def alias(scope, kind, value):
        import json
        msg = json.dumps(["NEURAL053-v2", scope, kind, value],
                         separators=(",", ":"), ensure_ascii=True).encode()
        return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:32]
    return alias


def case_indices(rows, held_person, profile=CANONICAL):
    require(held_person in profile.people, "Known held person")
    train = [i for i, r in enumerate(rows)
             if r["person"] != held_person and r["partition"] == "training"]
    query = [i for i, r in enumerate(rows)
             if r["person"] == held_person and r["partition"] == "query"]
    require(len(train) == profile.train_rows and len(query) == profile.query_rows,
            "Complete held-person/unseen-image support")
    require(not {rows[i]["image_id"] for i in train} &
            {rows[i]["image_id"] for i in query}, "No query-image copies in fit")
    return train, query


def make_case_metadata(rows, held_person, scope, alias, profile=CANONICAL):
    """Returns public training metadata and separate operator-only query metadata.

    The caller uses the same scope for a paired mode comparison, and a different
    scope for each fold/arm/author replication. Raw fold names never enter public
    training metadata. The query descriptor has no labels or image groups.
    """
    checked = validate_roster(rows, profile)
    train, query = case_indices(rows, held_person, profile)
    row_id = lambda i: alias(scope, "row", [rows[i]["person"], rows[i]["image_id"]])
    train = sorted(train, key=row_id)
    query = sorted(query, key=row_id)
    ids = [row_id(i) for i in train + query]
    require(len(set(ids)) == len(ids), "No opaque ID collision")
    groups = [{"training_id": row_id(i),
               "person_group": alias(scope, "person", rows[i]["person"]),
               "image_group": alias(scope, "image", rows[i]["image_id"]),
               "image_block": checked["training_blocks"][rows[i]["image_id"]]}
              for i in train]
    public = {"schema": "neural053_training_v2",
              "case_id": alias(scope, "case", "opaque"),
              "classes": list(range(1, profile.classes + 1)),
              "training_ids": [row_id(i) for i in train],
              "training_labels": [rows[i]["category_id"] for i in train],
              "groups": groups}
    validate_training_metadata(public, profile)
    query_meta = {"schema": "neural053_query_support_v2", "case_id": public["case_id"],
                  "query_ids": [row_id(i) for i in query], "classes": public["classes"]}
    return public, query_meta, tuple(train), tuple(query)


def validate_training_metadata(packet, profile=CANONICAL):
    require(set(packet) == {"schema", "case_id", "classes", "training_ids",
                            "training_labels", "groups"}, "Exact training metadata fields")
    require(packet["schema"] == "neural053_training_v2", "Training schema")
    ids, labels, groups = packet["training_ids"], packet["training_labels"], packet["groups"]
    require(packet["classes"] == list(range(1, profile.classes + 1)), "Complete class order")
    require(len(ids) == len(labels) == len(groups) == profile.train_rows, "Complete training rows")
    require(len(set(ids)) == len(ids) and ids == sorted(ids), "Unique canonical opaque IDs")
    images, persons, block_classes = defaultdict(list), set(), defaultdict(set)
    for tid, label, g in zip(ids, labels, groups):
        require(type(label) is int and label in packet["classes"], "Training label domain")
        require(set(g) == {"training_id", "person_group", "image_group", "image_block"},
                "No query/source identity metadata")
        require(g["training_id"] == tid and type(g["image_block"]) is int and
                0 <= g["image_block"] < 5, "Row-aligned block identity")
        require(all(isinstance(g[k], str) and len(g[k]) == 32 and
                    all(c in "0123456789abcdef" for c in g[k])
                    for k in ("training_id", "person_group", "image_group")), "Opaque group aliases")
        images[g["image_group"]].append((g["person_group"], label, g["image_block"]))
        persons.add(g["person_group"])
        block_classes[(label, g["image_block"])].add(g["image_group"])
    require(len(persons) == 3 and len(images) == profile.classes * 10, "Three people/ten images per class")
    for copies in images.values():
        require(len(copies) == 3 and {x[0] for x in copies} == persons and
                len({x[1:] for x in copies}) == 1, "One identical-image copy per training person")
    require(set(block_classes) == {(c, b) for c in packet["classes"] for b in range(5)} and
            all(len(x) == 2 for x in block_classes.values()), "Two class images per block")
    require(Counter(labels) == {c: 30 for c in packet["classes"]}, "Thirty training rows per class")
    return True


def inner_splits(packet, profile=CANONICAL):
    validate_training_metadata(packet, profile)
    groups = packet["groups"]
    splits = []
    for person in sorted({g["person_group"] for g in groups}):
        for block in range(5):
            fit = tuple(i for i, g in enumerate(groups)
                        if g["person_group"] != person and g["image_block"] != block)
            valid = tuple(i for i, g in enumerate(groups)
                          if g["person_group"] == person and g["image_block"] == block)
            require(len(fit) == 16 * profile.classes and len(valid) == 2 * profile.classes,
                    "Complete 29,664/3,708 canonical nested split")
            require(not {groups[i]["image_group"] for i in fit} &
                    {groups[i]["image_group"] for i in valid}, "No repeated-image leakage")
            splits.append({"held_person_group": person, "held_image_block": block,
                           "fit_indices": fit, "validation_indices": valid})
    require(Counter(i for s in splits for i in s["validation_indices"]) ==
            {i: 1 for i in range(profile.train_rows)}, "Each outer training row validates once")
    return tuple(splits)


def study_plan():
    contexts = [{"mode": mode, "replication": rep, "fold_ordinal": fold, "arm": arm}
                for mode in MODES for rep in range(3) for fold in range(4) for arm in ARMS]
    references = [{"fold_ordinal": f, "arm": a, "inner_fits": 240,
                   "selected_family_refits": 3, "centroid_fits": 1}
                  for f in range(4) for a in ARMS]
    return {"schema": "neural053_full_study_v2", "contexts": contexts,
            "reference_cases": references, "author_contexts": len(contexts),
            "prospective_reference_fits": sum(244 for _ in references),
            "candidate_matrices": 96, "reference_matrices": 64,
            "query_rows_per_case": 3708, "classes": 1854,
            "scientific_execution": False, "canonical_task_count": 1}
