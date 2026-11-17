"""Full feature materialization and case-visible staging with no query EEG.

Byte descriptors and flat output trees record custody, not authority. Native
array allocation/CPU/isolation qualification remains an operator obligation;
all explicit array allocations are reserved through the existing Owner first.
"""
from __future__ import annotations

from .splits import PERSONS, VIDEO_IDS, assignment_document, validate_outer_case
from .features import BLOCK_DIMS, NODES, NODE_SHAPES, VERSIONS

MANIFEST_LIMIT = 256 * 1024 * 1024
POOL_MANIFEST_LIMIT = 16 * 1024 * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _document(root, descriptor, owner, limit):
    from input_owner import capture
    from io_contract import decode
    from .artifacts import descriptor as checked_descriptor
    checked_descriptor(descriptor, limit)
    return decode(capture(root, descriptor, owner, max_bytes=limit))


def _array(root, descriptor, shape, owner):
    """Authenticate complete bytes; literal-only header validation precedes NumPy."""
    from input_owner import capture
    from .artifacts import array_limit, decode_array, descriptor as checked_descriptor
    maximum = array_limit(shape)
    checked_descriptor(descriptor, maximum)
    body = capture(root, descriptor, owner, max_bytes=maximum)
    return decode_array(body, shape, owner)


def materialize_features(feature_root, feature_descriptor, unscaled_pool_root,
                         pool_descriptor, owner):
    """Return shared and all-person raw eye/timing operands for capture_feature_pool.

    Every one of 1102 complete shared rows and all six persons' eye/timing bodies
    is captured. The private pool's EEG descriptors are never dereferenced here.
    The full source feature manifest may be large because it retains all native
    clock observations; its explicit cap and Owner budget both apply.
    """
    record = owner.begin("materialize_complete_generalization_feature_pool")
    answer = None
    try:
        document = _document(feature_root, feature_descriptor, owner, MANIFEST_LIMIT)
        need(type(document) is dict and document.get("schema") == "neural080_full_generalization_features_v1",
             "complete actual full-feature producer manifest")
        need(document.get("blocks") == BLOCK_DIMS and document.get("s3d_nodes") == list(NODES) and
             document.get("s3d_shapes") == [list(s) for s in NODE_SHAPES] and
             document.get("runtime_versions") == VERSIONS,
             "exact selected full producer dimensions, node order and versions")
        need(type(document.get("s3d_forward_calls")) is int and
             document["s3d_forward_calls"] == 1102 * 16 and document.get("silence_count") == 34,
             "all chronological/reverse/matched-static producer work and silence support")
        videos = document.get("videos")
        need(type(videos) is list and len(videos) == 1102 and
             all(type(r) is dict and type(r.get("video_id")) is int for r in videos) and
             tuple(r["video_id"] for r in videos) == VIDEO_IDS,
             "all1102 ordered feature identities exactly once")
        for row in videos:
            need(type(row.get("arrays")) is dict and set(row["arrays"]) == set(BLOCK_DIMS),
                 "complete per-video feature block roster")
            need(type(row.get("provenance")) is dict and
                 row["provenance"].get("video_id") == row["video_id"] and
                 row["provenance"].get("audio_status") in ("presented_audio", "presented_silent_no_track"),
                 "actual per-video producer provenance")
            for name in BLOCK_DIMS:
                need(row["arrays"][name].get("path") == "video-%04d-%s.npy" % (row["video_id"],name),
                     "canonical complete source feature body role")
        pool = _document(unscaled_pool_root, pool_descriptor, owner, POOL_MANIFEST_LIMIT)
        need(type(pool) is dict and pool.get("schema") == "neural080_unscaled_recording_pool_v1" and
             pool.get("persons") == list(PERSONS) and pool.get("video_ids") == list(VIDEO_IDS) and
             pool.get("projected_joined_trials") == 45144,
             "complete original unnormalized source pool")
        persons = pool.get("subjects")
        need(type(persons) is list and len(persons) == 6 and
             all(type(row) is dict for row in persons) and
             tuple(row.get("subject") for row in persons) == PERSONS,
             "all six actual source persons once in canonical order")
        basis = pool.get("basis")
        need(type(basis) is dict and basis.get("eye_shape_per_video") == [150,8] and
             basis.get("analysis_native_sample_slice") == [50,1550] and
             basis.get("eeg_normalization") == "none; no fitted target mean or scale is applied here",
             "exact original raw ocular/time basis and unscaled pool")
        import numpy as np
        need(np.__version__ == "2.2.6", "selected primitive array runtime")
        shared = {}
        # Preserve source dtypes while materializing. capture_feature_pool makes
        # its separately reserved immutable float64 snapshots afterward.
        for name,width in BLOCK_DIMS.items():
            dtype = np.float32 if name in ("learned_video","learned_video_reversed") else np.float64
            itemsize = 4 if dtype is np.float32 else 8
            owner.reserve("retained_bytes", 1102 * width * itemsize)
            matrix = np.empty((1102,width), dtype=dtype)
            for index,row in enumerate(videos):
                value = _array(feature_root, row["arrays"][name], (width,), owner)
                need(value.dtype.itemsize == itemsize, "exact source feature representation: "+name)
                matrix[index] = value
            matrix.flags.writeable = False
            shared[name] = matrix
        silence = shared["silence"][:,0]
        owner.reserve("retained_bytes", 1102*4)
        need(np.all((silence == 0) | (silence == 1)) and int(silence.sum()) == 34,
             "complete actual34 silence-status values")
        for index,row in enumerate(videos):
            silent = row["provenance"]["audio_status"] == "presented_silent_no_track"
            need(silence[index] == float(silent), "silence feature joins exact source observation")
            if silent:
                owner.reserve("retained_bytes", BLOCK_DIMS["acoustic"])
                need(np.all(shared["acoustic"][index] == 0), "confirmed no-playback acoustic features are exact zeros")
        personal = {}
        for row in persons:
            pid = row["subject"]
            arrays = row.get("arrays")
            need(type(arrays) is dict and set(arrays) == {"eeg_unscaled","eye","timing","repeat_counts"},
                 "complete source pool array roles; only eye/timing bodies are visible here")
            need(arrays["eye"].get("path") == pid+"-eye.npy" and
                 arrays["timing"].get("path") == pid+"-timing.npy", "exact personal source body roles")
            personal[pid] = {"eye": _array(unscaled_pool_root,arrays["eye"],(1102,150,8),owner),
                             "timing": _array(unscaled_pool_root,arrays["timing"],(1102,26),owner)}
        answer = shared, personal
    except BaseException as exc:
        owner.failure(record,exc)
    owner.complete(record)
    return answer


