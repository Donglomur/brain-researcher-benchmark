"""Concrete arm-file projection; host sandbox/admission remains a separate gap."""
from dataclasses import dataclass
from .core import Custody, Refusal, read_exact, write_exact, encode_json
from .roster import ACCESS


@dataclass(frozen=True)
class SourceMember:
    role: str
    path: str
    bytes: int
    sha256: str


def prepare_view(plan, arm, input_root_fd, source_root_fd, output_root_fd,
                 source_members, budget, custody):
    """Make an exact fresh view from original selected byte identities.

    SourceMember is an exposure-plan description, not rights/native authority.
    Output root must be fresh and owned upstream. No reference outputs, saved
    matrices, other attempts or private grading material is an admitted role.
    """
    if arm not in ACCESS:
        raise Refusal('only the two original access arms exist')
    expected = {'paper'} | ({'base', 'sound', 'omission', 'postprocessing', 'environment', 'readme'}
                          if arm == 'paper_data_official_code' else set())
    selected = tuple(m for m in source_members if m.role in expected)
    if {m.role for m in selected} != expected or len(selected) != len(expected):
        raise Refusal('exact arm source exposure required')
    local = Custody(custody)
    rows = []
    with local.attempt('arm projection'):
        for member in plan.members:
            raw, capture = read_exact(input_root_fd, member.path, member.bytes, member.sha256, budget, local)
            name = member.participant + '__' + member.condition + '.fif'
            rows.append({'role': 'data', 'input': member.path,
                         **write_exact(output_root_fd, name, raw, budget, local)})
        for member in selected:
            raw, capture = read_exact(source_root_fd, member.path, member.bytes, member.sha256, budget, local)
            rows.append({'role': member.role, 'input': member.path,
                         **write_exact(output_root_fd, 'source_' + member.role + '.txt', raw, budget, local)})
        projected = {'schema': 'FIND032_INPUT_V1', 'release': plan.release,
                     'rights_record': plan.rights_record, 'eligibility_record': plan.eligibility_record,
                     'members': [{'participant': m.participant, 'condition': m.condition,
                                  'path': m.participant + '__' + m.condition + '.fif',
                                  'bytes': m.bytes, 'sha256': m.sha256} for m in plan.members]}
        write_exact(output_root_fd, 'INPUT_MANIFEST.json', encode_json(projected), budget, local)
        result = {'arm': arm, 'input_manifest': plan.manifest_sha256, 'members': rows,
                  'isolation_qualified': False, 'source_rights_qualified': False,
                  'known_public_paper_results': True, 'reference_answers_in_view': False}
        write_exact(output_root_fd, 'ACCESS_VIEW.json', encode_json(result), budget, local)
    return result
