"""Complete declared input membership and real byte capture, without data access on import."""
from dataclasses import dataclass
import hashlib
import json
import re
from .core import Refusal, read_exact, relative_name
from .roster import PARTICIPANTS, CONDITIONS


@dataclass(frozen=True)
class InputMember:
    participant: str
    condition: str
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class InputPlan:
    members: tuple
    manifest_sha256: str
    release: str
    rights_record: str
    eligibility_record: str


def parse_input_manifest(raw):
    value = json.loads(raw)
    if set(value) != {'schema', 'release', 'rights_record', 'eligibility_record', 'members'}:
        raise Refusal('exact input manifest fields required')
    if value['schema'] != 'FIND032_INPUT_V1' or value['release'] != '10.5281/zenodo.3268713':
        raise Refusal('release/schema mismatch')
    for name in ('rights_record', 'eligibility_record'):
        if type(value[name]) is not str or not value[name].strip():
            raise Refusal('actual upstream rights/eligibility record must be identified')
    rows = []
    for row in value['members']:
        if set(row) != {'participant', 'condition', 'path', 'bytes', 'sha256'}:
            raise Refusal('exact input member fields required')
        if type(row['bytes']) is not int or row['bytes'] <= 0:
            raise Refusal('input byte extent')
        if type(row['sha256']) is not str or re.fullmatch('[0-9a-f]{64}', row['sha256']) is None:
            raise Refusal('original complete-file sha256 must be selected upstream')
        relative_name(row['path'])
        rows.append(InputMember(**row))
    expected = {(s, c) for s in PARTICIPANTS for c in CONDITIONS}
    actual = {(x.participant, x.condition) for x in rows}
    if len(rows) != len(expected) or actual != expected or len({x.path for x in rows}) != len(rows):
        raise Refusal('all 33 declared participants and four distinct recordings required')
    lookup = {(x.participant, x.condition): x for x in rows}
    ordered = tuple(lookup[s, c] for s in PARTICIPANTS for c in CONDITIONS)
    return InputPlan(ordered, hashlib.sha256(raw).hexdigest(), value['release'],
                     value['rights_record'], value['eligibility_record'])


def capture_recording(plan, participant, condition, root_fd, budget, custody):
    if type(plan) is not InputPlan:
        raise Refusal('input plan type')
    selected = [x for x in plan.members if (x.participant, x.condition) == (participant, condition)]
    if len(selected) != 1:
        raise Refusal('unselected participant/condition')
    member = selected[0]
    raw, captured = read_exact(root_fd, member.path, member.bytes, member.sha256, budget, custody)
    return raw, captured


def assert_scientific_metadata(raw):
    """Called only on the actual MNE object in a future admitted scientific run."""
    if float(raw.info['sfreq']) != 100.0:
        raise Refusal('selected release is the 100 Hz downsampled recording')
    if raw.n_times <= 0 or not raw.ch_names or len(set(raw.ch_names)) != len(raw.ch_names):
        raise Refusal('empty/ambiguous actual recording axes')
    # A file name, this shape check, or the two upstream record strings is not
    # an issuer of scientific eligibility, redistribution, or native execution.

