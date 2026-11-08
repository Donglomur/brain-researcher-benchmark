"""Future exact paired-mode training/query packets and private target custody.

All packet construction is operator-only. Public author inputs are the training
metadata and training array, never the CaseFiles mapping or its query/target
paths. Qualified namespaces must enforce this separation in actual execution.
"""
from pathlib import Path
from cohort import CANONICAL, ARMS, require, validate_roster, make_case_metadata
from io_support import admit_full_run, object_digest
from storage import write_array_fresh, write_json_fresh, read_array_exact, read_json_exact


def arm_matrix(features, arm):
    import numpy as np
    require(set(features) == {"neural", "ocular"}, "Only canonical base feature views")
    require(features["neural"].shape == (88992, 542) and features["ocular"].shape == (88992, 6),
            "Full original experimental feature support")
    if arm == "neural":
        return features["neural"]
    if arm == "ocular":
        return features["ocular"]
    if arm == "joint":
        return np.column_stack((features["neural"], features["ocular"]))
    require(arm == "neural_availability", "Named feature arm")
    return features["neural"][:, 271:]


def prepare_case_store(rows, features, alias, study_nonce, output_root, permit,
                        expected_bindings, approved_receipts, budget):
    """48 paired-mode cases plus16 independent-reference cases, complete support.

    Different replications/folds/arms get different aliases. The two modes share
    one readonly paired-case storage identity, never mutable fitted state. The
    independent-reference alias scope is separate but scientific image/person
    memberships are identical. No candidate sees an original participant name.
    """
    import numpy as np
    admit_full_run(permit, expected_bindings, approved_receipts, "prepare_views")
    validate_roster(rows)
    require(isinstance(study_nonce, str) and study_nonce, "Predeclared alias scope")
    require(expected_bindings.get("study_nonce") == study_nonce and
            expected_bindings.get("original_preparation") is not None, "Admitted original preparation/alias binding")
    output_root = Path(output_root)
    require(not output_root.exists(), "Fresh isolated operator case store")
    output_root.mkdir(parents=False)
    result = {}
    for role in ("reference", "rep0", "rep1", "rep2"):
        for fold, held in enumerate(CANONICAL.people):
            for arm in ARMS:
                scope = f"{study_nonce}/{role}/fold{fold}/{arm}"
                packet, query, train, held_indices = make_case_metadata(rows, held, scope, alias)
                case_dir = output_root / packet["case_id"]
                case_dir.mkdir()
                x = arm_matrix(features, arm)
                training = np.asarray(x[list(train)], dtype=np.float32)
                queries = np.asarray(x[list(held_indices)], dtype=np.float32)
                labels = np.asarray([rows[i]["category_id"] for i in held_indices], dtype=np.int32)
                require(np.isfinite(training).all() and np.isfinite(queries).all(), "Finite complete prepared views")
                public = case_dir / "author_training_only"
                sealed = case_dir / "operator_query_only"
                protected = case_dir / "protected_targets_only"
                for path in (public, sealed, protected):
                    path.mkdir()
                training_pin = write_array_fresh(public / "training.npy", training, budget)
                metadata_pin = write_json_fresh(public / "training.json", packet, budget)
                query_pin = write_array_fresh(sealed / "query.npy", queries, budget)
                query_meta = write_json_fresh(sealed / "query_support.json", query, budget)
                target_pin = write_array_fresh(protected / "targets.npy", labels, budget)
                result[role, fold, arm] = {"training": training_pin, "training_metadata": metadata_pin,
                                          "query": query_pin, "query_descriptor": query_meta,
                                          "protected_targets": target_pin, "case_id": packet["case_id"],
                                          "scientific_membership": {"fold": fold, "arm": arm},
                                          "training_support_digest": object_digest(packet)}
                del training, queries, labels, x
    require(len(result) == 64, "All paired replication and reference views")
    return result


def training_case(files, budget):
    packet = read_json_exact(files["training_metadata"]["path"], files["training_metadata"], budget)
    arm = files["scientific_membership"]["arm"]
    matrix = read_array_exact(files["training"]["path"], files["training"], (55620, ARMS[arm]), budget)
    require(object_digest(packet) == files["training_support_digest"], "Exact public training support")
    return matrix, packet


def candidate_training_loader(case_files, budget):
    def load(case):
        return training_case(case_files[f"rep{case['replication']}", case["fold_ordinal"], case["arm"]], budget)
    return load


def reference_training_loader(case_files, budget):
    def load(fold, arm):
        return training_case(case_files["reference", fold, arm], budget)
    return load


def prediction_case_files(case_files, key):
    mode, replication_or_family, fold, arm = key
    role = "reference" if mode == "independent_reference" else f"rep{replication_or_family}"
    require(mode in ("independent_reference", "fixed_program", "training_investigation"), "Known case mode")
    return case_files[role, fold, arm]


def protected_target_loader(case_files, budget):
    """Create only inside separately qualified grader custody, after panel gate."""
    def load(expected_descriptors):
        import numpy as np
        result = {}
        for key, expected in expected_descriptors.items():
            files = prediction_case_files(case_files, key)
            actual = read_json_exact(files["query_descriptor"]["path"], files["query_descriptor"], budget)
            require(actual == expected, "Protected targets bound to admitted query order")
            mapped = read_array_exact(files["protected_targets"]["path"], files["protected_targets"],
                                      (3708,), budget, kinds="iu", item_sizes=(4, 8))
            # These small labels total about2.4MB across160 cases. Copying and
            # releasing each map avoids another160 simultaneous file handles.
            result[key] = np.array(mapped, copy=True)
            del mapped
        return result
    return load
