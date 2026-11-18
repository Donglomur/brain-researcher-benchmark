"""Public-only typed SVG views and complete immutable NEURAL-035 responses.

This is a trusted-operator component, not a participant process sandbox or an
image-only transport. A host must rasterize SVG before claiming a vision-only
condition. No private targets, grader, model, fit or data-root resolver is used.
"""
from __future__ import annotations

from dataclasses import dataclass
import html
import importlib.util
import json
import math
from numbers import Real
from pathlib import Path
import re


_LOADER = Path(__file__).resolve().parents[1] / "public-delivery-v2" / "load_public.py"
_SPEC = importlib.util.spec_from_file_location("_neural035_viewer_public_loader", _LOADER)
public_loader = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(public_loader)

REQUEST_CAP = 131_072
SUBMISSION_CAP = 2_000_000
SVG_CAP = 200_000
MAX_CELLS_PER_VIEW = 8
# Twice the 5,060 single-cell public-block views covers all permitted data twice.
# This is a proposed display budget; no actual participant runtime is qualified.
VIEW_BUDGET = 10_120
PUBLIC_STARTS = (0, 30, 60, 90, 150)


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value):
    _need(isinstance(value, Real) and not isinstance(value, bool), "nonboolean real value")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("finite numeric value") from exc
    _need(math.isfinite(result), "finite numeric value")
    return result


@dataclass(frozen=True)
class PublicSession:
    session_id: str
    cell_ids: tuple[str, ...]
    queries: tuple[tuple[str, int], ...]
    # Immutable cell-major copies: five blocks, every cell, 300 samples each.
    blocks: tuple


@dataclass(frozen=True)
class Observations:
    """An immutable copy made only from the admitted early public observations.

    ``from_loaded`` expects the return value of public-delivery-v2.load. It also
    checks its whole metadata/geometry before copying values, so accidental
    truncation or query-array injection cannot silently change the task.
    Authenticity still requires the separately qualified external delivery pins.
    """

    sessions: tuple[PublicSession, ...]

    @classmethod
    def from_loaded(cls, rows):
        _need(type(rows) is list and len(rows) == 14, "all 14 public sessions")
        _need(all(type(row) is dict and set(row) == {"metadata", "calibration", "validation"}
                  for row in rows), "only loaded public fields")
        manifest = {"schema": "neural035-public-v1", "sessions": [row["metadata"] for row in rows]}
        public_loader.validate_manifest(manifest)
        for row in rows:
            n = len(row["metadata"]["cell_ids"])
            _need(getattr(row["calibration"], "shape", None) == (4, 300, n)
                  and getattr(row["validation"], "shape", None) == (1, 300, n),
                  "complete public array geometry")
        sessions = []
        for row in rows:
            meta = row["metadata"]
            n = len(meta["cell_ids"])
            blocks = tuple(
                tuple(tuple(_number(array[b, t, c]) for t in range(300)) for c in range(n))
                for array, b in [(row["calibration"], k) for k in range(4)]
                + [(row["validation"], 0)]
            )
            sessions.append(PublicSession(
                meta["session_id"], tuple(meta["cell_ids"]),
                tuple((query["query_id"], query["start_seconds"]) for query in meta["queries"]),
                blocks,
            ))
        return cls(tuple(sessions))


