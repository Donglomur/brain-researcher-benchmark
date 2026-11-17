"""Authenticate the fixed Deeprecon published-reference wording successor.

The caller authenticates raw files with its existing bounded reader. This module
checks the accepted parsed identities and projects only the nine approved contract edits
and their current task projection plus three policy locators. It never evaluates scientific data.
"""
from __future__ import annotations

import copy
import hashlib
import json

TASK = 'PAPER-paper-method-029'
HOME = 'benchmarks/paper/' + TASK
REVISION_FILE = 'reference-recovery-successor.v1.json'
CURRENT_FILE = 'improvement.reference-recovery.v1.json'
_SEAL = object()
# _APPROVED is installed below from the fixed reviewed source/adoption pins.

def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def approved_pin(name):
    return copy.deepcopy(_APPROVED[name]['pin'])


def _require_pin(selected, name):
    _need(type(selected) is dict and selected == approved_pin(name), 'Unreviewed Deeprecon ' + name + ' selector')


def has_primary_successor(row):
    _need(row.get('id') == TASK and row.get('track') == 'paper', 'Unexpected Deeprecon successor owner')
    declared = row.get('paper_outcomes')
    if declared is None:
        return False
    _need(type(declared) is dict, 'Deeprecon outcomes must be an object')
    fields = {'primary_policy_revision', 'primary_improvement_contract'}
    if not fields.intersection(declared):
        return False
    _need(fields | {'reproduction_contract'} <= set(declared), 'Incomplete Deeprecon reference selection')
    for field, name in (('primary_policy_revision', 'descriptor'),
                        ('primary_improvement_contract', 'improvement'), ('reproduction_contract', 'reproduction')):
        _require_pin(declared[field], name)
    return True


class _Authenticated:
    __slots__ = ('_payload', '_seal')

    def __init__(self, documents, seal):
        object.__setattr__(self, '_payload', _encode(documents))
        object.__setattr__(self, '_seal', seal)

    def __setattr__(self, name, value):
        raise AttributeError('Authenticated Deeprecon reference is immutable')

    def __delattr__(self, name):
        raise AttributeError('Authenticated Deeprecon reference is immutable')

    def snapshot(self):
        return json.loads(self._payload)

    @property
    def primary_improvement(self):
        return self.snapshot()['improvement']

    @property
    def retained_improvement(self):
        return self.snapshot()['retained_improvement']

    @property
    def descriptor_pin(self):
        return approved_pin('descriptor')

    @property
    def candidate_interface(self):
        return None

    @property
    def author_reproduction_routes(self):
        return None

    @property
    def members(self):
        # Predecessors/reference reports live under docs and keep their existing
        # documentation ownership. Only these two root files need new ownership.
        return [approved_pin('descriptor'), approved_pin('improvement')]

    @property
    def public_provenance(self):
        return {name: approved_pin(key) for name, key in (
            ('published_reference', 'reference'), ('previous_task', 'archived_task.json'),
            ('retained_improvement', 'retained_improvement'), ('previous_outcomes', 'archived_outcomes.v1.json'))}


