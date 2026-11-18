"""Optical-only typed viewer and complete first-final native-frame collection.

Operator-side source component, not a process or filesystem boundary. The
prepared optical packet, training calibration and source identities still need
independent qualification. No private reference is accepted or imported.
"""
from bisect import bisect_left
from fractions import Fraction
import copy
import hashlib
import html
import json
import math
from pathlib import Path
import types

SCORER_SHA256 = "781e3c625cd6d694392886ec94730314fe2d2fb98857ded7afa3a47a2cfcede2"
_source = Path(__file__).resolve().parent.parent / "voltron-native-frame-events-v1/event_score.py"
_body = _source.read_bytes()
if hashlib.sha256(_body).hexdigest() != SCORER_SHA256:
    raise ImportError("native-frame scoring dependency changed; review before adoption")
S = types.ModuleType("voltron_viewer_native_frame_dependency")
exec(compile(_body, str(_source), "exec"), S.__dict__)
del _body

TASK = S.TASK
MAX_VIEW_FRAMES = 2048
MAX_ACTIONS = 1000000
UNITS = {"raw_fluorescence", "delta_f_over_f", "arbitrary_fluorescence"}


class ViewerError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise ViewerError(message)


def identity(value):
    try:
        body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise ViewerError("finite JSON required") from exc
    return hashlib.sha256(body).hexdigest()


def scalar(value):
    need(type(value) in (int, float), "literal optical scalar required")
    if type(value) is float:
        need(math.isfinite(value), "finite optical scalar required")
    need(abs(value) <= 2**63, "optical scalar format bound")
    return Fraction(value)


def exact(value):
    try:
        return S.exact_time(value)
    except S.ContractError as exc:
        raise ViewerError(str(exc)) from exc


def fields(value, names):
    need(type(value) is dict and set(value) == set(names), "exact fields required")


def _capture(public, packet):
    contract = S.public_contract(public)
    need(len({m["fold_id"] for m in contract["movies"].values()}) == 6,
         "six public query folds required")
    cell_folds = {}
    for movie in contract["movies"].values():
        fold = cell_folds.setdefault(movie["cell_id"], movie["fold_id"])
        need(fold == movie["fold_id"], "one public fold per cell required")
    fields(packet, ("schema", "task_id", "public_sha256", "preparation_sha256", "movies"))
    need(packet["schema"] == "voltron-prepared-optical-traces/v1" and
         packet["task_id"] == TASK and packet["public_sha256"] == contract["identity"],
         "optical packet task/public binding")
    S.digest(packet["preparation_sha256"])
    need(type(packet["movies"]) is dict and
         set(packet["movies"]) == set(contract["movies"]), "all 34 optical movies required")
    traces = {}
    for mid, movie in contract["movies"].items():
        row = packet["movies"][mid]
        fields(row, ("samples", "amplitude_unit", "indicator_polarity", "exposure_seconds"))
        need(type(row["amplitude_unit"]) is str and row["amplitude_unit"] in UNITS,
             "explicit supported optical unit required")
        need(type(row["indicator_polarity"]) is int and row["indicator_polarity"] in (-1, 1),
             "source-qualified indicator polarity required")
        exposure = exact(row["exposure_seconds"])
        need(0 < exposure <= movie["end"] - movie["start"], "positive exposure duration")
        values = row["samples"]
        need(type(values) is list and len(values) == len(movie["frame_times"]),
             "complete native-frame optical vector required")
        if movie["input_disposition"] == "optical_extraction_failed":
            need(all(value is None for value in values), "failed extraction retains explicit missing samples")
        frozen = []
        for t, value in zip(movie["frame_times"], values):
            if value is None:
                need(not S._contains(t, movie["optical_valid_intervals"]),
                     "missing sample inside declared valid optical support")
                frozen.append(None)
            else:
                scalar(value)
                frozen.append(value)
        traces[mid] = (tuple(frozen), row["amplitude_unit"], row["indicator_polarity"], exposure)
    return contract, traces, identity(packet)


