"""Source-only native22 compiler, exact requests, and bounded selector primitives.

No execution happens on import. Native worker execution requires separate
authentic source/environment/data/resource admission. This module never calls
a scientific evaluator or imports either independent numerical reference.
"""
import base64
import hashlib
import json
import math
import re
from pathlib import PurePosixPath

PERSONS = tuple("sub-%02d" % n for n in range(1, 7))
Q = 127*1800
D = 15029136
WORKSPACE = "/tmp/n079-native"
VARIANTS = ("literal_cpu", "corrected_cuda_transfer")
FAMILIES = ("variance_vision", "variance_language", "unique_variance_vision", "unique_variance_language")
SOURCES = {
    "visual_features": ("paper_figure_5/01_extract_stimulus_vision_features.py", 13330, "553e59463324a4249441154e50869579b88845a4927679740da7b05288f49135"),
    "corrected_visual_features": ("corrected_cuda_transfer/01_extract_stimulus_vision_features.py", 13353, "09c740e8e8d50542cc9ccf224e762cc33645b7642265baa19bbe029ec0b7d3a5"),
    "language_features": ("paper_figure_5/01_extract_stimulus_language_features.py", 5031, "7dda5aae37bb53f03accc6c45843c384e407998f6c3fda15c6c82dc077138d6f"),
    "encoding": ("paper_figure_5/02_train_encoding.py", 4817, "faebdd4bee3f4bbaca9ecac92c8bacbd5a490cd41ba0c2e7bd134b916efd1c0a"),
    "partial": ("paper_figure_5/03_partial_correlation.py", 9524, "b094af19a4e75ad864a8ca3bf9404061343bfac81dbec21bd2d209687a116f78"),
    "statistics": ("paper_figure_5/04_stats.py", 5099, "7c44e14ad53bfc939b2be92f9c673f840d21d300d0f457c5853598ea74cb3cbc"),
    "plot": ("paper_figure_5/05_plot.py", 8572, "b123e8840dfcf3020aa4f6f57e09cf09729d60782cc02484def7065ef91a35f9"),
}
CAP_KEYS = ("request_bytes", "source_bytes", "capture_bytes", "artifact_bytes", "capture_elements", "index_bytes", "block_bytes")
VIEW_KEYS = ("common", "original_inputs", "native_compatibility", "original_native_target_names", "processed_epochs", "author_code", "oracle_capture_visible", "other_context_history_visible", "query_targets_visible")
EXECUTION_EVIDENCE = ("runtime_evidence", "environment_evidence", "input_support_evidence", "derivative_lineage_evidence", "model_weights_evidence", "native_allocation_evidence", "selector_admission_evidence", "workspace_admission_evidence")


class NativeError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(ok, code, message):
    if not ok:
        raise NativeError(code, message)


def fields(value, keys, name="record"):
    require(type(value) is dict and set(value) == set(keys), "schema", name+" requires exact keys")


def positive(value, name):
    require(type(value) is int and value > 0, "extent", name+" must be a positive integer")
    return value


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise NativeError("serialization", "finite JSON metadata required") from exc


def pin(raw):
    require(type(raw) is bytes, "pin", "pin input must be exact bytes")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def checked_pin(value):
    fields(value, ("bytes", "sha256"), "pin")
    require(type(value["bytes"]) is int and value["bytes"] >= 0 and type(value["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", value["sha256"]), "pin", "invalid exact byte/SHA-256 pin")
    return value


def relative_path(value):
    require(type(value) is str and value and "\\" not in value and "\x00" not in value, "path", "nonempty POSIX relative path required")
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(x not in ("", ".", "..") for x in value.split("/")) and str(p) == value, "path", "noncanonical or escaping path")
    return value


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", value), "identifier", "safe identifier required")
    return value


def source_record(source_id):
    require(source_id in SOURCES, "source", "source must be in the exact captured catalog")
    path, count, digest = SOURCES[source_id]
    record = {"id": source_id, "author_relative_path": path, "pin": {"bytes": count, "sha256": digest}}
    if source_id == "corrected_visual_features":
        record["literal_original"] = source_record("visual_features")
        record["correction"] = "One np.append operand gains .detach().cpu().numpy(); separately named source, not original execution or qualified numerical parity."
    return record