def authenticate(*, task_id, revision_pin, primary_pin, reproduction_pin, previous_pin,
                 retained_improvement_pin, read_pin):
    _need(task_id == TASK, 'Unexpected Deeprecon successor task')
    for selected, name in ((revision_pin, 'descriptor'), (primary_pin, 'improvement'),
                           (reproduction_pin, 'reproduction'), (previous_pin, 'pre_outcomes'),
                           (retained_improvement_pin, 'retained_improvement')):
        _require_pin(selected, name)
    documents = {}
    for name, expected in _APPROVED.items():
        if name == 'task':
            continue
        value = read_pin(approved_pin(name), 'Deeprecon reference ' + name)
        _need(_digest(value) == expected['canonical'], 'Deeprecon parsed identity mismatch: ' + name)
        documents[name] = value
    descriptor = documents['descriptor']
    _need(descriptor['schema_version'] == 'deeprecon-reference-recovery-successor/v1'
          and descriptor['task_id'] == TASK, 'Invalid Deeprecon reference descriptor')
    _need(documents['improvement']['disposition'] == 'source_unresolved'
          and documents['reproduction']['eligibility'] == 'source_unresolved',
          'Deeprecon source reference cannot qualify either outcome')
    replayed = copy.deepcopy(documents['retained_improvement'])
    changes = descriptor['improvement_replacements']
    _need(len(changes) == 9, 'Deeprecon requires exactly nine accepted contract edits')
    for change in changes:
        _contract_replace(replayed, change)
    _need(replayed == documents['improvement'], 'Deeprecon contract differs beyond accepted wording edits')
    _need(documents['improvement']['same_task'] == documents['retained_improvement']['same_task'],
          'Deeprecon reference recovery cannot change same-task anchors')
    replayed_outcomes = copy.deepcopy(documents['archived_outcomes.v1.json'])
    for change in descriptor['outcome_identity_replacements'] + descriptor['administrative_rationale_replacements']:
        _replace(replayed_outcomes, change)
    _need(replayed_outcomes == documents['outcomes'], 'Deeprecon outcomes differ beyond reviewed binding edits')
    _need(documents['improvement']['source_paper']['url'] == documents['reproduction']['source_paper']['url'],
          'Deeprecon source paper mismatch')
    for anchor in ('dataset', 'cohort', 'target', 'inputs', 'split', 'preprocessing', 'metric', 'aggregation'):
        _need(documents['improvement']['same_task'][anchor]['description'] ==
              documents['reproduction']['same_task'][anchor]['description'], 'Deeprecon anchor mismatch: ' + anchor)
    _need(documents['archived_outcomes.v1.json']['original_task_sha256'] == approved_pin('archived_task.json')['sha256'],
          'Deeprecon predecessor outcome identity mismatch')
    _need(documents['outcomes']['original_task_sha256'] == approved_pin('task')['sha256'],
          'Deeprecon current outcome identity mismatch')
    _need(all(item['protocol'] is None for item in documents['outcomes']['pairing'].values()),
          'Deeprecon reference recovery cannot instantiate paired protocols')
    return _Authenticated(documents, _SEAL)


def _replace(document, change):
    pointer = change['pointer']
    _need(type(pointer) is str and pointer.startswith('/') and '~' not in pointer, 'Invalid Deeprecon replacement pointer')
    parts = pointer[1:].split('/')
    target = document
    for part in parts[:-1]:
        if type(target) is list:
            _need(part.isdigit() and int(part) < len(target), 'Missing Deeprecon replacement parent')
            target = target[int(part)]
        else:
            _need(type(target) is dict and part in target, 'Missing Deeprecon replacement parent')
            target = target[part]
    key = int(parts[-1]) if type(target) is list else parts[-1]
    present = key < len(target) if type(target) is list else key in target
    _need(present == change['before_present'], 'Deeprecon replacement presence mismatch')
    _need(not present or target[key] == change['before'], 'Deeprecon replacement preimage mismatch')
    target[key] = copy.deepcopy(change['after'])


def _contract_replace(document, change):
    _need(change['op'] in ('replace', 'add'), 'Invalid Deeprecon contract edit')
    if change['op'] == 'add':
        _need(change['path'] == '/evidence/7' and len(document['evidence']) == 7,
              'Unexpected Deeprecon evidence addition')
        document['evidence'].append(copy.deepcopy(change['after']))
        return
    _replace(document, {'pointer': change['path'], 'before_present': True,
                        'before': change['before'], 'after': change['after']})


def project(base_dual_task, authenticated):
    _need(type(authenticated) is _Authenticated and authenticated._seal is _SEAL,
          'Authenticated Deeprecon reference required')
    documents = authenticated.snapshot()
    _need(base_dual_task == documents['archived_task.json'],
          'Deeprecon reference requires the exact deterministic predecessor projection')
    result = copy.deepcopy(base_dual_task)
    descriptor = documents['descriptor']
    for change in descriptor['task_replacements'] + descriptor['locator_replacements']:
        _replace(result, change)
    _need(result['episode']['improvement'] == documents['improvement']['episode']
          and result['blocking_issues']['improvement'] == documents['improvement']['blocking_issues']
          and result['holds']['preserved_limits']['task_specific'] == documents['improvement']['blocking_issues'],
          'Deeprecon current instructions must select the reviewed current policy')
    body = _encode(result)
    expected = approved_pin('task')
    _need(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
          'Deeprecon current projection differs from reviewed source-fact and locator edits')
    return result


