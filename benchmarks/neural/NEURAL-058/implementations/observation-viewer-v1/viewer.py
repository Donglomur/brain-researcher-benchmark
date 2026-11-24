"""Host-side typed, exact numeric observation pages for admitted NEURAL-058 views.

SVG is host transport: render to an image before participant delivery. This module
is not a sandbox, target grader, authenticity verifier or model/provider client.
"""
from html import escape
import math
import json
from numbers import Integral, Real
import re

OPAQUE = re.compile(r'[0-9a-f]{32}\Z')
COMMON_TABLES = ('context', 'timestamps', 'anatomy')
NEURAL_TABLES = ('spikes', 'domain')
CONTEXT = ('stimulus_side', 'stimulus_contrast', 'block_prior')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, minimum=0):
    need(type(value) is int and value >= minimum, 'ordinary integer required')
    return value


def alias(value):
    need(type(value) is str and OPAQUE.fullmatch(value), 'opaque prepared alias required')
    return value


def number(value):
    need(isinstance(value, Real) and not isinstance(value, bool), 'real numeric observation required')
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError('observation outside finite binary64 range') from error
    need(math.isfinite(result), 'finite observation required')
    return result


def display(value):
    # repr(float) is the shortest round-trip decimal, not a lossy plot rounding.
    return 'MISSING' if value is None else repr(value) if type(value) is float else str(value)


def sequence(value):
    need(not isinstance(value, (str, bytes, dict)), 'numeric sequence required')
    try:
        return list(value)
    except TypeError as error:
        raise ValueError('sequence required') from error


