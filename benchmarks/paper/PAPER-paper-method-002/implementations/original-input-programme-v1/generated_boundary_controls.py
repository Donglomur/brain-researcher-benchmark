"""Portable generated consumer boundary entry; genuine 20-control suite.

The camera metadata version-gate substitute inside the unchanged run
is disclosed; it does not qualify historical pandas pickle handling.
Use --artifacts with an entirely absent directory.
"""

def run(consumer, binding, camera):
    import numpy as np
    import pandas as pd

    checks = []

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def refuses(call, name):
        try:
            call()
        except ValueError:
            checks.append(name)
            return
        raise AssertionError("did not refuse:" + name)

    # Generated complete site/ROI shape, with multiple ROIs in the first85 sites.
    fields = [field for field in range(1, 16) for _ in range(10 if field <= 12 else 9)]
    values = np.arange(1024, dtype=np.float64)[None, :] / 4096.0 + np.arange(147, dtype=np.float64)[:, None] / 256.0
    groups, assoc, local_roi = [], [], {}
    for ordinal, field in enumerate(fields):
        members = []
        for _ in range(2 if ordinal < 85 else 1):
            joined = len(assoc)
            local_roi[field] = local_roi.get(field, 0) + 1
            roi = local_roi[field]
            assoc.append({"joined_recording_row": joined, "recording_meta_row": joined,
                "label_frame_row": joined, "unique_id": field * 100 + roi,
                "rec_id": field, "roi_id": roi, "rec_id_ca": field, "roi_id_ca": roi})
            members.append(joined)
        groups.append({"average_row": ordinal, "rec_id": field, "branch_ind": ordinal,
            "comp_discrete": 0.0, "joined_recording_rows": members, "continuous_comp_mean": 0.125})
    average = pd.DataFrame({"branch_ind": np.arange(147, dtype=np.int64),
        "comp_discrete": np.zeros(147, dtype=np.float64), "rec_id": np.asarray(fields, dtype=np.int64),
        "comp": np.full(147, 0.125), "ca": values.tolist()},
        index=np.concatenate([np.arange(10 if field <= 12 else 9) for field in range(1, 16)]))
    association = pd.DataFrame(assoc)

    # New camera extraction boundary only: generated metadata runs under host
    # packages with an explicit test-only version-gate substitute. This is not
    # native-runtime or original-pickle qualification.
    class GeneratedMetadataContext:
        require = staticmethod(consumer.require)

        @staticmethod
        def reference_versions():
            pass

    roi_rows, scan_rows = [], []
    for field in range(15, 0, -1):
        x, y = 10.0 + 3 * field, 100.0 + 2 * field
        center = np.asarray([float(field), -2.0 * field, 9.0])
        for dx, dy in ((-2.0, 1.0), (2.0, -1.0)):
            roi_rows.append({"expdate": "20161028_1", "recording_id": field,
                "roi_pos": np.asarray([x + dx, y + dy, 7.0]), "recording_center": center})
        scan_rows.append({"cell_id": "20161028_1", "rec_id": field, "position": np.asarray([1.0, 2.0, 3.0])})
    roi_rows.insert(0, {"expdate": "other_cell", "recording_id": 1,
        "roi_pos": np.asarray([9999.0, -9999.0, 0.0]), "recording_center": np.asarray([999.0, 999.0, 0.0])})
    camera_roi, camera_scans = pd.DataFrame(roi_rows), pd.DataFrame(scan_rows)
    camera_stacks = pd.DataFrame({"cell_id": ["other_cell", "20161028_1", "20161028_1"],
                                  "pixel_size": [np.asarray([999.0]), np.asarray([2.0]), np.asarray([3.0])]})
    _, camera_result = camera.construct_target_camera_centers(GeneratedMetadataContext, camera_roi, camera_scans, camera_stacks)
    expected_centers = [[2.0 * field + 18.0, -4.0 * field + 148.0] for field in range(1, 16)]
    check(camera_result["centers"] == expected_centers and camera_result["field_order"] == list(range(1, 16)), "camera preserves target identity axes source mean and ascending field order")
    refuses(lambda: camera.construct_target_camera_centers(GeneratedMetadataContext, camera_roi,
        camera_scans[camera_scans.rec_id != 7], camera_stacks), "camera refuses missing source scan field")

    arrays, manifest = consumer.numeric_crossing(average, groups)
    restored = consumer.restore_numeric_crossing(arrays, manifest)
    check(restored.index.equals(average.index), "crossing preserves repeated source row index")
    check(list(restored.columns) == list(average.columns), "crossing preserves column order")
    check(np.stack(restored.ca).tobytes() == values.tobytes(), "crossing preserves exact binary64 labels")
    check([str(d) for d in restored.dtypes] == [str(d) for d in average.dtypes], "crossing preserves numeric column dtypes")
    ca_key = next(d["key"] for d in manifest["columns"] if d["name"] == "ca")
    changed = dict(arrays)
    changed[ca_key] = arrays[ca_key].copy()
    changed[ca_key][0, 0] = np.nextafter(changed[ca_key][0, 0], 1.0)
    refuses(lambda: consumer.restore_numeric_crossing(changed, manifest), "crossing rejects one-bit-value corruption")
    changed = dict(arrays)
    changed[ca_key] = arrays[ca_key].astype(np.float32)
    refuses(lambda: consumer.restore_numeric_crossing(changed, manifest), "crossing rejects dtype narrowing")
    changed = dict(arrays)
    changed[ca_key] = arrays[ca_key][::-1].copy()
    refuses(lambda: consumer.restore_numeric_crossing(changed, manifest), "crossing rejects site-order permutation")
    changed = dict(arrays)
    changed[ca_key] = arrays[ca_key].copy()
    changed[ca_key][0, 0] = np.nan
    refuses(lambda: consumer.restore_numeric_crossing(changed, manifest), "crossing rejects nonfinite values")

    # Direct literal global-RNG source fragment is an independent split oracle.
    saved = np.random.get_state()
    np.random.seed(0)
    permutation = np.random.permutation(np.arange(15360))
    np.random.set_state(saved)
    splits = binding.source_split()
    check(splits == {"test": permutation[:128].tolist(), "train": permutation[128:12313].tolist(),
                     "val": permutation[12313:].tolist()}, "private RNG equals literal source-default split")
    check([len(splits[k]) for k in ("train", "val", "test")] == [12185, 3047, 128], "source split counts and complete support")

    noise = np.zeros((15360, 15, 20), dtype=np.uint8)
    stimuli = pd.DataFrame({"activity": [(np.arange(15360, dtype=np.float64) / 32768).tolist()] * 2,
                            "num_synapses_of_bc": [2, 4]})
    private = binding.bind_model_arrays(noise, stimuli, restored, groups, association)
    check(int(private["mask"].sum()) == 147 * 1024, "mask counts observed targets only")
    check(np.array_equal(private["currents"][:, 0], 0.1 * np.asarray(stimuli.activity.iloc[0]) / 2), "current columns and source synapse scaling")
    wrong_order = restored.iloc[::-1]
    refuses(lambda: binding.bind_model_arrays(noise, stimuli, wrong_order, groups, association), "binding rejects reordered average sites")
    candidate = binding.candidate_view(private, "paper+data")
    check("targets" in candidate["splits"]["train"], "candidate receives source training targets")
    check(all(set(candidate["splits"][part]) == {"row_ids", "images", "currents", "mask"} for part in ("val", "test")), "candidate raw val/test targets excluded")
    check(candidate["identity_sha256"] == private["identity_sha256"], "candidate and evaluator share frozen identities")
    train_row = int(candidate["splits"]["train"]["row_ids"][0])
    original = private["labels"][train_row, 0]
    candidate["splits"]["train"]["targets"][0, 0] = 12345.0
    check(private["labels"][train_row, 0] == original, "released arrays cannot mutate evaluator target storage")
    packet = binding.operator_packet(private)
    for packet_row, source_row in enumerate(splits["test"]):
        for site, field in enumerate(fields):
            observed = source_row // 1024 + 1 == field
            check(packet["mask"][packet_row][site] == int(observed), "operator field support" if packet_row == 0 and site == 0 else "mask-cell")
            if not observed and packet["labels"][packet_row][site] is not None:
                raise AssertionError("unobserved fill leaked as observed target")
    # Store a compact check count rather than thousands of repeated mask checks.
    checks = [name for name in checks if name != "mask-cell"]
    return {"schema": "jaxley-consumer-generated-boundary-controls-v1", "status": "PASS",
            "checks": checks, "mask_cells_checked": 128 * 147,
            "runtime": {"numpy": np.__version__, "pandas": pd.__version__},
            "native_pickle_decode": False, "native_reference_grouping": False,
            "camera_version_gate_substituted_for_generated_metadata_only": True,
            "original_model_readiness": False, "fixtures_persisted": False}


