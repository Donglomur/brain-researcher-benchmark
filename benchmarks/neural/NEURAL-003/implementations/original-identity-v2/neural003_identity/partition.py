"""Whole-person folds retaining original block identity and instruction binding.

An original identity is (person, session, block, trial). Instruction is bound
metadata, not an additional trial: conflicting metadata cannot create a new row.
The caller must supply the authentic join; these functions do not discover it.
"""
from dataclasses import dataclass

PEOPLE = tuple(range(26))
MAX_TRIALS_PER_PERSON = 20000


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


def identity(row):
    """Validate and return all four original source-identity fields."""
    if type(row) is not Trial or type(row.person) is not int or row.person not in PEOPLE:
        raise ValueError("exact trial/person type")
    for value in (row.session, row.block, row.trial):
        _text(value)
    if type(row.instruction) is not str or row.instruction not in ("speed", "accuracy"):
        raise ValueError("instruction")
    return (row.person, row.session, row.block, row.trial)


def _group(rows):
    rows = tuple(rows)
    if not rows or len(rows) > len(PEOPLE) * MAX_TRIALS_PER_PERSON:
        raise ValueError("trial roster extent")
    by_person = {person: [] for person in PEOPLE}
    identities, blocks = set(), {}
    for row in rows:
        key = identity(row)
        if key in identities:
            raise ValueError("duplicate original trial, including conflicting metadata")
        identities.add(key)
        block = key[:3]
        if blocks.setdefault(block, row.instruction) != row.instruction:
            raise ValueError("source block crosses instruction; resolve original join")
        by_person[row.person].append(row)
        if len(by_person[row.person]) > MAX_TRIALS_PER_PERSON:
            raise ValueError("per-person trial roster extent")
    if any(not by_person[person] for person in PEOPLE):
        raise ValueError("all 26 original people required")
    return {person: tuple(sorted(values, key=identity))
            for person, values in by_person.items()}


def _one_fold(by_person, held):
    training_people = tuple(person for person in PEOPLE if person != held)
    training = tuple(row for person in training_people for row in by_person[person])
    inner = tuple(
        (validation,
         tuple(row for person in training_people if person != validation
               for row in by_person[person]),
         by_person[validation])
        for validation in training_people
    )
    return Fold(held, training, by_person[held], inner)


def compile_splits(rows):
    """Compile all 26 outer folds and all 25 inner-person folds per outer fold.

Every roster entry retains its complete immutable Trial. No labels/signals enter
planning; no block, trial identifier, or instruction is inferred from row order.
"""
    by_person = _group(rows)
    return tuple(_one_fold(by_person, held) for held in PEOPLE)


def validate_fold(fold):
    """Reject changed metadata, partial inner folds and noncanonical membership.

This checks internal consistency, not authenticity of the supplied source join.
Validation precedes fitting; callers cannot bypass it by constructing Fold directly.
"""
    if (type(fold) is not Fold or type(fold.held_person) is not int
            or fold.held_person not in PEOPLE
            or type(fold.training) is not tuple or type(fold.query) is not tuple
            or type(fold.inner) is not tuple):
        raise ValueError("compiled fold")
    by_person = _group(fold.training + fold.query)
    for entry in fold.inner:
        if (type(entry) is not tuple or len(entry) != 3 or type(entry[0]) is not int
                or type(entry[1]) is not tuple or type(entry[2]) is not tuple):
            raise ValueError("typed inner-person fold")
        for row in entry[1] + entry[2]:
            identity(row)
    if fold != _one_fold(by_person, fold.held_person):
        raise ValueError("complete canonical whole-person fold and metadata binding")
    return fold


def block_members(rows):
    """Private audit table; original group names are not prediction features."""
    by_person = _group(rows)
    out = {}
    for values in by_person.values():
        for row in values:
            out.setdefault((row.person, row.session, row.block, row.instruction), []).append(row.trial)
    return tuple((key, tuple(sorted(values))) for key, values in sorted(out.items()))