def _indices(values, left, right):
    need(type(values) is list and len(values) <= S.MAX_EVENTS, "bounded event list required")
    previous = left - 1
    for index in values:
        need(type(index) is int and left <= index < right and previous < index,
             "sorted unique literal core-owned frame indices required")
        previous = index
    return tuple(values)


def _view_geometry(contract, cores, request):
    fields(request, ("core_id", "start_frame", "end_frame", "low", "high"))
    cid = request["core_id"]
    need(type(cid) is str and cid in cores, "core outside this held fold")
    mid, a, b = cores[cid]
    movie = contract["movies"][mid]
    times = movie["frame_times"]
    end = times[b] if b < len(times) else movie["end"]
    halo_a, halo_b = bisect_left(times, times[a] - 1), bisect_left(times, end + 1)
    start_frame, end_frame = request["start_frame"], request["end_frame"]
    need(type(start_frame) is int and type(end_frame) is int and
         halo_a <= start_frame < end_frame <= halo_b and
         end_frame - start_frame <= MAX_VIEW_FRAMES,
         "bounded native-frame window within one-second context halo required")
    lo, hi = scalar(request["low"]), scalar(request["high"])
    need(lo < hi, "increasing explicit vertical bounds required")
    return mid, a, b, movie, times, lo, hi


