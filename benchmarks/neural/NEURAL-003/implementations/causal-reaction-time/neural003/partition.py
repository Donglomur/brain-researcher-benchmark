"""Original-person and original-block partitions. No labels or signals enter planning."""
from dataclasses import dataclass

PEOPLE = tuple(range(26))

@dataclass(frozen=True)
class Trial:
    person: int
    session: str
    block: str
    trial: str
    instruction: str

@dataclass(frozen=True)
class Fold:
    held_person: int
    training: tuple
    query: tuple
    inner: tuple

def _text(value):
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError("original identity must be a bounded nonempty string")
    return value

def compile_splits(rows):
    """Requires original joined identities; never derives blocks from row numbers."""
    rows = tuple(rows)
    if not rows or len(rows) > 26 * 20000:
        raise ValueError("trial roster extent")
    by_person = {p: [] for p in PEOPLE}
    identities = set()
    blocks = {}
    for row in rows:
        if type(row) is not Trial or type(row.person) is not int or row.person not in PEOPLE:
            raise ValueError("exact trial/person type")
        for value in (row.session, row.block, row.trial):
            _text(value)
        if row.instruction not in ("speed", "accuracy"):
            raise ValueError("instruction")
        key = (row.person, row.session, row.trial)
        if key in identities:
            raise ValueError("duplicate original trial")
        identities.add(key)
        block = (row.person, row.session, row.block)
        prior = blocks.setdefault(block, row.instruction)
        if prior != row.instruction:
            raise ValueError("source block crosses instruction; resolve original join")
        by_person[row.person].append(key)
    if any(not by_person[p] for p in PEOPLE):
        raise ValueError("all 26 original people required")
    by_person = {p: tuple(sorted(keys)) for p, keys in by_person.items()}
    folds = []
    for held in PEOPLE:
        training_people = tuple(p for p in PEOPLE if p != held)
        training = tuple(k for p in training_people for k in by_person[p])
        inner = tuple(
            (validation,
             tuple(k for p in training_people if p != validation for k in by_person[p]),
             by_person[validation])
            for validation in training_people
        )
        folds.append(Fold(held, training, by_person[held], inner))
    return tuple(folds)

def block_members(rows):
    """Private audit table; original block/session names never enter public predictors."""
    out = {}
    for r in rows:
        out.setdefault((r.person, r.session, r.block, r.instruction), []).append(r.trial)
    return tuple((k, tuple(sorted(v))) for k, v in sorted(out.items()))