def _validate_observations(observations):
    """Check direct dataclass construction as well as the loader factory.

    The dataclasses themselves do not enforce type annotations. Validate every
    immutable axis before constructing lookup dictionaries, so duplicate IDs or
    a truncated cohort cannot be silently collapsed by those dictionaries.
    """
    _need(type(observations) is Observations and type(observations.sessions) is tuple
          and len(observations.sessions) == 14, "complete immutable observations")
    seen_sessions, seen_queries, cell_count = set(), set(), 0
    def opaque(value):
        return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    for session in observations.sessions:
        _need(type(session) is PublicSession, "immutable public session record")
        _need(opaque(session.session_id) and session.session_id not in seen_sessions,
              "unique opaque public sessions")
        seen_sessions.add(session.session_id)
        cells = session.cell_ids
        _need(type(cells) is tuple and 2 <= len(cells) <= 1012
              and all(opaque(c) for c in cells) and len(set(cells)) == len(cells),
              "immutable unique session-local cells")
        cell_count += len(cells)
        _need(type(session.queries) is tuple and len(session.queries) == 2,
              "two immutable query records")
        for query, expected_start in zip(session.queries, (210, 270), strict=True):
            _need(type(query) is tuple and len(query) == 2 and opaque(query[0])
                  and query[0] not in seen_queries and type(query[1]) is int
                  and query[1] == expected_start, "unique queries at original future times")
            seen_queries.add(query[0])
        _need(type(session.blocks) is tuple and len(session.blocks) == 5,
              "five immutable public blocks")
        for block in session.blocks:
            _need(type(block) is tuple and len(block) == len(cells),
                  "every cell in every immutable block")
            for trace in block:
                _need(type(trace) is tuple and len(trace) == 300,
                      "all 300 samples in immutable trace")
                _need(all(type(v) is float and math.isfinite(v) for v in trace),
                      "immutable finite float samples")
    _need(cell_count == 1012 and len(seen_queries) == 28,
          "complete 1012 cells and 28 unique queries")


def _svg(session, block, cells):
    width, left, right, panel = 1100, 90, 1080, 170
    height = 70 + panel * len(cells)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<style>text{font-family:monospace;font-size:12px;fill:#17212b}'
           '.axis{stroke:#687683;stroke-width:1}.trace{fill:none;stroke:#174e8a;stroke-width:1.2}</style>',
           f'<title>NEURAL-035 public block {PUBLIC_STARTS[block]}–{PUBLIC_STARTS[block]+30} seconds</title>',
           f'<text x="12" y="22">Session {html.escape(session.session_id)}</text>',
           f'<text x="12" y="43">Public {"validation" if block == 4 else "calibration"}; '
           f'block {PUBLIC_STARTS[block]}–{PUBLIC_STARTS[block]+30} s; '
           '300 sample centres at 10 Hz; processed fluorescence, no physical unit asserted.</text>']
    for position, cell in enumerate(cells):
        top = 75 + panel * position
        bottom = top + 105
        trace = session.blocks[block][cell]
        # A cell's common scale across all five public blocks supports comparisons.
        # It cannot use either future query block.
        lo = min(min(b[cell]) for b in session.blocks)
        hi = max(max(b[cell]) for b in session.blocks)
        scale = max(abs(lo), abs(hi)) if lo != hi else 1.0
        low_scaled, high_scaled = lo / scale, hi / scale
        points = []
        for sample, value in enumerate(trace):
            x = left + (sample + .5) / 300 * (right - left)
            fraction = .5 if lo == hi else (value / scale - low_scaled) / (high_scaled - low_scaled)
            y = bottom - fraction * (bottom - top)
            _need(math.isfinite(x) and math.isfinite(y), "finite rendered coordinate")
            points.append(f"{x:.6f},{y:.6f}")
        out.extend([
            f'<text x="12" y="{top-10}">Cell {cell}: {html.escape(session.cell_ids[cell])}</text>',
            f'<text x="2" y="{top+5}">{hi:.7g}</text>',
            f'<text x="2" y="{bottom}">{lo:.7g}</text>',
            f'<path class="axis" d="M {left} {top} V {bottom} H {right}"/>',
            f'<polyline class="trace" points="{" ".join(points)}"/>',
        ])
        for second in (0, 10, 20, 30):
            x = left + second / 30 * (right - left)
            out.append(f'<text x="{x:.6f}" y="{bottom+20}">{second}</text>')
        out.append(f'<text x="{left+200}" y="{bottom+38}">seconds within block; '
                   f'shared per-cell scale across all five public blocks{"; constant" if lo == hi else ""}</text>')
    out.append('</svg>')
    result = '\n'.join(out)
    _need(len(result.encode()) <= SVG_CAP, "bounded SVG response")
    return result