def _logical_limits(value):
    need(type(value) is dict and set(value) == {"read_bytes","write_bytes","retained_bytes","attempts"} and
         all(type(v) is int and 0 < v < 2**63 for v in value.values()),
         "explicit complete case worker logical limits")
    return dict(value)


def stage_case(plan, case, feature_pool, training_targets, owner, out, logical_limits):
    """Write the actual flat case view, then return its complete descriptor roster.

    Shared stimulus blocks include all1102 identities as selected; personal
    covariates include only exact outer TRAIN + QUERY coordinates. The target
    operand is restricted to raw TRAIN EEG. Source recordings, other-person
    ocular coordinates and query EEG are not inputs to this writer.
    """
    record = owner.begin("stage_generalization_case:"+case.case_id)
    answer = None
    try:
        from input_owner import Writer
        from .models import (check_feature_pool, TrainingTargets, array_identity,
                             reserve_array, SHARED, TARGET_SHAPE)
        import numpy as np
        validate_outer_case(plan,case)
        limits = _logical_limits(logical_limits)
        check_feature_pool(feature_pool)
        train = tuple(case.training_coordinates())
        query = tuple(case.query_coordinates())
        coordinates = train + query
        need(type(training_targets) is TrainingTargets and training_targets.coordinates == train and
             training_targets.values.shape == (len(train),*TARGET_SHAPE) and
             not training_targets.values.flags.writeable and
             array_identity(training_targets.values) == training_targets.identity,
             "exact immutable raw TRAIN target support only")
        need(set(feature_pool.shared) == set(BLOCK_DIMS) == set(SHARED), "all selected shared feature blocks")
        for name,width in BLOCK_DIMS.items():
            need(feature_pool.shared[name].shape == (1102,width), "complete shared matrix width: "+name)
        reserve_array(owner,(len(coordinates),150,8))
        reserve_array(owner,(len(coordinates),26))
        eye = np.empty((len(coordinates),150,8),dtype=np.float64)
        timing = np.empty((len(coordinates),26),dtype=np.float64)
        for index,(person,video) in enumerate(coordinates):
            personal = feature_pool.personal[person]
            need(video in personal["index"], "selected case covariate coordinate exists")
            at = personal["index"][video]
            eye[index] = personal["raw_eye"][at]
            timing[index] = personal["timing"][at]
        writer = Writer(out,owner)
        shared = {name: writer.array("shared-"+name+".npy",feature_pool.shared[name]) for name in SHARED}
        personal = {"eye":writer.array("personal-eye.npy",eye),
                    "timing":writer.array("personal-timing.npy",timing)}
        target = writer.array("training-targets.npy",training_targets.values)
        document = {"schema":"neural080_generalization_case_input_v1",
                    "backend":"full_svd_materialized",
                    "assignment":assignment_document(plan),"assignment_sha256":plan.assignment_sha256,
                    "case_id":case.case_id,"units":"original_eeg",
                    "video_ids":list(VIDEO_IDS),"blocks":dict(BLOCK_DIMS),
                    "training_coordinates":[list(c) for c in train],
                    "query_coordinates":[list(c) for c in query],
                    "personal_coordinates":[list(c) for c in coordinates],
                    "shared":shared,"personal":personal,"training_targets":target,
                    "logical_limits":limits,
                    "target_contract":"raw TRAIN EEG in original released numerical units; predictions must use the same units",
                    "access_scope":"all shared unlabeled stimuli; exact outerTRAIN+QUERY ocular/timing; outerTRAIN EEG only",
                    "authority":"none; actual isolated operator admission and resource enforcement remain required"}
        manifest = writer.document("CASE.json",document)
        answer = {"root":str(writer.root),"manifest":manifest,"document":document,
                  "files":tuple(dict(row) for row in writer.files)}
    except BaseException as exc:
        owner.failure(record,exc)
    owner.complete(record)
    return answer