class Session:
    """One held-fold collector. Only this API belongs on a participant transport.

    The trusted operator retains this object and all optical packet storage;
    passing the Python object itself to participant code is not isolation.
    """

    def __init__(self, public, packet, *, fold_id, program_sha256, calibration_sha256):
        self._contract, self._traces, self._packet_sha256 = _capture(public, packet)
        S.name(fold_id)
        S.digest(program_sha256)
        S.digest(calibration_sha256)
        self._fold = fold_id
        self._program = program_sha256
        self._calibration = calibration_sha256
        self._cores = {cid: row for cid, row in self._contract["cores"].items()
                       if self._contract["movies"][row[0]]["fold_id"] == fold_id}
        need(bool(self._cores), "unknown or empty held fold")
        self._answers = {}
        self._event_total = 0
        self._actions = []
        self._closed = False
        self._final = None
        self._head = identity(self._header())

    def _header(self):
        return {"schema": "voltron-fold-frame-responses/v1", "task_id": TASK,
                "public_sha256": self._contract["identity"],
                "packet_sha256": self._packet_sha256, "fold_id": self._fold,
                "program_sha256": self._program, "calibration_sha256": self._calibration}

    def _open(self):
        need(not self._closed, "session is closed")

    def _record(self, action, request, response):
        need(len(self._actions) < MAX_ACTIONS, "action format ceiling; no truncation")
        entry = {"seq": len(self._actions), "previous_sha256": self._head,
                 "action": action, "request": request, "response_sha256": identity(response)}
        entry["sha256"] = identity(entry)
        self._head = entry["sha256"]
        self._actions.append(entry)

    def catalog(self):
        self._open()
        return [{"core_id": cid, "movie_id": mid, "start_frame": a, "end_frame": b,
                 "input_disposition": self._contract["movies"][mid]["input_disposition"]}
                for cid, (mid, a, b) in sorted(self._cores.items())]

    def view(self, core_id, *, start_frame, end_frame, low, high):
        """Every requested sample is retained; no binning or clock substitution.

        Vertical bounds are explicit participant/operator choices, never fitted
        automatically from query values. Clipped/missing frames are disclosed.
        The exact original optical vector stays frozen for other declared arms.
        """
        self._open()
        request = {"core_id": core_id, "start_frame": start_frame,
                   "end_frame": end_frame, "low": low, "high": high}
        mid, a, b, movie, times, lo, hi = _view_geometry(self._contract, self._cores, request)
        values, unit, polarity, exposure = self._traces[mid]
        left, right = times[start_frame], times[end_frame - 1]
        # A singleton view uses its known exposure solely as drawing width.
        # It never changes the timestamp or prediction index.
        if left == right:
            left, right = left - exposure / 2, right + exposure / 2
        parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">',
                 '<rect width="1200" height="400" fill="white"/>',
                 '<path d="M60 30V350H1160" fill="none" stroke="black"/>']
        missing, clipped, points = [], [], []
        for index in range(start_frame, end_frame):
            x = 60 + 1100 * float((times[index] - left) / (right - left))
            value = values[index]
            valid = S._contains(times[index], movie["optical_valid_intervals"])
            if value is None:
                missing.append(index)
                parts.append(f'<path d="M{x:.8f} 342v8" stroke="#888"/>')
                points.append(None)
                continue
            v = scalar(value)
            is_clipped = not lo <= v <= hi
            if is_clipped:
                clipped.append(index)
            y = 350 - 320 * float((min(hi, max(lo, v)) - lo) / (hi - lo))
            color = '#c33' if is_clipped else '#163d80' if valid else '#999'
            parts.append(f'<circle cx="{x:.8f}" cy="{y:.8f}" r="2" fill="{color}"/>')
            points.append((x, y, valid, is_clipped))
        # Never draw a line through missingness or a positive invalid interval.
        for offset, (p, q) in enumerate(zip(points, points[1:])):
            i = start_frame + offset
            if p is not None and q is not None and p[2] and q[2] and not p[3] and not q[3] and any(
                    x <= times[i] < times[i + 1] < y for x, y in movie["optical_valid_intervals"]):
                parts.append(f'<path d="M{p[0]:.8f} {p[1]:.8f}L{q[0]:.8f} {q[1]:.8f}" stroke="#163d80" fill="none"/>')
        label = (f'{core_id}: frames {start_frame}:{end_frame}; {unit}; polarity {polarity:+d}; '
                 f'vertical [{low!r}, {high!r}]; clipped {len(clipped)}; missing {len(missing)}')
        parts.append(f'<text x="60" y="20" font-size="12">{html.escape(label)}</text>')
        parts.append(f'<text x="60" y="375" font-size="12">native seconds: {html.escape(str(left))} to {html.escape(str(right))}</text>')
        parts.append('</svg>')
        response = {"schema": "voltron-optical-view/v1", "core_id": core_id,
                    "start_frame": start_frame, "end_frame": end_frame,
                    "core_start_frame": a, "core_end_frame": b,
                    "native_start_seconds": S.ratio(times[start_frame]),
                    "native_last_seconds": S.ratio(times[end_frame - 1]),
                    "exposure_seconds": S.ratio(exposure), "amplitude_unit": unit,
                    "indicator_polarity": polarity, "clipped_frames": clipped,
                    "missing_frames": missing, "svg": ''.join(parts)}
        self._record("view", request, response)
        return response

    def answer(self, core_id, frames):
        self._open()
        need(type(core_id) is str and core_id in self._cores and core_id not in self._answers,
             "unknown core or already-final response")
        _, a, b = self._cores[core_id]
        captured = _indices(frames, a, b)
        need(self._event_total + len(captured) <= S.MAX_EVENTS,
             "whole-fold event format ceiling")
        response = {"core_id": core_id, "frames": list(captured), "final": True}
        self._record("answer", {"core_id": core_id, "frames": list(captured)}, response)
        self._answers[core_id] = captured
        self._event_total += len(captured)
        return copy.deepcopy(response)

    def finish(self):
        if self._final is not None:
            return copy.deepcopy(self._final)
        self._open()
        need(set(self._answers) == set(self._cores), "complete held-fold core answers required")
        final = {**self._header(), "cores": {k: list(v) for k, v in sorted(self._answers.items())},
                 "actions": copy.deepcopy(self._actions), "action_head_sha256": self._head,
                 "scientific_qualified": False}
        final["receipt_sha256"] = identity(final)
        self._closed = True
        self._final = copy.deepcopy(final)
        return copy.deepcopy(final)