def native_jobs():
    rows = [{"id": "native-visual-features", "kind": "visual_features"}, {"id": "native-language-features", "kind": "language_features"}]
    rows += [{"id": "native-%s-%s" % (branch, person), "kind": branch+"_fit", "person": person} for branch in ("visual", "language") for person in PERSONS]
    rows += [{"id": "native-partial-"+person, "kind": "partial", "person": person} for person in PERSONS]
    return rows+[{"id": "native-statistics", "kind": "statistics"}, {"id": "native-plot", "kind": "plot"}]


def selector(root, *steps):
    return {"root": root, "steps": [{"kind": k, "value": v} for k, v in steps]}


def select_value(namespace, selected):
    """Read only named globals, dictionary keys, stored attributes, tuple indices.

    No eval, function call, descriptor/property lookup or selector expression.
    The exact selector must additionally join the immutable job catalog.
    """
    fields(selected, ("root", "steps"), "selector")
    root = selected["root"]
    require(type(root) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", root) and type(selected["steps"]) is list and len(selected["steps"]) <= 4, "selector", "invalid bounded selector")
    require(type(namespace) is dict and root in namespace, "missing_quantity", "source global is absent: "+root)
    value = namespace[root]
    for step in selected["steps"]:
        fields(step, ("kind", "value"), "selector step")
        kind, key = step["kind"], step["value"]
        if kind == "key":
            require(type(value) is dict and type(key) is str and key in value, "missing_quantity", "source dictionary key is absent")
            value = value[key]
        elif kind == "attribute":
            require(type(key) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key), "selector", "public stored attribute required")
            try:
                stored = object.__getattribute__(value, "__dict__")
            except (AttributeError, TypeError) as exc:
                raise NativeError("missing_quantity", "source object has no stored attributes") from exc
            require(type(stored) is dict and key in stored, "missing_quantity", "stored source attribute is absent; properties are not evaluated")
            value = stored[key]
        elif kind == "index":
            require(type(value) in (list, tuple) and type(key) is int and 0 <= key < len(value), "missing_quantity", "bounded source tuple/list index absent")
            value = value[key]
        else:
            raise NativeError("selector", "only key/attribute/index selectors are allowed")
    return value


def _quantity(name, selected, shape, source, encoding="numeric"):
    return {"id": name, "selector": selected, "selector_pin": pin(canonical(selected)), "shape": shape,
            "encoding": encoding, "source_pin": source["pin"], "source_id": source["id"],
            "provenance": "Exact named variable/key/stored attribute in the independently selected captured original source; units/support/reference/tolerance require independent admission."}


