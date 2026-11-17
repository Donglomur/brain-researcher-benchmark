"""Regenerate every fixed source feature, exposing only explicit column blocks.

This changes feature access/storage, not the feature recipe or readout policy.
Each request performs the full1102-video,16-forward-per-video producer work.
No callback, substitute encoder, fitted transform, eigensolver or reduced node
set can be supplied. Numerical imports occur only inside an actual request.

The caller must run from its independently validated complete source-tree pin
on a readonly runner. The selected tree digest below is a provenance operand,
not an authority token. Recapturing imported-module origin files detects an
observed file change; it does not prove which bytes a preloaded code object ran,
nor protect against ABA mutation. That requires the sealed source bootstrap.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

from input_owner import Owner, Writer, capture
from . import features, source_map
from .features import BLOCK_DIMS, FEATURE_DIM, FeatureLimits
from .source_map import SourceMap, VIDEO_IDS, descriptor, need


@dataclass(frozen=True)
class FilePin:
    path: str
    bytes: int
    sha256: str

    def row(self):
        return {"path":self.path,"bytes":self.bytes,"sha256":self.sha256}


@dataclass(frozen=True)
class ProgrammePin:
    module: str
    body: FilePin


@dataclass(frozen=True)
class StreamSpec:
    metadata_root: str
    source_map_descriptor: FilePin
    source_map: SourceMap
    media_root: str
    checkpoint_root: str
    checkpoint: FilePin
    programme_root: str
    programme_sources: tuple[ProgrammePin, ...]
    programme_tree_sha256: str
    column_width: int
    limits: FeatureLimits


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def _sha(value):
    need(type(value) is str and len(value)==64 and all(c in "0123456789abcdef" for c in value),
         "complete selected SHA256")


def programme_tree_digest(tree_members):
    """SHA256 of canonical JSON sorted complete runner member dictionaries.

    Each member is exactly {path,bytes,sha256,executable}. The host root is
    excluded so the same whole-tree identity joins its readonly guest mount.
    This is metadata hashing; actual complete census/body verification is the
    runner's obligation and is not replaced by a matching dictionary digest.
    """
    need(type(tree_members) in (list,tuple) and bool(tree_members),"complete programme tree member roster")
    rows=[]
    for member in tree_members:
        need(type(member) is dict and set(member)=={"path","bytes","sha256","executable"} and
             type(member["executable"]) is bool,"exact runner member metadata fields")
        need(type(member["bytes"]) is int and 0<=member["bytes"]<2**63,
             "finite ordinary tree member extent, including empty package files")
        descriptor({"path":member["path"],"bytes":max(1,member["bytes"]),
                    "sha256":member["sha256"]},cap=2**63-1)
        rows.append(dict(member))
    rows.sort(key=lambda row:row["path"])
    need(len({row["path"] for row in rows})==len(rows),"unique complete programme tree paths")
    return hashlib.sha256(_canonical(rows)).hexdigest()


def validate_programme_tree(spec,tree_members):
    """Join actual admitted runner roster to the spec and all seven origins.

    Campaign must pass its actual /source mount TreePin members (plain dicts);
    the worker repeats this join to its captured CONTEXT roster. The independent
    complete readonly-tree census/bootstrap remains necessary in both routes.
    """
    _validate(spec)
    need(programme_tree_digest(tree_members)==spec.programme_tree_sha256,
         "whole actual programme tree roster must match stream selection")
    members={row["path"]:row for row in tree_members}
    for pin in spec.programme_sources:
        need(pin.body.path in members and all(members[pin.body.path][key]==value
             for key,value in pin.body.row().items()),"every selected imported origin must join whole programme tree")
    return spec.programme_tree_sha256


def _modules():
    return tuple(sorted((__name__,features.__name__,source_map.__name__,
                         "input_owner","decode_media","stimulus_core","io_contract")))


def _validate(spec):
    need(type(spec) is StreamSpec and type(spec.source_map) is SourceMap,
         "actual immutable source-map stream selection")
    for name in ("metadata_root","media_root","checkpoint_root","programme_root"):
        root=getattr(spec,name)
        need(type(root) is str and Path(root).is_absolute() and str(Path(root))==root,
             "explicit absolute selected root: "+name)
    need(type(spec.column_width) is int and 0<spec.column_width<=FEATURE_DIM,
         "explicit positive caller-selected column width; no default")
    need(type(spec.limits) is FeatureLimits,"exact original full feature limits")
    spec.limits.validate()
    need(type(spec.source_map_descriptor) is FilePin and type(spec.checkpoint) is FilePin,
         "immutable map and local checkpoint body pins")
    descriptor(spec.source_map_descriptor.row(),cap=16_777_216)
    descriptor(spec.checkpoint.row(),cap=spec.limits.max_checkpoint_bytes)
    need(spec.checkpoint.sha256.startswith(features.KINETICS400_PREFIX),
         "full local checkpoint pin has official KINETICS400 source prefix")
    _sha(spec.programme_tree_sha256)
    need(tuple(r.video_id for r in spec.source_map.roles)==VIDEO_IDS,
         "all1102 actual source roles")
    _sha(spec.source_map.canonical_source_map_sha256)
    need(type(spec.programme_sources) is tuple and len(spec.programme_sources)==len(_modules()) and
         all(type(p) is ProgrammePin and type(p.body) is FilePin for p in spec.programme_sources) and
         tuple(p.module for p in spec.programme_sources)==_modules(),
         "complete fixed programme-origin roster in canonical module order")
    paths=[]
    for selected in spec.programme_sources:
        descriptor(selected.body.row(),cap=1_048_576)
        paths.append(selected.body.path)
    need(len(set(paths))==len(paths),"distinct exact selected programme source bodies")
    return hashlib.sha256(_canonical(asdict(spec))).hexdigest()


def parse_stream_spec(document,owner):
    """Construct typed selection from captured ordinary metadata and actual map.

    The caller captures the enclosing STREAM_INPUT body. This parser captures
    the selected map/evidence using their own descriptors; it does not import a
    numerical package, read media/checkpoint bodies, or assert source authority.
    """
    record=owner.begin("parse_actual_feature_stream_selection")
    answer=None
    try:
        keys={"schema","metadata_root","source_map_descriptor","media_root","checkpoint_root",
              "checkpoint","programme_root","programme_sources","programme_tree_sha256","column_width","limits"}
        need(type(document) is dict and set(document)==keys and
             document["schema"]=="neural080_feature_stream_input_v1","closed actual stream selection")
        def pin(row):
            need(type(row) is dict and set(row)=={"path","bytes","sha256"},"exact source FilePin fields")
            return FilePin(**row)
        sources=document["programme_sources"]
        need(type(sources) is list and all(type(p) is dict and set(p)=={"module","body"} for p in sources),
             "complete typed selected programme source roster")
        limits=document["limits"]
        need(type(limits) is dict and set(limits)==set(FeatureLimits.__dataclass_fields__),
             "all six explicit original feature capacities")
        selected_map=source_map.load_source_map(document["metadata_root"],document["source_map_descriptor"],VIDEO_IDS,owner)
        answer=StreamSpec(document["metadata_root"],pin(document["source_map_descriptor"]),selected_map,
                          document["media_root"],document["checkpoint_root"],pin(document["checkpoint"]),
                          document["programme_root"],tuple(ProgrammePin(p["module"],pin(p["body"])) for p in sources),
                          document["programme_tree_sha256"],document["column_width"],FeatureLimits(**limits))
        _validate(answer)
    except BaseException as exc:
        owner.failure(record,exc)
    owner.complete(record)
    return answer


def _programme(spec,owner):
    """Recapture actual selected files and join their known imported origins.

    This complements, and cannot replace, the caller's readonly verified source
    bootstrap. No statement about preloaded code-object identity is emitted.
    """
    result=[]
    for selected in spec.programme_sources:
        body=capture(spec.programme_root,selected.body.row(),owner,max_bytes=1_048_576)
        module=importlib.import_module(selected.module)
        origin=getattr(module,"__file__",None)
        need(type(origin) is str and Path(origin).is_absolute() and
             Path(origin)==Path(spec.programme_root)/selected.body.path,
             "imported module origin must be the exact selected programme path")
        result.append({"module":selected.module,"origin":origin,"body":selected.body.row(),
                       "observed_bytes":len(body)})
    return result


def _identity(array,owner,np):
    need(type(array) is np.ndarray and array.flags.c_contiguous and
         array.dtype.kind=="f" and array.dtype.itemsize in (4,8),
         "complete contiguous source feature representation")
    owner.reserve("retained_bytes",int(array.size))
    need(np.isfinite(array).all(),"all full feature-row values finite")
    metadata={"dtype":array.dtype.str,"shape":list(array.shape),"order":"C"}
    digest=hashlib.sha256(_canonical(metadata)+b"\n")
    digest.update(memoryview(array).cast("B"))
    return {**metadata,"value_bytes":int(array.nbytes),"value_sha256":digest.hexdigest()}


def _blocks(decoded,role,encoder,runtime,owner,limits):
    """Same ordered operations/dtypes as features.produce, without full disk output."""
    np=runtime[0];frames=decoded["frames"]
    learned=encoder.vector(frames)
    reversed_values=encoder.vector(list(reversed(frames)))
    features.reserve(owner,limits,FEATURE_DIM*8,"stream complete matched-static accumulator",vector=True)
    static=np.zeros(FEATURE_DIM,dtype=np.float64)
    for frame in frames:
        static+=encoder.vector([frame]*14)
    static/=14
    silent=role.audio_status=="presented_silent_no_track"
    features.reserve(owner,limits,BLOCK_DIMS["acoustic"]*8,"stream complete acoustic output")
    acoustic=(np.zeros(BLOCK_DIMS["acoustic"],dtype=np.float64) if silent else
              features.acoustic_features(decoded["audio"],decoded["audio_rate"],
                                         decoded["audio_start"],np,owner,limits))
    return {"matched_static":static,"motion":decoded["motion"],"acoustic":acoustic,
            "learned_video":learned,"learned_video_reversed":reversed_values,
            "silence":np.asarray([float(silent)],dtype=np.float64)}


class ActualFeatureStream:
    """Metadata-only construction; a request performs the actual complete work.

    Owner and Writer are concrete existing source classes. They are not issuer
    callbacks. A failed request leaves no usable returned array and cannot set
    or replace the baseline. Partially written ledger files remain failures.
    """
    def __init__(self,spec,ledger_writer):
        self.spec=spec
        self.spec_sha256=_validate(spec)
        need(type(ledger_writer) is Writer and type(ledger_writer.owner) is Owner,
             "actual append-only source Writer and original Owner required")
        self.writer=ledger_writer
        self._baseline=None
        self._baseline_pass=None
        self._last_pass=None
        self._next=0
        self._active=False

    @property
    def widths(self):
        return dict(BLOCK_DIMS)

    @property
    def completed_baseline(self):
        return None if self._baseline_pass is None else dict(self._baseline_pass)

    @property
    def last_completed_pass(self):
        return None if self._last_pass is None else dict(self._last_pass)

    def check_selection(self):
        need(_validate(self.spec)==self.spec_sha256,"unchanged complete stream selection")
        return self.spec_sha256

    def columns(self,block,start,stop,owner):
        """Regenerate every full feature row; return only one explicit range.

        The matrix has all1102 rows, in canonical video order, and exactly the
        producer's source dtype. Downstream fit/normalization uses its separately
        selected numeric policy. No learned transform is fitted by this method.
        """
        record=owner.begin("regenerate_full_features_columns")
        answer=None;entered=False
        wall=time.monotonic();cpu=time.process_time();before=dict(owner.used)
        try:
            need(type(owner) is Owner and owner is self.writer.owner,"one original Owner for stream effects and ledger")
            need(not self._active,"one actual feature regeneration request at a time")
            self._active=True;entered=True
            index=self._next;self._next+=1
            need(_validate(self.spec)==self.spec_sha256,"immutable exact source stream selection")
            need(type(block) is str and block in BLOCK_DIMS and type(start) is int and type(stop) is int and
                 0<=start<stop<=BLOCK_DIMS[block] and stop-start<=self.spec.column_width,
                 "explicit contiguous requested columns within selected block and caller width")
            imported_origins=_programme(self.spec,owner)
            observed_map=source_map.load_source_map(self.spec.metadata_root,
                self.spec.source_map_descriptor.row(),VIDEO_IDS,owner)
            need(observed_map==self.spec.source_map,"same actual captured map and independent evidence every pass")
            runtime=features.modules();np,torch,vision,cv2,scipy,av=runtime
            torch.set_num_threads(1);cv2.setNumThreads(1)
            torch.use_deterministic_algorithms(True)
            encoder=features.Encoder(self.spec.checkpoint_root,self.spec.checkpoint.row(),
                                     owner,self.spec.limits,runtime)
            itemsize=4 if block in ("learned_video","learned_video_reversed") else 8
            features.reserve(owner,self.spec.limits,1102*(stop-start)*itemsize,
                             "full1102 requested feature column matrix")
            answer=np.empty((1102,stop-start),dtype=np.float32 if itemsize==4 else np.float64)
            rows=[];identities=[]
            for row_index,role in enumerate(observed_map.roles):
                row_before=dict(owner.used);row_wall=time.monotonic();row_cpu=time.process_time()
                decoded=features.decode_features(self.spec.media_root,role,
                    observed_map.library_versions,owner,self.spec.limits,runtime)
                blocks=_blocks(decoded,role,encoder,runtime,owner,self.spec.limits)
                need(set(blocks)==set(BLOCK_DIMS),"all six complete original feature blocks")
                full={}
                for name,width in BLOCK_DIMS.items():
                    need(blocks[name].shape==(width,),"no reduced or truncated original feature row")
                    full[name]=_identity(blocks[name],owner,np)
                if self._baseline is not None:
                    need(full==self._baseline[row_index],
                         "every full regenerated feature row must exactly equal first completed pass")
                answer[row_index]=blocks[block][start:stop]
                # Retain exact clock/provenance observations and full row hashes;
                # hashes do not claim external authenticity or a fitted score.
                rows.append({"video_id":role.video_id,"full_row_identities":full,
                             "source_observations":decoded["provenance"],
                             "s3d_forward_calls":16,
                             "cost":{"cpu_seconds":time.process_time()-row_cpu,
                                     "wall_seconds":time.monotonic()-row_wall,
                                     "logical_delta":{k:owner.used[k]-row_before[k] for k in row_before}}})
                identities.append(full)
                # The next decode does not retain this video's numerical arrays.
                del blocks,decoded
            need(encoder.calls==1102*16,"every full producer call completed")
            result_identity=_identity(answer,owner,np)
            answer.flags.writeable=False
            first=self._baseline is None
            document={"schema":"neural080_full_feature_regeneration_pass_v1",
                      "pass_index":index,"stream_spec_sha256":self.spec_sha256,
                      "block":block,"start":start,"stop":stop,
                      "explicit_column_width":self.spec.column_width,
                      "video_ids":list(VIDEO_IDS),"block_widths":dict(BLOCK_DIMS),
                      "range_identity":result_identity,"rows":rows,
                      "baseline_pass":self._baseline_pass,"sets_first_complete_baseline":first,
                      "source_map_descriptor":self.spec.source_map_descriptor.row(),
                      "canonical_source_map_sha256":observed_map.canonical_source_map_sha256,
                      "mapping_evidence":dict(observed_map.identity_evidence),
                      "checkpoint":self.spec.checkpoint.row(),
                      "programme_tree_sha256":self.spec.programme_tree_sha256,
                      "programme_origin_captures":imported_origins,
                      "runtime_versions":features.VERSIONS,
                      "native_library_versions":dict(observed_map.library_versions),
                      "feature_limits":asdict(self.spec.limits),
                      "s3d_forward_calls":encoder.calls,
                      "resampling":"identical complete native audio/constant-boundary Kaiser5 polyphase16000Hz; exactt0phase gate; periodicHann400/hop160/reflect200/first300centers",
                      "workspace":"one video's full original decoded/feature arrays, encoder, all1102 requested columns, and complete pass clock/hash metadata; explicit FeatureLimits/Owner reservations; native peaks separately qualified",
                      "cost":{"cpu_seconds":time.process_time()-cpu,"wall_seconds":time.monotonic()-wall,
                              "logical_delta":{k:owner.used[k]-before[k] for k in before}},
                      "cost_scope":"through final range hash before this ledger serialization; the same Owner also charges the final ledger write",
                      "source_binding_limit":"origin-file recapture complements mandatory caller-validated readonly whole-tree bootstrap; no loaded-code or ABA attestation",
                      "numeric_policy":"original feature operations/dtypes only; no scaler, PCA or solver choice"}
            ledger=self.writer.document("feature-pass-%06d.json"%index,document)
            if first:
                self._baseline=tuple(identities)
                self._baseline_pass=dict(ledger)
            self._last_pass=dict(ledger)
        except BaseException as exc:
            owner.failure(record,exc)
        finally:
            if entered:self._active=False
        owner.complete(record)
        return answer