HELPER_PIN = (14104, 'd44de0d61c9b8c5f1f33226fcedfec40dc66873f669ad44e8c28eb07e930b59e')
SOURCE_PINS = {'portable_consumer.py': (15008, 'e72e33d0a97648d8023e656695e0a3ce54b0e0140df2382e340e0f2534bc7c12'), 'input_binding.py': (10007, 'f4bd10b4c40cef74835001937ce3dc5cb4bd16fcc061b4138696b39827a707d9'), 'camera_centers.py': (3458, 'd6706e2ea864c9898df5491094add2852f13f544e555c4b62c6e7924f4f2d5c9'), 'bc_producer.py': (12222, '2a0890f8cfd44d54592cde0935627d2ab4c096ba0c03a7401dbfa6f4a3d9580a'), 'author_kernels.py': (7692, '46af417cfe92b2ffbd8fa5618c97ba5f9d6ddee93452d50aa8df7dc6e4a01517'), 'input_composition.py': (10440, 'f8c2296b5434ace7478fd762f7709700c867ad528818c85055a42f1655457d75'), 'generated_producer_controls.py': (5887, '37bddb6bfa43e13aec782582f0a4b78a083aa5e838331333959466e463715cb9')}
PUBLIC_NAMES = ['README.md', 'SOURCE.json', 'author_kernels.py', 'bc_producer.py', 'camera_centers.py', 'generated_boundary_controls.py', 'generated_producer_controls.py', 'input_binding.py', 'input_composition.py', 'portable_consumer.py', 'reporting_transport.py', 'run_generated_controls.py']
EXPECTED_IDS = ['camera preserves target identity axes source mean and ascending field order', 'camera refuses missing source scan field', 'crossing preserves repeated source row index', 'crossing preserves column order', 'crossing preserves exact binary64 labels', 'crossing preserves numeric column dtypes', 'crossing rejects one-bit-value corruption', 'crossing rejects dtype narrowing', 'crossing rejects site-order permutation', 'crossing rejects nonfinite values', 'private RNG equals literal source-default split', 'source split counts and complete support', 'mask counts observed targets only', 'current columns and source synapse scaling', 'binding rejects reordered average sites', 'candidate receives source training targets', 'candidate raw val/test targets excluded', 'candidate and evaluator share frozen identities', 'released arrays cannot mutate evaluator target storage', 'operator field support']