def job_spec(row, variant):
    require(row in native_jobs() and variant in VARIANTS, "job", "exact native22 roster and named variant required")
    kind = row["kind"]
    sid = "encoding" if kind.endswith("_fit") else kind
    if kind == "visual_features" and variant == "corrected_cuda_transfer": sid = "corrected_visual_features"
    src = source_record(sid)
    argv = ["/source/author/"+src["author_relative_path"]]
    if "person" in row: argv += ["--subject", str(int(row["person"][-2:]))]
    if kind.endswith("_fit"): argv += ["--modality", "vision" if kind == "visual_fit" else "language"]
    if kind == "visual_features": argv += ["--model_name", "s3d", "--batch_size", "4"]
    if kind == "language_features": argv += ["--model_name", "all-mpnet-base-v2"]
    if kind == "statistics": argv += ["--n_iter", "100000"]
    # --subjects is intentionally absent: the source's type=list parser is
    # preserved and its exact six-person default is used unchanged.
    argv += ["--emd_dir", WORKSPACE]
    quantities, files, dependencies, dims = [], [], [], {}
    def q(name, root, shape, *steps, encoding="numeric"):
        quantities.append(_quantity(name, selector(root, *steps), shape, src, encoding))
    def artifact(name, path): files.append({"id": name, "relative_path": path, "encoding": "opaque_original_bytes", "source_pin": src["pin"]})
    if kind == "visual_features":
        dims["visual_p"] = {"selector": selector("n_components_95"), "minimum": 1, "maximum": 1000}
        q("pca-count", "n_components_95", [])
        q("features-train", "features_train", [1000, "visual_p"])
        q("features-test", "features_test", [102, "visual_p"])
        q("pca-variance-ratio", "explained_variance_ratio", [1000])
        q("pca-all-axes", "principal_axes", [D, 1000])
        q("fitting-mean", "scaler", [D], ("attribute", "mean_"))
        q("fitting-scale", "scaler", [D], ("attribute", "scale_"))
        q("all17-nodes", "fe_nodes", None, encoding="json")
        q("ordered-videos", "dataset", None, ("attribute", "video_files"), encoding="json")
        q("selected-device", "device", None, encoding="json")
        for split in ("train", "test"): artifact("features-file-"+split, "results/stimulus_features/vision_features/s3d/vision_features_"+split+".npy")
    elif kind == "language_features":
        dims["language_p"] = {"selector": selector("n_components_95"), "minimum": 1, "maximum": 6000}
        dims["embedding_dim"] = {"selector": selector("embeddings_train_shape", ("index", 2)), "minimum": 1, "maximum": 6000}
        q("pca-count", "n_components_95", [])
        q("features-train", "embeddings_train", [1000, 6, "language_p"])
        q("features-test", "embeddings_test", [102, 6, "language_p"])
        q("pca-components", "pca", ["embedding_dim", "embedding_dim"], ("attribute", "components_"))
        q("pca-variance-ratio", "explained_variance_ratio", ["embedding_dim"])
        q("pca-mean", "pca", ["embedding_dim"], ("attribute", "mean_"))
        q("fitting-mean", "scaler", ["embedding_dim"], ("attribute", "mean_"))
        q("fitting-scale", "scaler", ["embedding_dim"], ("attribute", "scale_"))
        q("original-training-shape", "embeddings_train_shape", None, encoding="json")
        q("original-test-shape", "embeddings_test_shape", None, encoding="json")
        for split in ("train", "test"): artifact("features-file-"+split, "results/stimulus_features/language_features/all-mpnet-base-v2/language_features_"+split+".npy")
    elif kind.endswith("_fit"):
        branch = "visual" if kind == "visual_fit" else "language"
        dimensions = branch+"_p"
        dims[dimensions] = {"selector": selector("reg_param", ("key", "n_features_in_")), "minimum": 1, "maximum": 1000 if branch == "visual" else 6000}
        q("coefficients", "reg_param", [Q, dimensions], ("key", "coef_"))
        q("intercept", "reg_param", [Q], ("key", "intercept_"))
        q("feature-count", "reg_param", [], ("key", "n_features_in_"))
        q("native-training-target", "eeg_train", [1000 if branch == "visual" else 6000, Q])
        q("training-video-order", "video_conditions", [1000])
        dependencies = ["native-"+branch+"-features"]
        artifact("weights-file", "results/encoding_models/model_weights/weights_"+row["person"]+"_modality_"+("vision" if branch == "visual" else "language")+".npy")
    elif kind == "partial":
        for name in FAMILIES:
            key = "total_"+name if name.startswith("variance_") else name
            q(name.replace("_", "-"), "results", [127, 1800], ("key", key))
        q("vision-prediction", "eeg_test_pred_vision", [102, Q])
        q("language-prediction", "eeg_test_pred_language", [102, Q])
        q("native-test-target", "eeg_test", [102, Q])
        q("test-video-order", "video_conditions", [102])
        dependencies = ["native-visual-"+row["person"], "native-language-"+row["person"], "native-visual-features", "native-language-features"]
        artifact("partial-file", "results/encoding_models/partial_correlation/partial_correlation_"+row["person"]+".npy")
    elif kind == "statistics":
        for name in FAMILIES:
            q(name.replace("_", "-")+"-trajectories", "results_chan_avg", [6, 1800], ("key", name))
            q(name.replace("_", "-")+"-ci", "ci", [2, 1800], ("key", name))
            q(name.replace("_", "-")+"-bh-mask", "sig", [1800], ("key", name))
            q(name.replace("_", "-")+"-bootstrap", "ci_dist", [100000, 1800], ("key", name))
        q("times", "times", [1800]);q("channel-names", "ch_names", None, encoding="json")
        q("selected-channel-indices", "idx_ch", None, encoding="json")
        dependencies = ["native-partial-"+p for p in PERSONS]
        artifact("statistics-file", "results/encoding_models/stats/stats.npy")
    elif kind == "plot":
        for name in FAMILIES:
            q(name.replace("_", "-")+"-trajectories", "partial_correlation", [6, 1800], ("key", name))
            q(name.replace("_", "-")+"-ci", "ci", [2, 1800], ("key", name))
            q(name.replace("_", "-")+"-bh-mask", "sig", [1800], ("key", name))
        q("source-noise-ceiling", "noise_ceiling", [6, 1800])
        q("times", "times", [1800]);q("channel-names", "ch_names", None, encoding="json")
        q("selected-channel-indices", "idx_ch", None, encoding="json")
        dependencies = ["native-statistics"]
        for name in ("correlation", "partial_correlation"): artifact(name.replace("_", "-")+"-svg", "results/encoding_models/plots/"+name+".svg")
    dependency_files = {}
    for dep in dependencies:
        required_file = "features-file-train" if kind.endswith("_fit") else "features-file-test" if dep.endswith("-features") else "weights-file" if kind == "partial" else "partial-file" if kind == "statistics" else "statistics-file"
        dependency_files[dep] = [required_file]
    return {**row, "variant": variant, "source": src, "argv": argv, "workspace": WORKSPACE,
            "dimensions": dims, "quantities": quantities, "native_files": files, "dependencies": dependencies,
            "dependency_files": dependency_files}