def assemble_candidate(public, packet, receipts):
    """Join exactly six complete fold receipts into the unchanged scorer role.

    Hashes/chain consistency do not prove who produced a receipt, physical
    isolation, authentic calibration or that a model viewed the returned SVG.
    """
    contract, _, packet_sha = _capture(public, packet)
    folds = {m["fold_id"] for m in contract["movies"].values()}
    need(type(receipts) is list and len(receipts) == 6, "six complete fold receipts required")
    joined, calibrations, seen, programs = {}, {}, set(), set()
    for row in receipts:
        fields(row, ("schema", "task_id", "public_sha256", "packet_sha256", "fold_id",
                     "program_sha256", "calibration_sha256", "cores", "actions",
                     "action_head_sha256", "scientific_qualified", "receipt_sha256"))
        unsigned = {k: v for k, v in row.items() if k != "receipt_sha256"}
        need(row["receipt_sha256"] == identity(unsigned), "fold receipt identity mismatch")
        fold = row["fold_id"]
        S.name(fold)
        need(row["schema"] == "voltron-fold-frame-responses/v1" and row["task_id"] == TASK and
             row["public_sha256"] == contract["identity"] and row["packet_sha256"] == packet_sha and
             row["scientific_qualified"] is False and fold in folds and fold not in seen,
             "bound unique unqualified fold receipt required")
        seen.add(fold)
        programs.add(S.digest(row["program_sha256"]))
        calibrations[fold] = S.digest(row["calibration_sha256"])
        required = {cid: x for cid, x in contract["cores"].items()
                    if contract["movies"][x[0]]["fold_id"] == fold}
        need(type(row["cores"]) is dict and set(row["cores"]) == set(required), "complete fold core coverage")
        declared = {cid: list(_indices(row["cores"][cid], a, b))
                    for cid, (_, a, b) in required.items()}
        answers = {}
        head = identity({k: row[k] for k in ("schema", "task_id", "public_sha256", "packet_sha256",
                                            "fold_id", "program_sha256", "calibration_sha256")})
        need(type(row["actions"]) is list and len(row["actions"]) <= MAX_ACTIONS, "bounded action chain")
        for seq, action in enumerate(row["actions"]):
            fields(action, ("seq", "previous_sha256", "action", "request", "response_sha256", "sha256"))
            need(type(action["seq"]) is int and action["seq"] == seq and
                 action["previous_sha256"] == head and action["sha256"] ==
                 identity({k: v for k, v in action.items() if k != "sha256"}), "action chain mismatch")
            head = action["sha256"]
            S.digest(action["response_sha256"])
            request = action["request"]
            need(action["action"] in ("view", "answer"), "unsupported recorded action")
            if action["action"] == "answer":
                fields(request, ("core_id", "frames"))
                cid = request["core_id"]
                need(cid in required and cid not in answers, "first-final same-fold action required")
                _, a, b = required[cid]
                indices = list(_indices(request["frames"], a, b))
                need(action["response_sha256"] == identity({"core_id": cid, "frames": indices, "final": True}),
                     "answer response identity mismatch")
                answers[cid] = indices
            else:
                _view_geometry(contract, required, request)
        need(head == row["action_head_sha256"] and answers == declared, "final answers/chain mismatch")
        joined.update(answers)
    need(seen == folds and len(programs) == 1, "one frozen program across all six folds required")
    need(sum(map(len, joined.values())) <= S.MAX_EVENTS, "whole-role event format ceiling")
    return {"program_sha256": next(iter(programs)),
            "calibration_sha256": identity({"schema": "voltron-six-fold-calibration-identities/v1",
                                             "public_sha256": contract["identity"], "folds": calibrations}),
            "cores": dict(sorted(joined.items()))}