def materialize_personal(unscaled_pool_root,pool_descriptor,owner):
    """Capture only six persons' raw eye/timing; never open an EEG array body."""
    record=owner.begin("materialize_only_original_personal_covariates")
    answer=None
    try:
        pool=_document(unscaled_pool_root,pool_descriptor,owner,POOL_MANIFEST_LIMIT)
        need(type(pool) is dict and pool.get("schema")=="neural080_unscaled_recording_pool_v1" and
             pool.get("persons")==list(PERSONS) and pool.get("video_ids")==list(VIDEO_IDS) and
             pool.get("projected_joined_trials")==45144,"complete actual original person pool")
        subjects=pool.get("subjects")
        need(type(subjects) is list and len(subjects)==6 and all(type(r) is dict for r in subjects) and
             tuple(r.get("subject") for r in subjects)==PERSONS,"all six original persons in exact order")
        basis=pool.get("basis")
        need(type(basis) is dict and basis.get("eye_shape_per_video")==[150,8] and
             basis.get("analysis_native_sample_slice")==[50,1550],"original common ocular clock and eight terms")
        result={}
        for row in subjects:
            person=row["subject"];arrays=row.get("arrays")
            need(type(arrays) is dict and set(arrays)=={"eeg_unscaled","eye","timing","repeat_counts"},
                 "exact pool roles; EEG body is outside this reader")
            need(arrays["eye"].get("path")==person+"-eye.npy" and
                 arrays["timing"].get("path")==person+"-timing.npy","exact personal source filenames")
            result[person]={"eye":_array(unscaled_pool_root,arrays["eye"],(1102,150,8),owner),
                            "timing":_array(unscaled_pool_root,arrays["timing"],(1102,26),owner)}
        answer=result
    except BaseException as exc:
        owner.failure(record,exc)
    owner.complete(record)
    return answer