def compile_program(selection):
    fields(selection, ("schema", "variant", "design_evidence"), "native source selection")
    require(selection["schema"] == "n079_native_source_selection_v1" and selection["variant"] in VARIANTS, "selection", "named source variant required")
    checked_pin(selection["design_evidence"])
    jobs = [job_spec(row, selection["variant"]) for row in native_jobs()]
    return {"schema": "n079_native_program_v1", "task": "NEURAL-079", "variant": selection["variant"],
            "design_evidence": selection["design_evidence"], "jobs": jobs,
            "scope": {"persons": list(PERSONS), "sessions": 48, "channels": 127, "times": 1800,
                      "feature_outputs": 17, "language_fit_rows": 6000, "language_test_caption_rows": 612,
                      "test_videos": 102, "correlation_arrays_per_person": 4, "bootstrap_draws": 100000, "BH_families": 4},
            "counts": {"jobs": 22, "native_OLS": 12, "native_normalization_applications": 144,
                       "nuisance_regressions": 5486400, "correlation_values": 5486400},
            "execution_ready": False, "missing_admissions": list(EXECUTION_EVIDENCE)+["independent_native_quantity_units_support_reference_tolerance", "independent_observer_closure"],
            "transductive_disclosure": "Original native EEG includes held responses; session-wide zscore precedes video filtering. query_targets_visible=False protects only the prospective prepared-target namespace.",
            "source_hazards": ["compute_ncsnr uses eeg_ses before assignment; derivative lineage is independently required", "original CPU and corrected CUDA transfer are distinct sources", "plot repeats first-subject noise ceiling and leaves its curve commented out", "statsmodels is imported but unpinned in author requirements", "original nan_to_num infinity/default and null PCA behavior remain unchanged"],
            "reproduction_policy": "Missing necessary evidence means incomplete. Native numerical mismatch is a retained outcome and does not suppress otherwise valid prospective grading. No whole-paper claim."}


