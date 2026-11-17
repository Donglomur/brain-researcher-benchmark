"""Immutable map values and exact support joins, without pretending to issue data."""
from dataclasses import dataclass
import hashlib
from .contracts import require


@dataclass(frozen=True)
class MapValue:
    source_identity: str
    support_identity: str
    values: bytes
    length: int
    sha256: str

    def array(self, expected_source, expected_support, maximum_bytes):
        import numpy as np
        require(self.source_identity == expected_source, 'Map source identity mismatch')
        require(self.support_identity == expected_support, 'Map spatial support mismatch')
        require(type(self.length) is int and self.length > 1, 'Invalid map length')
        require(type(self.values) is bytes and len(self.values) == 8 * self.length <= maximum_bytes, 'Map byte extent mismatch')
        require(hashlib.sha256(self.values).hexdigest() == self.sha256, 'Map value identity mismatch')
        a = np.frombuffer(self.values, dtype='<f8')
        require(np.isfinite(a).all(), 'Nonfinite map values')
        return a


def read_training(reader, population, fold, support_identity, maximum_map_bytes):
    """Only declared training keys reach the reader; a candidate receives arrays, not reader access.

    Reader provenance, native isolation and genuine protected-input issuance are
    external qualification requirements. A user-supplied reader is not that proof.
    """
    import numpy as np
    require(fold.eligible, 'Ineligible training/query support')
    cases = {(c.person, c.endpoint): c for c in population.cases}
    rows, width = [], None
    for person in fold.training_people:
        person_rows = []
        for endpoint in fold.training_endpoints:
            c = cases[person, endpoint]
            require(c.status == 'present', 'Nonpresent training case')
            value = reader.read_training_map(person, endpoint, c.source_identity)
            require(isinstance(value, MapValue), 'Reader did not return an immutable map envelope')
            a = value.array(c.source_identity, support_identity, maximum_map_bytes)
            width = len(a) if width is None else width
            require(len(a) == width, 'Training maps disagree on spatial extent')
            person_rows.append(a)
        rows.append(np.stack(person_rows, axis=0))
    return np.stack(rows, axis=0)


def freeze_prediction(person, endpoint, arm, array, support_identity, maximum_map_bytes):
    import numpy as np
    a = np.asarray(array, dtype='<f8')
    require(a.ndim == 1 and len(a) > 1 and np.isfinite(a).all(), 'Invalid prediction map')
    require(a.nbytes <= maximum_map_bytes, 'Prediction exceeds declared retained-map bound')
    data = a.tobytes(order='C')
    identity = 'P1:' + person + ':' + endpoint + ':' + arm
    return MapValue(identity, support_identity, data, len(a), hashlib.sha256(data).hexdigest())