class EvaluationViewer:
    """One role and condition, containing the complete 29-session evaluation set.

    sessions are the trusted corpus.load_session(..., role, training=False)
    results. required is the independently admitted ordered evaluation roster,
    each row containing session, animal, session_ordinal and animal_ordinal.
    Neither inputs nor instances may be mounted in the participant process.
    """
    def __init__(self, sessions, required, *, role, page_rows, max_cells,
                 max_actions, max_svg_bytes):
        need(role in ('C', 'J'), 'explicit context/neural role required')
        self.role = role
        self.page_rows = integer(page_rows, 1)
        need(self.page_rows <= 32, 'at most 32 readable rows per rendered page')
        self.max_cells = integer(max_cells, 1)
        self.max_actions = integer(max_actions, 1)
        self.max_svg_bytes = integer(max_svg_bytes, 1)
        self.actions = self.svg_bytes = self.cells = 0
        self._pages_seen = set()
        self._tables = {}
        self._targets = {}
        self._identity = {}
        self._catalog = []
        required = list(required)
        sessions = list(sessions)
        need(len(required) == len(sessions) == 29, 'all 29 evaluation sessions required')
        need(len({r['animal'] for r in required}) == 13, 'all 13 evaluation animals required')
        animal_ordinals = {}
        for ordinal, (session, expected) in enumerate(zip(sessions, required)):
            need(set(expected) == {'session', 'animal', 'session_ordinal', 'animal_ordinal'},
                 'exact independently admitted roster fields')
            sid, animal = alias(expected['session']), alias(expected['animal'])
            need(integer(expected['session_ordinal']) == ordinal, 'complete source-owned session order')
            ao = integer(expected['animal_ordinal'])
            need(animal not in animal_ordinals or animal_ordinals[animal] == ao, 'stable animal ordinal')
            animal_ordinals[animal] = ao
            need(all(session[k] == expected[k] for k in expected), 'exact prepared evaluation roster')
            need(session['role'] == role and session['fold'] is None, 'evaluation-only matched projection')
            need(set(session) == {'session', 'animal', 'session_ordinal', 'animal_ordinal', 'fold',
                                 'regions', 'locations', 'location_missing', 'windows', 'source_view', 'role'},
                 'exact loaded evaluation fields; no labels or target joins')
            need(sid not in self._targets, 'unique evaluation sessions')
            self._targets[sid] = {}
            self._identity[sid] = dict(expected)
            anatomy = self._anatomy(session)
            windows = sequence(session['windows'])
            need(windows, 'no omitted or empty required session')
            seen_queries = set()
            for window in windows:
                query = alias(window['query'])
                need(query not in seen_queries, 'unique original window occurrences')
                seen_queries.add(query)
                self._window(sid, query, window, anatomy)
        need(sorted(animal_ordinals.values()) == list(range(13)), 'complete unique animal ordinals')
        self._required = tuple((r['session'], r['animal']) for r in required)

    def _rows(self, rows):
        result = []
        for row in rows:
            self.cells += len(row)
            need(self.cells <= self.max_cells, 'complete observations exceed selected cell allowance')
            rendered = tuple(display(value) for value in row)
            need(all(len(text) <= 180 and all(ord(c) >= 32 for c in text) for text in rendered),
                 'observation text must fit complete readable page; no truncation')
            result.append(rendered)
        return tuple(result)

    def _anatomy(self, session):
        regions = sequence(session['regions'])
        locations, missing = sequence(session['locations']), sequence(session['location_missing'])
        need(regions and len(regions) == len(locations) == len(missing), 'complete anatomical unit axis')
        rows = []
        for unit, (region, xyz, absent) in enumerate(zip(regions, locations, missing)):
            need(type(region) is str and region, 'original anatomical region required')
            xyz, absent = sequence(xyz), sequence(absent)
            need(len(xyz) == len(absent) == 3, 'three complete coordinates and masks')
            # The loaded primitive bool array may contain numpy.bool_ scalars.
            need(all(type(flag) is bool or (getattr(getattr(flag, 'dtype', None), 'kind', None) == 'b'
                                          and getattr(flag, 'ndim', None) == 0) for flag in absent),
                 'explicit coordinate missingness mask')
            rows.append((unit, region, *(number(v) for v in xyz), *(bool(v) for v in absent)))
        return self._rows(rows)

    def _window(self, sid, query, window, anatomy):
        expected = {'query', 'context', 'support', 'locations', 'location_missing', 'regions', 'times'}
        if self.role == 'J':
            expected |= {'spike_times', 'spike_units', 'neural_domain'}
        need(set(window) == expected, 'exact permitted window fields; no target values or joins')
        # Window anatomy is a repeated reference in corpus.load_session. Confirm
        # it agrees rather than silently discarding a contradictory copy.
        repeated = self._anatomy(window)
        need(repeated == anatomy, 'window/session anatomical agreement')
        context = sequence(window['context'])
        support = tuple(number(v) for v in sequence(window['support']))
        need(len(context) == 3 and len(support) == 2 and 0 <= support[0] < support[1] <= 1,
             'complete permitted context and onset-relative support')
        rows = [(name, None if value is None else number(value)) for name, value in zip(CONTEXT, context)]
        rows.extend((('support_start_seconds', support[0]), ('support_stop_exclusive_seconds', support[1])))
        tables = {'context': self._rows(rows), 'anatomy': anatomy}
        times = tuple(number(v) for v in sequence(window['times']))
        need(times and all(support[0] <= t < support[1] for t in times)
             and all(a < b for a, b in zip(times, times[1:])), 'complete ordered target timestamp support')
        tables['timestamps'] = self._rows((i, t) for i, t in enumerate(times))
        self._targets[sid][query] = len(times)
        if self.role == 'J':
            domains = [tuple(number(v) for v in sequence(row)) for row in sequence(window['neural_domain'])]
            need(domains and all(len(row) == 2 and row[0] < row[1] for row in domains)
                 and all(a[1] <= b[0] for a, b in zip(domains, domains[1:])), 'complete disjoint neural domain')
            tables['domain'] = self._rows((i, *row) for i, row in enumerate(domains))
            spike_times, units = sequence(window['spike_times']), sequence(window['spike_units'])
            need(len(spike_times) == len(units), 'all event times have original units')
            events = []
            previous = -math.inf
            for i, (time, unit) in enumerate(zip(spike_times, units)):
                time = number(time)
                need(isinstance(unit, Integral) and not isinstance(unit, bool)
                     and 0 <= unit < len(anatomy), 'original unit membership')
                need(previous <= time and support[0] <= time < support[1]
                     and any(a <= time < b for a, b in domains), 'ordered complete event/domain membership')
                previous = time
                events.append((i, time, int(unit)))
            tables['spikes'] = self._rows(events)
        for kind in COMMON_TABLES + (NEURAL_TABLES if self.role == 'J' else ()):
            data = tables[kind]
            pages = max(1, (len(data) + self.page_rows - 1) // self.page_rows)
            self._tables[(sid, query, kind)] = data
            self._catalog.append({**self._identity[sid], 'query': query, 'table': kind,
                                  'rows': len(data), 'pages': pages})

    def catalog(self):
        """Safe navigation metadata; no filesystem locators or source identities."""
        return [dict(row) for row in self._catalog]

    def view(self, action):
        """Only page selection is accepted. Host renders the returned SVG image."""
        self.actions += 1
        need(self.actions <= self.max_actions, 'selected viewer action budget exhausted')
        need(type(action) is dict and set(action) == {'session', 'query', 'table', 'page'},
             'only exact typed page action accepted')
        key = (action['session'], action['query'], action['table'])
        need(all(type(value) is str for value in key) and key in self._tables, 'permitted observation page')
        page = integer(action['page'])
        rows = self._tables[key]
        pages = max(1, (len(rows) + self.page_rows - 1) // self.page_rows)
        need(page < pages, 'page outside complete support')
        start = page * self.page_rows
        selected = rows[start:start + self.page_rows]
        heading = f'{key[2]} | page {page + 1}/{pages} | original rows {start}:{start + len(selected)} of {len(rows)}'
        lines = [heading, self._columns(key[2]), *(' | '.join(row) for row in selected)]
        if not rows:
            lines.append('EMPTY: zero original events; complete support retained')
        # Width grows rather than clipping long anatomical names or decimals.
        width = max(760, max(len(line) for line in lines) * 9 + 32)
        height = 32 + 24 * len(lines)
        need(width <= 4096 and height <= 848, 'complete page exceeds readable dimensions; no clipping')
        body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="white"/>']
        for i, line in enumerate(lines):
            body.append(f'<text x="16" y="{24 + i * 24}" font-family="monospace" font-size="14" fill="black" textLength="{len(line) * 9}" lengthAdjust="spacingAndGlyphs">{escape(line)}</text>')
        body.append('</svg>')
        svg = '\n'.join(body)
        count = len(svg.encode('utf-8'))
        need(self.svg_bytes + count <= self.max_svg_bytes, 'selected rendered-output byte budget exhausted')
        self.svg_bytes += count
        self._pages_seen.add((*key, page))
        return svg

    @staticmethod
    def _columns(kind):
        return {'context': 'permitted field | value', 'timestamps': 'sample index | seconds from window onset',
                'anatomy': 'unit index | region | x | y | z | x missing | y missing | z missing',
                'spikes': 'original event index | seconds from window onset | unit index',
                'domain': 'interval index | start seconds | stop exclusive seconds'}[kind]

    def coverage(self):
        """Operator evidence of returned pages; never proof of participant attention."""
        total = sum(row['pages'] for row in self._catalog)
        return {'sessions': len(self._targets), 'animals': len({a for _, a in self._required}),
                'windows': sum(len(w) for w in self._targets.values()),
                'timestamps': sum(n for w in self._targets.values() for n in w.values()),
                'required_pages': total, 'returned_pages': len(self._pages_seen),
                'complete_delivery': len(self._pages_seen) == total,
                'actions': self.actions, 'svg_bytes': self.svg_bytes,
                'limits': {'max_actions': self.max_actions, 'max_svg_bytes': self.max_svg_bytes,
                           'page_rows': self.page_rows, 'max_cells': self.max_cells}}

    def validate_response(self, predictions):
        """Host-side shape/finite check, with no target values and no score.

        Required structure: session -> query -> [[signed_velocity, speed], ...].
        Both heads keep every timestamp. Negative predictions are not clipped.
        """
        need(type(predictions) is dict and set(predictions) == set(self._targets), 'all evaluation sessions exactly once')
        clean = {}
        for sid, windows in self._targets.items():
            proposed = predictions[sid]
            need(type(proposed) is dict and set(proposed) == set(windows), 'all original query occurrences exactly once')
            clean[sid] = {}
            for query, count in windows.items():
                rows = sequence(proposed[query])
                need(len(rows) == count, 'all original timestamps required')
                result = []
                for row in rows:
                    row = sequence(row)
                    need(len(row) == 2, 'signed velocity and separate speed head required')
                    result.append([number(value) for value in row])
                clean[sid][query] = result
        return clean


def parse_response(body, *, max_bytes):
    """Decode a bounded UTF-8 response before EvaluationViewer.validate_response.

    Duplicate keys at any level and nonfinite JSON constants are rejected. The
    byte limit is selected before receiving a participant response.
    """
    need(type(body) is bytes and len(body) <= integer(max_bytes, 1), 'bounded response bytes required')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate response key')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError('nonfinite response literal')
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
    except (UnicodeError, RecursionError) as error:
        raise ValueError('invalid response encoding or nesting') from error