def admit_execution(execution, job):
    fields(execution, ("interpreter", "interpreter_pin", "environment", "python_path", "caps", "evidence", "quantity_admissions", "native_file_admissions"), "native execution")
    interpreter = execution["interpreter"]
    require(type(interpreter) is str and interpreter.startswith("/") and ".." not in PurePosixPath(interpreter).parts and not interpreter.startswith(("/tmp/", "/data/", "/output/", "/request/", "/source/")), "runtime", "selected interpreter in the immutable runtime mount required")
    checked_pin(execution["interpreter_pin"])
    env = execution["environment"]
    require(type(env) is dict and all(type(k) is str and type(v) is str and k and "\x00" not in k+v and "=" not in k for k, v in env.items()), "environment", "exact finite environment mapping required")
    if job["variant"] == "literal_cpu": require(env.get("CUDA_VISIBLE_DEVICES") == "", "environment", "literal CPU source needs an independently admitted CPU-visible environment")
    require(type(execution["python_path"]) is list and execution["python_path"] and all(type(v) is str and v.startswith("/") and not v.startswith(("/tmp", "/output", "/data", "/request")) and ".." not in PurePosixPath(v).parts for v in execution["python_path"]), "runtime", "exact selected immutable Python import paths required")
    fields(execution["caps"], CAP_KEYS, "native caps")
    for key in CAP_KEYS: positive(execution["caps"][key], key)
    require(8 <= execution["caps"]["block_bytes"] <= execution["caps"]["artifact_bytes"] <= execution["caps"]["capture_bytes"], "extent", "complete-scalar and ordered block/artifact/total caps required")
    numeric_total = 0
    for quantity in job["quantities"]:
        if quantity["encoding"] == "numeric":
            upper_shape = [job["dimensions"][x]["maximum"] if type(x) is str else x for x in quantity["shape"]]
            count = math.prod(upper_shape)
            require(count <= execution["caps"]["capture_elements"] and 8*count <= execution["caps"]["artifact_bytes"], "extent", "full source-derived quantity maximum must fit capture caps before native launch")
            numeric_total += 8*count
    require(numeric_total <= execution["caps"]["capture_bytes"], "extent", "full source-derived numeric capture upper bound exceeds total cap before native launch")
    fields(execution["evidence"], EXECUTION_EVIDENCE, "independent native evidence")
    for value in execution["evidence"].values(): checked_pin(value)
    require(type(execution["quantity_admissions"]) is dict and set(execution["quantity_admissions"]) == {q["id"] for q in job["quantities"]}, "quantity_support", "every selected native quantity needs an independent units/support admission")
    for q in job["quantities"]:
        admitted = execution["quantity_admissions"][q["id"]]
        fields(admitted, ("selector_pin", "units", "units_evidence", "support_evidence"), "native quantity admission")
        require(admitted["selector_pin"] == q["selector_pin"] and type(admitted["units"]) is str and admitted["units"], "quantity_join", "exact selector and nonempty independently admitted unit label required")
        checked_pin(admitted["units_evidence"]);checked_pin(admitted["support_evidence"])
    require(type(execution["native_file_admissions"]) is dict and set(execution["native_file_admissions"]) == {f["id"] for f in job["native_files"]}, "file_support", "every exact native output file requires selection evidence")
    for value in execution["native_file_admissions"].values(): checked_pin(value)


def role_command(execution):
    caps = execution["caps"]
    command = [execution["interpreter"], "/source/native_worker.py", "--request", "/request/request.json", "--output", "/output"]
    for key in CAP_KEYS: command += ["--"+key.replace("_", "-"), str(caps[key])]
    return command


def make_dependency_record(index, index_pin, observer_evidence, promotions):
    """Join an actually observed worker index to immutable supervisor promotions.

    The owner supplies only closed JobSupervisor output and genuine promotion
    descriptors. This pure join cannot authenticate an arbitrary evidence pin.
    """
    checked_pin(index_pin);checked_pin(observer_evidence)
    require(pin(canonical(index)) == index_pin and index.get("schema") == "n079_native_capture_index_v1", "dependency", "exact independently observed native capture index required")
    require(index.get("native_execution", {}).get("status") == "returned" and index.get("capture_complete") is True, "dependency", "failed or incomplete native output cannot feed a later job")
    require(type(promotions) is dict, "dependency", "immutable output promotion descriptors required")
    native_files = {}
    for artifact in index["native_files"]:
        require(artifact.get("status") == "captured" and artifact["path"] in promotions, "dependency", "every original output must have a genuine immutable promotion")
        descriptor = promotions[artifact["path"]]
        require(type(descriptor) is dict and type(descriptor.get("path")) is str and {k: descriptor.get(k) for k in ("bytes", "sha256")} == artifact["pin"], "dependency", "promoted original bytes must match captured bytes")
        native_files[artifact["id"]] = {"native_relative_path": artifact["native_relative_path"], "descriptor": descriptor}
    return {"schema": "n079_native_dependency_v1", "job_id": index["job_id"], "variant": index["variant"],
            "source_pin": index["source_pin"], "context": index["context"], "request_pin": index["request_pin"],
            "capture_index_pin": index_pin, "observer_evidence": observer_evidence, "native_files": native_files}