class Viewer:
    """A typed action state machine owned by a trusted operator.

    The participant receives only serialized action results. Giving it this
    Python object, filesystem access or SVG source is not a vision-only sandbox.
    Answers become immutable on successful acceptance; malformed attempts never
    partially commit. ``finish`` exports the unchanged original submission ABI.
    """

    def __init__(self, observations):
        _validate_observations(observations)
        self._observations = observations
        self._sessions = {s.session_id: s for s in observations.sessions}
        self._queries = {qid: (s, start) for s in observations.sessions for qid, start in s.queries}
        self._answers = {}
        self._views = 0
        self._closed = False

    def handle(self, raw):
        """Accept one bounded UTF-8 JSON action, rejecting duplicate keys/NaN."""
        _need(type(raw) is bytes and 0 < len(raw) <= REQUEST_CAP, "bounded action bytes")
        try:
            action = public_loader.safe.strict(raw.decode('utf-8'))
        except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("invalid action JSON") from exc
        return self.act(action)

    def act(self, request):
        _need(not self._closed, "viewer already finished")
        _need(type(request) is dict and type(request.get("action")) is str, "typed action")
        kind = request["action"]
        if kind == "catalogue":
            _need(set(request) == {"action"}, "exact catalogue fields")
            return {"kind": "catalogue", "view_budget": VIEW_BUDGET,
                    "public_block_starts_seconds": list(PUBLIC_STARTS),
                    "samples_per_block": 300, "sample_rate_hz": 10,
                    "sessions": [{"session_id": s.session_id, "cell_ids": list(s.cell_ids),
                                  "queries": [{"query_id": q, "start_seconds": t} for q, t in s.queries]}
                                 for s in self._observations.sessions]}
        if kind == "view":
            _need(set(request) == {"action", "session_id", "block", "cells"}, "exact view fields")
            sid, block, cells = request["session_id"], request["block"], request["cells"]
            _need(type(sid) is str and sid in self._sessions, "known public session")
            session = self._sessions[sid]
            _need(type(block) is int and 0 <= block < 5, "only five early public blocks")
            _need(type(cells) is list and 1 <= len(cells) <= MAX_CELLS_PER_VIEW
                  and all(type(c) is int and 0 <= c < len(session.cell_ids) for c in cells)
                  and len(set(cells)) == len(cells), "unique bounded public cell indices")
            _need(self._views < VIEW_BUDGET, "public view budget exhausted")
            image = _svg(session, block, cells)
            self._views += 1
            return {"kind": "svg", "svg": image, "view_number": self._views}
        if kind == "answer":
            _need(set(request) == {"action", "query_id", "ordering_scores"}, "exact answer fields")
            qid, values = request["query_id"], request["ordering_scores"]
            _need(type(qid) is str and qid in self._queries, "known public query")
            _need(qid not in self._answers, "query answer already committed")
            _need(type(values) is list and len(values) == len(self._queries[qid][0].cell_ids),
                  "one score per listed cell")
            scores = tuple(_number(v) for v in values)
            _need(all(0 <= v <= 1 for v in scores), "ordering scores in [0,1]")
            self._answers[qid] = scores
            return {"kind": "accepted", "query_id": qid, "remaining_queries": 28-len(self._answers)}
        if kind == "finish":
            _need(set(request) == {"action"}, "exact finish fields")
            _need(len(self._answers) == 28 and set(self._answers) == set(self._queries),
                  "all 28 query answers must be committed")
            submission = {"schema": "neural035-order-predictions-v1", "predictions": [
                {"query_id": qid, "ordering_scores": list(self._answers[qid])}
                for session in self._observations.sessions for qid, _ in session.queries]}
            raw = (json.dumps(submission, allow_nan=False, separators=(',', ':'))+'\n').encode()
            _need(len(raw) <= SUBMISSION_CAP, "original complete submission cap")
            self._closed = True
            return {"kind": "submission", "submission": raw}
        raise ValueError("unsupported typed action")