_APPROVED = {
  "archived_task.json": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/docs/provenance/pre-reference-recovery-20261117/task.json",
      "bytes": 28973,
      "sha256": "70a52fc9f86d15d5046c334b96668eae4983a94ed14aadb0aea07f05e6828f9e"
    },
    "canonical": "f9360955d348a294a04442e46f7e30c4e6b57831decb4beb7ea14e3df6d7719d"
  },
  "archived_outcomes.v1.json": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/docs/provenance/pre-reference-recovery-20261117/outcomes.v1.json",
      "bytes": 1691,
      "sha256": "63b1a7e6bffa0f0ebcee65c34dc8f6d9dc897f322bf30fed32109f408c9b39db"
    },
    "canonical": "d6eb8e1e095902e0b6e13f7bd8816f3ad4c9df52f23c536bd8a466f51376b6b1"
  },
  "retained_improvement": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/improvement.v1.json",
      "bytes": 14354,
      "sha256": "50d522ee645ea86054bde5fb053e72c7a536664174015649c82c57b6c2058717"
    },
    "canonical": "a8f0efcd6d3c31b42347c60fee446d2b9c3cee36ae9e4be71c7c646112464665"
  },
  "pre_outcomes": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/historical/task.pre-outcomes.v1.json",
      "bytes": 29966,
      "sha256": "8deeb7ba501c5c1a6155b4049fc2e4ada289ba6eed31e378f7d0f2cf4dd01dd0"
    },
    "canonical": "3c8ef1fa823dbe45f927a8d01b8522d08e92ae7358387403f739dbb096942cce"
  },
  "improvement": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/improvement.reference-recovery.v1.json",
      "bytes": 16145,
      "sha256": "87181df3a225144d4b39820b3873fb55061bdd566fed57a240b282c0f3b650cd"
    },
    "canonical": "bd6328d829dae7d6ebdbb3820ee91f89613464b7c045e8088d2b012901b2efca"
  },
  "reproduction": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/reproduction.v1.json",
      "bytes": 1251690,
      "sha256": "d9432f48416392bad798461dfabc5d49f60e44b6ce658a9e2127c4c0aca7a602"
    },
    "canonical": "2ff740c0aa95b4885a2f3b39ed036c2ce61cbc5fefce0ae548b6ef23265ab320"
  },
  "task": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/task.json",
      "bytes": 29884,
      "sha256": "bf0a50c891e2654e310ede3e5e322283db064e990d925f54559b58bcc1ca1eeb"
    },
    "canonical": "b642856be87ee133c1d909950b3339181d014c7b111d880efc257cb7f764a704"
  },
  "outcomes": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/outcomes.v1.json",
      "bytes": 1559,
      "sha256": "4ecaa3fe84077ff455079bb817edf5e7defb7a6e529f8bfd8eed6660f5364ecf"
    },
    "canonical": "53efdefec3715fbef026643f6f85bf0aafa3c45f51996fabd336565bcf80b773"
  },
  "reference": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/implementations/published-reference-v1/SOURCE_PROVENANCE.json",
      "bytes": 2154,
      "sha256": "f500b03c515593a21d842dc32d778eb643ce9dc91edeaf35c58893013aff9a38"
    },
    "canonical": "1dd9888e06c9b9451d280c0f8767c6f4ed52b37a27bac490d57f215143eddb8d"
  },
  "descriptor": {
    "pin": {
      "path": "benchmarks/paper/PAPER-paper-method-029/reference-recovery-successor.v1.json",
      "bytes": 20682,
      "sha256": "2e7b690aec9d923929edd4ad60097d5b270b3d03b4c1dbb30b17cd49a00f38cb"
    },
    "canonical": "2546ab3dd0fb610c742b325320cb7d855d24e52a63a458321040dbc13f52c09b"
  }
}