def stage_stream_case(plan,case,stream_spec_document,personalraw,training_targets,owner,out,logical_limits):
    """Stage concrete streamed inputs and only exact TRAIN+QUERY covariates.

    The selected finite map/media/checkpoint/programme trees are mounted by the
    runner under the fixed guest roots. Flat map/evidence copies here retain
    their original bytes for custody; they are not rewritten into a different
    map or substituted for the pinned metadata tree's original relative paths.
    """
    record=owner.begin("stage_streamed_generalization_case:"+case.case_id)
    answer=None
    try:
        import json
        import numpy as np
        from input_owner import Writer,capture
        from io_contract import decode
        from .models import TrainingTargets,array_identity,reserve_array,TARGET_SHAPE
        from .feature_stream import parse_stream_spec
        validate_outer_case(plan,case)
        limits=_logical_limits(logical_limits)
        snapshot=json.loads(json.dumps(stream_spec_document,allow_nan=False))
        spec=parse_stream_spec(snapshot,owner)
        train=tuple(case.training_coordinates());query=tuple(case.query_coordinates())
        coordinates=train+query
        need(type(training_targets) is TrainingTargets and training_targets.coordinates==train and
             training_targets.values.shape==(len(train),*TARGET_SHAPE) and
             not training_targets.values.flags.writeable and
             array_identity(training_targets.values)==training_targets.identity,
             "exact immutable raw TRAIN-only target rows")
        need(type(personalraw) is dict and set(personalraw)==set(PERSONS),"all six operator-private raw covariate groups")
        for person in PERSONS:
            row=personalraw[person]
            need(type(row) is dict and set(row)=={"eye","timing"},"closed raw personal feature fields")
            for name,shape in (("eye",(1102,150,8)),("timing",(1102,26))):
                value=row[name]
                need(type(value) is np.ndarray and value.shape==shape and value.flags.c_contiguous and
                     not value.flags.writeable and value.dtype.kind=="f" and value.dtype.itemsize in (4,8),
                     "captured immutable primitive raw personal feature matrix")
        reserve_array(owner,(len(coordinates),150,8))
        reserve_array(owner,(len(coordinates),26))
        eye=np.empty((len(coordinates),150,8),dtype=np.float64)
        timing=np.empty((len(coordinates),26),dtype=np.float64)
        for index,(person,video) in enumerate(coordinates):
            eye[index]=personalraw[person]["eye"][video-1]
            timing[index]=personalraw[person]["timing"][video-1]
        writer=Writer(out,owner)
        personal={"eye":writer.array("personal-eye.npy",eye),"timing":writer.array("personal-timing.npy",timing)}
        target=writer.array("training-targets.npy",training_targets.values)
        original=spec.source_map_descriptor.row()
        raw=capture(spec.metadata_root,original,owner,max_bytes=16_777_216)
        selected=decode(raw)
        metadata=[{"role":"source_map","original":original,"captured":writer.put("source-map.json",raw)}]
        evidence=selected.get("evidence")
        need(type(evidence) is dict and set(evidence)=={"experimental_identity","audio_presence","provenance_graph"},
             "all three exact map evidence roles for finite metadata mount")
        from .artifacts import descriptor as checked_descriptor
        for role in sorted(evidence):
            original=checked_descriptor(evidence[role],16_777_216)
            body=capture(spec.metadata_root,original,owner,max_bytes=16_777_216)
            metadata.append({"role":role,"original":original,
                             "captured":writer.put("map-evidence-"+role+".json",body)})
        guest=dict(snapshot)
        guest.update(metadata_root="/tools/feature-metadata",media_root="/tools/media",
                     checkpoint_root="/tools/checkpoint",programme_root="/source")
        stream_input=writer.document("STREAM_INPUT.json",guest)
        document={"schema":"neural080_generalization_case_input_v1","backend":"streamed_dual_certified",
                  "assignment":assignment_document(plan),"assignment_sha256":plan.assignment_sha256,
                  "case_id":case.case_id,"units":"original_eeg","video_ids":list(VIDEO_IDS),
                  "blocks":dict(BLOCK_DIMS),"training_coordinates":[list(c) for c in train],
                  "query_coordinates":[list(c) for c in query],"personal_coordinates":[list(c) for c in coordinates],
                  "personal":personal,"training_targets":target,"stream_spec":stream_input,
                  "stream_metadata_captures":metadata,"logical_limits":limits,
                  "target_contract":"raw TRAIN EEG in original released numerical units; predictions must use the same units",
                  "access_scope":"all selected pinned raw media/checkpoint and ordinary feature tools; exact outerTRAIN+QUERY ocular/timing; outerTRAIN EEG only",
                  "mount_contract":{"metadata":"finite pinned original relative map/evidence tree at /tools/feature-metadata",
                                    "media":"finite pinned complete1102 source media tree at /tools/media",
                                    "checkpoint":"exact selected local checkpoint at /tools/checkpoint",
                                    "programme":"validated complete pinned readonly source bootstrap at /source"},
                  "authority":"none; actual runner enforces mounted finite trees, code bootstrap, resource limits and isolation"}
        manifest=writer.document("CASE.json",document)
        answer={"root":str(writer.root),"manifest":manifest,"document":document,
                "files":tuple(dict(row) for row in writer.files)}
    except BaseException as exc:
        owner.failure(record,exc)
    owner.complete(record)
    return answer
