"""Original full public domains; private failures are retained, never admitted."""
import io
from custody import need, read_pinned, write_exclusive
from source_plan import encode, digest

JSON_CAP = 4_000_000
FEATURE_CAP = 24_000_128


def feature_bytes(np, values, rows, validate_features):
    need(isinstance(values, np.ndarray) and values.shape == (len(rows), 5, 6)
         and values.dtype == np.dtype('<f8') and len(rows) <= 100000, 'complete original feature geometry')
    validate_features(values, rows)
    need(values.nbytes + 128 <= FEATURE_CAP, 'original full feature domain before serialization')
    f = io.BytesIO()
    np.lib.format.write_array(f, values, version=(1, 0), allow_pickle=False)
    raw = f.getvalue()
    need(len(raw) <= FEATURE_CAP, 'original full feature byte cap')
    return raw


def feature_readback(np, raw, n):
    need(len(raw) <= FEATURE_CAP, 'original consumer feature domain')
    f = io.BytesIO(raw)
    need(np.lib.format.read_magic(f) == (1, 0), 'original NPYv1 feature version')
    shape, fortran, dtype = np.lib.format.read_array_header_1_0(f, max_header_size=10000)
    need(shape == (n, 5, 6) and fortran is False and dtype == np.dtype('<f8')
         and len(raw) - f.tell() == n * 240, 'exact original consumer feature envelope')
    f.seek(0); values = np.load(f, allow_pickle=False)
    need(f.tell() == len(raw), 'complete original feature consumer EOF')
    return values


class Publisher:
    def __init__(self, *, np, output_fd, evidence_fd, budget, scientific, people):
        self.np, self.output_fd, self.evidence_fd = np, output_fd, evidence_fd
        self.budget, self.scientific, self.people = budget, scientific, people
        self.parts = []; self.part_bytes = 0

    def checkpoint(self, person, rows, block):
        need(person == self.people[len(self.parts)], 'complete ordered private checkpoints')
        body = feature_bytes(self.np, block, rows, self.scientific['validate_features'])
        self.part_bytes += len(body)
        need(self.part_bytes <= FEATURE_CAP + 33 * 128, 'whole private feature checkpoint cap')
        pin = write_exclusive(self.evidence_fd, person + '.features.npy', body, self.budget, FEATURE_CAP)
        row_raw = encode(rows)
        need(len(row_raw) <= JSON_CAP, 'whole original row JSON domain')
        row_pin = write_exclusive(self.evidence_fd, person + '.rows.json', row_raw, self.budget, JSON_CAP)
        self.parts.append({'participant': person, 'features': pin, 'rows': row_pin})

    def publish(self, rows, blocks, provenance):
        self.budget.check()
        need([v['participant'] for v in self.parts] == list(self.people), 'all33 private checkpoints closed')
        self.scientific['validate_rows'](rows, self.people)
        need(sum(len(v) for v in blocks) == len(rows) and len(blocks) == 33, 'whole original block join')
        values = self.np.concatenate(blocks).astype('<f8')
        feature_raw = feature_bytes(self.np, values, rows, self.scientific['validate_features'])
        packet = {'schema': 'neural098-packet-v1', 'features_sha256': digest(feature_raw), 'rows': rows}
        preparation = {'schema': 'neural098-preparation-v1', 'sources': provenance,
            'scientific_analysis_executed': False,
            'temporal_availability': 'Retrospective author-preprocessed signals; no causal online claim.'}
        bodies = {'features.npy': feature_raw, 'packet.json': encode(packet), 'PREPARATION.json': encode(preparation)}
        need(len(bodies['packet.json']) <= JSON_CAP and len(bodies['PREPARATION.json']) <= JSON_CAP,
             'complete public packet/history must fit unchanged4MB consumer; no row truncation')
        pins = {}
        for name, body in bodies.items():
            pin = write_exclusive(self.output_fd, name, body, self.budget, FEATURE_CAP if name == 'features.npy' else JSON_CAP)
            captured = read_pinned(self.output_fd, pin, self.budget, pin['bytes'])
            need(captured == body, 'closed complete output readback')
            pins[name] = pin
        # Same shape, availability, finite and all-cohort support checks a
        # consumer needs. No scientific reference/model function is loaded.
        checked = feature_readback(self.np, feature_raw, len(rows))
        self.scientific['validate_features'](checked, rows)
        self.scientific['validate_rows'](packet['rows'], self.people)
        self.budget.check()
        return {'outputs': pins, 'rows': len(rows), 'people': len(self.people),
                'complete_support_validated': True, 'checkpoints': self.parts}
