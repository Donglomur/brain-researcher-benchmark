"""Strict adapter for the already qualified complete pre-pair MEG bank.

This does not re-create CSV parsing/QC or infer archive-generation lineage.  It
authenticates the saved inventory and joins every pre/post-QC and pair record.
There is no archive reader, scientific fit, duration or Data_Type filter here.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

ORIENTATIONS = (("Category_Selective", "Prefrontal_Cortex"),
                ("Prefrontal_Cortex", "Category_Selective"))
LABELS = ("face", "object")
MAX_BYTES = 4 * 1024 * 1024
MAX_LINE = 65536
MAX_RECORDS = 10000
KINDS = {"archive", "member_start", "member_parser_stage", "complete_prepair_bank_row",
         "member_parser_contract", "participant_identity_disposition",
         "participant_identity_audit_complete", "member_complete", "global_stimulus_order",
         "source_QC_stage", "source_QC_summary", "complete_post_QC_bank_row",
         "post_QC_target_row", "complete_bank_summary"}


class AdmissionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AdmissionError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def no_duplicate_keys(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "duplicate JSON key")
        result[k] = v
    return result


def text_tag(value):
    require(isinstance(value, dict) and set(value) == {"type", "value"}
            and value["type"] == "str" and isinstance(value["value"], str)
            and 0 < len(value["value"]) <= 128, "invalid exact string tag")
    return value["value"]


def float_tag(value):
    require(isinstance(value, dict) and set(value) == {"type", "hex"}
            and value["type"] == "float" and isinstance(value["hex"], str)
            and len(value["hex"]) <= 64, "invalid exact float tag")
    try:
        result = float.fromhex(value["hex"])
    except (ValueError, OverflowError) as exc:
        raise AdmissionError("invalid float hex") from exc
    require(math.isfinite(result) and result.hex() == value["hex"],
            "nonfinite/noncanonical float hex")
    return result


def record_key(record):
    direction = tuple(record.get("direction", ()))
    require(direction in ORIENTATIONS, "unrecognized orientation")
    for name in ("member", "original_row", "source_context_index"):
        require(type(record.get(name)) is int and 0 <= record[name] < 100000000,
                "invalid row provenance")
    sha = record.get("row_sha256")
    require(isinstance(sha, str) and len(sha) == 64
            and all(c in "0123456789abcdef" for c in sha), "invalid row hash")
    return (record["member"], record["original_row"],
            record["source_context_index"], direction)


@dataclass(frozen=True)
class Row:
    key: str
    participant: str
    label: str
    value: float
    orientation: tuple
    member: int
    original_row: int
    source_context_index: int
    row_sha256: str


@dataclass(frozen=True)
class Bank:
    roster: tuple
    rows: tuple
    inventory_sha256: str
    source_kind: str
    source_ordered_pair: tuple = LABELS

    def direction(self, orientation):
        require(tuple(orientation) in ORIENTATIONS, "orientation selection")
        return tuple(r for r in self.rows if r.orientation == tuple(orientation))


def decode_inventory(stream, binding, *, source_kind):
    """One bounded stream pass; generated controls supply their own exact binding.

    Original binding is pinned by the disabled execution profile.  Final adapter
    execution on original input has not been selected during construction.
    """
    require(source_kind in ("generated-control", "qualified-original-bank"), "source kind")
    roster = tuple(binding["roster"])
    require(len(roster) == 94 and len(set(roster)) == 94
            and all(isinstance(p, str) and 0 < len(p) <= 64 for p in roster), "94-person roster")
    members = binding["members"]
    require(len(members) == 94, "member cardinality")
    member_map = {x["member"]: x["participant"] for x in members}
    require(len(member_map) == 94 and tuple(member_map.values()) == roster, "ordered member roster")
    h = hashlib.sha256(); total = 0; counts = {}; pre = {}; post = {}; targets = []
    member_seen = []; starts = []; qc = {}; globals_seen = []; summary = None
    record_order = []; target_keys = set(); archive_seen = False
    for line_no in range(MAX_RECORDS + 1):
        line = stream.readline(MAX_LINE + 1)
        if not line:
            break
        require(line_no < MAX_RECORDS and len(line) <= MAX_LINE and line.endswith(b"\n"),
                "inventory record/line bound")
        total += len(line)
        require(total <= MAX_BYTES, "inventory byte cap")
        h.update(line)
        try:
            x = json.loads(line, object_pairs_hook=no_duplicate_keys,
                           parse_constant=lambda _: (_ for _ in ()).throw(AdmissionError("JSON nonfinite")))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise AdmissionError("invalid inventory JSON") from exc
        require(isinstance(x, dict), "record object")
        kind = x.get("kind"); require(kind in KINDS, "unexpected inventory kind")
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "archive":
            require(not archive_seen and line_no == 0, "archive identity placement")
            archive_seen = True
        elif kind == "member_start":
            require(member_map.get(x.get("member")) == x.get("participant"), "member start identity")
            starts.append(x["member"])
        elif kind == "member_complete":
            require(member_map.get(x.get("member")) == x.get("participant")
                    and x.get("complete_member_CRC_verified") is True, "member completion/CRC")
            expected = members[len(member_seen)] if len(member_seen) < 94 else {}
            require(all(x.get(k) == expected.get(k) for k in
                        ("member", "participant", "rows", "ordered_rows_sha256")),
                    "member source/order binding")
            member_seen.append(x["member"])
        elif kind == "member_parser_contract":
            require(x.get("full_member_read_csv_defaults") is True
                    and x.get("raw_pandas_selection_equal") is True
                    and x.get("additional_duration_or_Data_Type_filter") is False,
                    "qualified parser/selection contract")
        elif kind == "global_stimulus_order":
            require(x.get("order") == len(globals_seen)
                    and x.get("from_all_SPI_and_context_rows") is True, "global stimulus order")
            label = text_tag(x["value"])
            require(label not in globals_seen, "duplicate global stimulus")
            globals_seen.append(label)
        elif kind in ("complete_prepair_bank_row", "complete_post_QC_bank_row", "post_QC_target_row"):
            key = record_key(x)
            require(member_map.get(x.get("member")) == x.get("participant"), "bank participant identity")
            if kind == "complete_prepair_bank_row":
                require(key not in pre and len(pre) < 752
                        and x.get("before_QC_or_pair_restriction") is True, "pre-pair uniqueness/order")
                core = x["normalized_core"]
                require(text_tag(core["subject_ID"]) == x["participant"]
                        and text_tag(core["SPI"]) == "bary-sq_dtw_max"
                        and text_tag(core["relevance_type"]) == "Irrelevant"
                        and text_tag(core["stimulus_presentation"]) == "on"
                        and (text_tag(core["meta_ROI_from"]), text_tag(core["meta_ROI_to"])) == key[-1],
                        "source-selected full-bank context")
                label = text_tag(core["stimulus_type"]); value = float_tag(core["value"])
                pre[key] = (x["participant"], label, value, x["row_sha256"], core["value"])
                record_order.append(key)
            else:
                require(key in pre and x["row_sha256"] == pre[key][3], "missing/mixed-origin pre-pair join")
                label = text_tag(x["stimulus"]); value = float_tag(x["value"])
                require((x["participant"], label, value) == pre[key][:3]
                        and x["value"] == pre[key][4], "qualified no-imputation value/label join")
                if kind == "complete_post_QC_bank_row":
                    require(key not in post and x.get("before_pair_restriction") is True
                            and x.get("source_QC_rejected") is False, "post-QC bank admission")
                    post[key] = x
                else:
                    require(key in post and key not in target_keys and len(targets) < 376
                            and label in LABELS and x.get("pair_restriction_after_QC") is True,
                            "target order/uniqueness/support")
                    target_keys.add(key)
                    targets.append(Row(digest([key, x["participant"], label, x["row_sha256"]]),
                                       x["participant"], label, value, key[-1], key[0], key[1], key[2], x["row_sha256"]))
        elif kind == "source_QC_summary":
            direction = tuple(x.get("direction", ()))
            require(direction in ORIENTATIONS and direction not in qc
                    and x.get("rows") == 376 and x.get("missing_before") == 0
                    and x.get("imputation_performed") is False
                    and x.get("imputed_assignments") == [] and x.get("source_QC_rejected") is False,
                    "qualified all-category QC contract")
            qc[direction] = x
        elif kind == "complete_bank_summary":
            require(summary is None, "duplicate bank summary"); summary = x
    require(total == binding["inventory"]["bytes"] and h.hexdigest() == binding["inventory"]["sha256"],
            "inventory byte/SHA identity")
    require(counts == binding["expected_counts"], "complete record-kind inventory")
    require(starts == list(member_map) and member_seen == list(member_map), "complete ordered member population")
    require(len(pre) == len(post) == 752 and set(pre) == set(post)
            and len(targets) == 376 and len(qc) == 2, "complete pre/post/target bank")
    require(len(globals_seen) == 4 and tuple(x for x in globals_seen if x in LABELS) == LABELS,
            "source global pair ordering")
    require(summary is not None and summary.get("prepair_rows") == 752
            and summary.get("source_ordered_target_pair") == list(LABELS)
            and summary.get("complete_target_support_after_source_QC") is True
            and summary.get("no_Data_Type_or_duration_filter") is True, "complete bank summary")
    for orientation in ORIENTATIONS:
        keys = [k for k in record_order if k[-1] == orientation]
        require(len(keys) == 376, "orientation full-bank size")
        require([k for k in keys if pre[k][1] in LABELS] ==
                [k for k in post if k[-1] == orientation and pre[k][1] in LABELS],
                "post-QC preserved source row order")
        selected = [r for r in targets if r.orientation == orientation]
        require([(r.member, r.original_row, r.source_context_index, r.orientation) for r in selected]
                == [k for k in keys if pre[k][1] in LABELS], "target preserved source row order")
        support = {(p, label): 0 for p in roster for label in globals_seen}
        for k in keys:
            require((pre[k][0], pre[k][1]) in support, "unrecognized full-bank label")
            support[(pre[k][0], pre[k][1])] += 1
        require(set(support.values()) == {1}, "every participant has every full-bank category once")
        require(len(selected) == 188, "all 188 endpoint rows")
    return Bank(roster, tuple(targets), h.hexdigest(), source_kind)


def load_original_inventory(path, binding):
    path = Path(path)
    require(not path.is_symlink() and path.is_file()
            and path.stat().st_size == binding["inventory"]["bytes"], "regular pinned inventory")
    require(str(path) == binding["inventory"]["path"], "exact original inventory locator")
    with path.open("rb") as stream:
        return decode_inventory(stream, binding, source_kind="qualified-original-bank")