def _reporter():
    # Authenticate the one adjacent stdlib helper before executing its bytes.
    import hashlib
    import os
    import stat
    import types
    root = os.path.dirname(os.path.abspath(__file__))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open('/', flags)
    fd = None
    try:
        for part in root.split('/')[1:]:
            if part in ('', '.', '..'):
                raise ValueError('noncanonical source root')
            child = os.open(part, flags, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open('reporting_transport.py', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != HELPER_PIN[0]:
            raise ValueError('helper mode/link/extent')
        chunks, total = [], 0
        while total <= HELPER_PIN[0]:
            part = os.read(fd, min(8192, HELPER_PIN[0] + 1 - total))
            if not part:
                break
            chunks.append(part)
            total += len(part)
        body = b''.join(chunks)
        identity = lambda value: (value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        if identity(before) != identity(os.fstat(fd)) or len(body) != HELPER_PIN[0] or hashlib.sha256(body).hexdigest() != HELPER_PIN[1]:
            raise ValueError('helper byte identity')
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)
    module = types.ModuleType('_jaxley_input_reporting_transport')
    module.__file__ = os.path.join(root, 'reporting_transport.py')
    exec(compile(body, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    return module, root


def _authenticated_sources(reporting, root):
    import os
    directory = reporting._directory(root)
    try:
        reporting.require(sorted(os.listdir(directory)) == PUBLIC_NAMES, 'exact owned source namespace')
    finally:
        os.close(directory)
    # All seven unchanged source/control modules are authenticated before any
    # scientific import; execution consumes these held bytes, never a reopen.
    return {name: reporting.read_source(root, name, size, digest)
            for name, (size, digest) in SOURCE_PINS.items()}


def main(argv=None):
    import argparse
    import os
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--artifacts', help='one entirely absent artifact directory')
    mode.add_argument('--worker-report-fd', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    reporting, root = _reporter()
    if args.worker_report_fd is not None:
        # Internal transport endpoint always invokes this suite's real function.
        # It accepts no replacement source, command, roster or fixture selector.
        return _worker(reporting, root, args.worker_report_fd)
    command = [sys.executable, '-I', '-B', os.path.join(root, os.path.basename(__file__))]
    return reporting.transport(command, args.artifacts, EXPECTED_IDS)


def _worker(reporting, root, report_fd):
    import os
    import types
    entry = {'scientific_call_started': False, 'source_pins': {},
             'resource_authority': False, 'original_inputs': False, 'model_fits': False}
    try:
        bodies = _authenticated_sources(reporting, root)
        modules = []
        for name in ('portable_consumer.py', 'input_binding.py', 'camera_centers.py'):
            module = types.ModuleType('_jaxley_input_' + name[:-3])
            module.__file__ = os.path.join(root, name)
            exec(compile(bodies[name], module.__file__, 'exec', dont_inherit=True), module.__dict__)
            modules.append(module)
        entry['source_pins'] = {name: {'bytes': size, 'sha256': digest} for name, (size, digest) in SOURCE_PINS.items()}
        entry['scientific_call_started'] = True
        raw = run(*modules)
        reporting.require(type(raw) is dict and raw.get('schema') == 'jaxley-consumer-generated-boundary-controls-v1'
                          and raw.get('status') == 'PASS' and raw.get('checks') == EXPECTED_IDS,
                          'complete unchanged consumer result required')
        reporting.require(raw.get('mask_cells_checked') == 18816
                          and raw.get('camera_version_gate_substituted_for_generated_metadata_only') is True
                          and raw.get('original_model_readiness') is False,
                          'consumer scientific scope changed')
        result = {'status': 'PASS', 'controls': raw['checks'], 'scientific_result': raw, 'entry': entry}
        reporting._encode(result, reporting.MAX_RESULT_BYTES)
        code = 0
    except Exception as exc:
        result = {'status': 'FAIL', 'controls': [], 'error': reporting.bounded_error(exc), 'entry': entry,
                  **reporting.trace_observations(exc, run)}
        code = 1
    reporting.write_worker_report(report_fd, result)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