def build_request(program, job_id, *, execution, context, work_id, worker_sources, selected_role_command, view, binding, view_evidence, program_evidence, dependencies):
    # Recompile the roster, rather than trusting caller-modified job specs.
    expected = compile_program({"schema": "n079_native_source_selection_v1", "variant": program.get("variant"), "design_evidence": program.get("design_evidence")})
    require(program == expected, "program_join", "program must equal the complete source-produced roster")
    matches = [j for j in program["jobs"] if j["id"] == job_id]
    require(len(matches) == 1 and type(context) is str and context and type(work_id) is str and work_id, "job", "one exact native22 job and fresh owner context/work allocation required")
    job = matches[0];admit_execution(execution, job)
    require(selected_role_command == role_command(execution), "command_join", "exact selected role_commands['native'] required")
    fields(view, VIEW_KEYS, "private native view")
    require(all(view[k] is False for k in ("oracle_capture_visible", "other_context_history_visible", "query_targets_visible")), "view", "protected prospective target/oracle/history namespaces must be absent")
    require(type(view["original_inputs"]) is dict and type(view["original_native_target_names"]) is dict, "view", "native input descriptor mapping and exact native path map required")
    inputs = {}
    for key, descriptor in view["original_inputs"].items():
        require(type(descriptor) is dict and type(descriptor.get("path")) is str, "view", "input descriptor path required")
        checked_pin({k: descriptor[k] for k in ("bytes", "sha256")})
        require(type(key) is str and key not in inputs, "view", "unique native input keys required")
        inputs[key] = descriptor
    names = view["original_native_target_names"]
    require(set(names) == set(inputs) and len(set(names.values())) == len(names), "view", "complete injective descriptor-to-native-path join required")
    links = []; by_target = {}; material_by_target = {}
    for name in sorted(inputs):
        target = relative_path(names[name]);require(target.startswith(("derivatives/", "stimuli/", "results/")), "view", "native workspace links must use original source paths")
        by_target[target] = {k: inputs[name][k] for k in ("bytes", "sha256")}
        material_by_target[target] = inputs[name]["path"]
    if view["processed_epochs"] is not None:
        require(type(view["processed_epochs"]) is dict and type(view["processed_epochs"].get("members")) is list, "view", "declared processed epoch members required")
        for descriptor in view["processed_epochs"]["members"]:
            target = relative_path(descriptor["path"]);actual_pin = checked_pin({k: descriptor[k] for k in ("bytes", "sha256")})
            require(target not in by_target or by_target[target] == actual_pin, "view", "contradictory processed epoch mount")
            by_target[target] = actual_pin
            material_by_target[target] = descriptor["path"]
    require(type(view["native_compatibility"]) is dict and type(view["native_compatibility"].get("aliases")) is list, "view", "explicit native compatibility alias list required")
    aliases = {}
    for alias in view["native_compatibility"]["aliases"]:
        fields(alias, ("canonical_target", "literal"), "native alias")
        target, literal = relative_path(alias["canonical_target"]), relative_path(alias["literal"])
        require(target in by_target and (literal not in by_target or by_target[literal] == by_target[target]), "view", "alias must join an admitted original target")
        aliases[literal] = by_target[target]
        material_by_target[literal] = material_by_target[target]
    by_target.update(aliases)
    for target in sorted(by_target):
        links.append({"native_relative_path": target, "mounted_path": "/data/"+target, "material_path": material_by_target[target], "input_pin": by_target[target]})
    require(not ({f["relative_path"] for f in job["native_files"]} & {x["native_relative_path"] for x in links}), "view", "new native outputs cannot shadow preexisting inputs")
    require(type(dependencies) is dict and set(dependencies) == set(job["dependencies"]), "dependency", "exact source-derived prior job outputs required")
    by_job = {j["id"]: j for j in program["jobs"]}
    for dep_id, dependency in dependencies.items():
        fields(dependency, ("schema", "job_id", "variant", "source_pin", "context", "request_pin", "capture_index_pin", "observer_evidence", "native_files"), "native dependency")
        require(dependency["schema"] == "n079_native_dependency_v1" and dependency["job_id"] == dep_id and dependency["variant"] == job["variant"] and dependency["source_pin"] == by_job[dep_id]["source"]["pin"], "dependency", "source/job/variant dependency join failed")
        for key in ("request_pin", "capture_index_pin", "observer_evidence"): checked_pin(dependency[key])
        expected_files = {f["id"]: f for f in by_job[dep_id]["native_files"]}
        require(set(dependency["native_files"]) == set(expected_files), "dependency", "complete original output inventory required")
        for file_id in job["dependency_files"][dep_id]:
            member = dependency["native_files"][file_id]
            fields(member, ("native_relative_path", "descriptor"), "native dependency output")
            target = member["native_relative_path"];descriptor = member["descriptor"]
            require(target == expected_files[file_id]["relative_path"] and target in by_target and by_target[target] == {k: descriptor.get(k) for k in ("bytes", "sha256")} and material_by_target[target] == descriptor.get("path"), "dependency", "captured output-to-next-job immutable material join failed")
    authors = view["author_code"]
    require(type(authors) is list and any(a.get("author_relative_path") == job["source"]["author_relative_path"] and {k: a.get(k) for k in ("bytes", "sha256")} == job["source"]["pin"] for a in authors), "source_join", "exact selected original/corrected script must be mounted under /source/author")
    if "literal_original" in job["source"]:
        original = job["source"]["literal_original"]
        require(any(a.get("author_relative_path") == original["author_relative_path"] and {k: a.get(k) for k in ("bytes", "sha256")} == original["pin"] for a in authors), "source_join", "corrected source requires literal original bytes alongside it")
    checked_pin(view_evidence);checked_pin(program_evidence)
    require(type(worker_sources) is dict and {"/source/native_worker.py", "/source/native_adapter.py"} <= set(worker_sources), "worker_source", "fixed worker and compiler source dependencies required")
    sources = {}
    for name, item in worker_sources.items():
        require(type(name) is str and name.startswith("/source/") and ".." not in PurePosixPath(name).parts, "worker_source", "only source-owned fixed worker paths allowed")
        fields(item, ("body_base64", "pin"), "worker source");checked_pin(item["pin"])
        require(type(item["body_base64"]) is str and len(item["body_base64"]) <= 4*((item["pin"]["bytes"]+2)//3), "extent", "source base64 extent must be bounded before decode")
        try: raw = base64.b64decode(item["body_base64"], validate=True)
        except ValueError as exc: raise NativeError("worker_source", "invalid base64 source") from exc
        require(pin(raw) == item["pin"], "source_join", "worker source body pin mismatch")
        sources[name] = dict(item)
    payload = {"schema": "n079_native_worker_request_v1", "context": context, "work_id": work_id, "job": job,
               "program_pin": pin(canonical(program)), "execution": execution, "input_links": links,
               "dependencies": dependencies,
               "view_evidence": view_evidence, "program_evidence": program_evidence,
               "transductive_disclosure": program["transductive_disclosure"]}
    raw = canonical(payload);require(len(raw) <= execution["caps"]["request_bytes"], "extent", "native request exceeds admitted cap")
    sources["/request/request.json"] = {"body_base64": base64.b64encode(raw).decode("ascii"), "pin": pin(raw)}
    return {"schema": "n079_actual_job_v1", "context": context, "work_id": work_id, "role": "native",
            "sources": sources, "view": view, "binding": binding, "argv": selected_role_command,
            "request_pin": pin(raw), "view_evidence": view_evidence, "program_evidence": program_evidence}


def resolve_dimensions(namespace, job):
    out = {}
    for key, rule in job["dimensions"].items():
        value = select_value(namespace, rule["selector"])
        # NumPy integer scalars support __index__; float counts are forbidden.
        import operator
        try: result = operator.index(value)
        except TypeError as exc: raise NativeError("support", "source dimension must be an integer") from exc
        require(type(value) is not bool and rule["minimum"] <= result <= rule["maximum"], "support", "source-produced dimension outside complete allowed bounds")
        out[key] = result
    if job["kind"] == "language_features":
        require(out["language_p"] <= out["embedding_dim"], "support", "PCA count exceeds native embedding dimension")
    # A language_fit job obtains only the already-selected feature count from
    # reg_param.n_features_in_. Its independently captured predecessor owns
    # embedding_dim/PCA support; do not read an absent extraction-only field.
    return out


def expected_shape(quantity, dimensions):
    return None if quantity["shape"] is None else [dimensions[x] if type(x) is str else x for x in quantity["shape"]]


def admitted_json(value, depth=0):
    require(depth <= 8, "extent", "native JSON capture nesting cap")
    if value is None or type(value) in (str, bool, int): return value
    if type(value) is float:
        require(math.isfinite(value), "nonfinite_metadata", "nonfinite native scalar JSON metadata")
        return value
    if type(value) in (list, tuple): return [admitted_json(v, depth+1) for v in value]
    if type(value) is dict:
        require(all(type(k) is str for k in value), "metadata", "string metadata keys required")
        return {k: admitted_json(v, depth+1) for k, v in value.items()}
    raise NativeError("metadata", "native JSON selector returned an unsupported object; no conversion callback")
