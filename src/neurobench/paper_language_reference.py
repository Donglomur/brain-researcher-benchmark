"""Authenticate the fixed LANGUAGE author-array reference successor.

The caller authenticates raw files with its existing bounded reader. This module
checks the accepted parsed identities and projects only the reviewed source-fact
updates plus three current-policy locators. It never evaluates scientific data.
"""
from __future__ import annotations

import copy
import hashlib
import json

TASK = 'PAPER-ROOT-ADD-001'
HOME = 'benchmarks/paper/' + TASK
REVISION_FILE = 'reference-successor.v1.json'
CURRENT_FILE = 'improvement.reference.v1.json'
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
    _need(type(selected) is dict and selected == approved_pin(name), 'Unreviewed LANGUAGE ' + name + ' selector')


def has_primary_successor(row):
    _need(row.get('id') == TASK and row.get('track') == 'paper', 'Unexpected LANGUAGE successor owner')
    declared = row.get('paper_outcomes')
    if declared is None:
        return False
    _need(type(declared) is dict, 'LANGUAGE outcomes must be an object')
    fields = {'primary_policy_revision', 'primary_improvement_contract'}
    if not fields.intersection(declared):
        return False
    _need(fields | {'reproduction_contract'} <= set(declared), 'Incomplete LANGUAGE reference selection')
    if declared['primary_policy_revision'] == figure3b_pin('descriptor'):
        for field, name in (('primary_policy_revision', 'descriptor'), ('primary_improvement_contract', 'improvement')):
            _need(declared[field] == figure3b_pin(name), 'Unreviewed LANGUAGE Figure3b selector')
        _require_pin(declared['reproduction_contract'], 'reproduction')
        return True
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
        raise AttributeError('Authenticated LANGUAGE reference is immutable')

    def __delattr__(self, name):
        raise AttributeError('Authenticated LANGUAGE reference is immutable')

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
            ('scope_decision', 'scope'), ('provided_reference', 'reference'), ('reference_receipt', 'receipt'),
            ('previous_task', 'archived_task.json'), ('previous_reproduction', 'archived_reproduction.v2.json'),
            ('previous_improvement', 'archived_improvement.v1.json'), ('previous_outcomes', 'archived_outcomes.v1.json'))}


def authenticate(*, task_id, revision_pin, primary_pin, reproduction_pin, previous_pin,
                 retained_improvement_pin, read_pin):
    if revision_pin == figure3b_pin('descriptor'):
        return _authenticate_figure3b(task_id=task_id, revision_pin=revision_pin, primary_pin=primary_pin, reproduction_pin=reproduction_pin, previous_pin=previous_pin, retained_improvement_pin=retained_improvement_pin, read_pin=read_pin)
    _need(task_id == TASK, 'Unexpected LANGUAGE successor task')
    for selected, name in ((revision_pin, 'descriptor'), (primary_pin, 'improvement'),
                           (reproduction_pin, 'reproduction'), (previous_pin, 'pre_outcomes'),
                           (retained_improvement_pin, 'retained_improvement')):
        _require_pin(selected, name)
    documents = {}
    for name, expected in _APPROVED.items():
        if name == 'task':
            continue
        value = read_pin(approved_pin(name), 'LANGUAGE reference ' + name)
        _need(_digest(value) == expected['canonical'], 'LANGUAGE parsed identity mismatch: ' + name)
        documents[name] = value
    descriptor = documents['descriptor']
    _need(descriptor['schema_version'] == 'language-current-reference-successor/v1'
          and descriptor['task_id'] == TASK, 'Invalid LANGUAGE reference descriptor')
    _need(documents['archived_improvement.v1.json'] == documents['retained_improvement'],
          'LANGUAGE retained improvement lineage differs')
    _need(documents['improvement']['disposition'] == 'design_ready'
          and documents['reproduction']['eligibility'] == 'source_unresolved',
          'LANGUAGE source reference cannot qualify either outcome')
    _need(documents['improvement']['source_paper']['url'] == documents['reproduction']['source_paper']['url'],
          'LANGUAGE source paper mismatch')
    for anchor in ('dataset', 'cohort', 'target', 'inputs', 'split', 'preprocessing', 'metric', 'aggregation'):
        _need(documents['improvement']['same_task'][anchor]['description'] ==
              documents['reproduction']['same_task'][anchor]['description'], 'LANGUAGE anchor mismatch: ' + anchor)
    _need(documents['archived_outcomes.v1.json']['original_task_sha256'] == approved_pin('archived_task.json')['sha256'],
          'LANGUAGE predecessor outcome identity mismatch')
    _need(documents['outcomes']['original_task_sha256'] == approved_pin('task')['sha256'],
          'LANGUAGE current outcome identity mismatch')
    _need(all(item['protocol'] is None for item in documents['outcomes']['pairing'].values()),
          'LANGUAGE reference recovery cannot instantiate paired protocols')
    return _Authenticated(documents, _SEAL)


def _replace(document, change):
    pointer = change['pointer']
    _need(type(pointer) is str and pointer.startswith('/') and '~' not in pointer, 'Invalid LANGUAGE replacement pointer')
    parts = pointer[1:].split('/')
    target = document
    for part in parts[:-1]:
        if type(target) is list:
            _need(part.isdigit() and int(part) < len(target), 'Missing LANGUAGE replacement parent')
            target = target[int(part)]
        else:
            _need(type(target) is dict and part in target, 'Missing LANGUAGE replacement parent')
            target = target[part]
    key = int(parts[-1]) if type(target) is list else parts[-1]
    present = key < len(target) if type(target) is list else key in target
    _need(present == change['before_present'], 'LANGUAGE replacement presence mismatch')
    _need(not present or target[key] == change['before'], 'LANGUAGE replacement preimage mismatch')
    target[key] = copy.deepcopy(change['after'])


def project(base_dual_task, authenticated):
    if type(authenticated) is _Figure3bAuthenticated:
        return _project_figure3b(base_dual_task, authenticated)
    _need(type(authenticated) is _Authenticated and authenticated._seal is _SEAL,
          'Authenticated LANGUAGE reference required')
    documents = authenticated.snapshot()
    _need(base_dual_task == documents['archived_task.json'],
          'LANGUAGE reference requires the exact deterministic predecessor projection')
    result = copy.deepcopy(base_dual_task)
    descriptor = documents['descriptor']
    for change in descriptor['task_replacements']:
        _replace(result, change)
    accepted = descriptor['accepted_semantic_documents']['task.json']
    body = _encode(result)
    _need(len(body) == accepted['bytes'] and hashlib.sha256(body).hexdigest() == accepted['sha256'],
          'LANGUAGE semantic projection differs from root-adopted proposal')
    for change in descriptor['locator_replacements']:
        _replace(result, change)
    body = _encode(result)
    expected = approved_pin('task')
    _need(len(body) == expected['bytes'] and hashlib.sha256(body).hexdigest() == expected['sha256'],
          'LANGUAGE current locators differ from reviewed mechanical projection')
    return result


_APPROVED = {
  "archived_task.json": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/current-definition-pre-reference-20261117/task.json",
      "bytes": 27626,
      "sha256": "2213beed3a83ad5d49a54844db0d024741b61d3a7b53f0b2be08b8739d50616f"
    },
    "canonical": "8f06d03eb310cde5d35636eb5cf33e049e87ffae7e3fae5fe81d17d8288c7554"
  },
  "archived_reproduction.v2.json": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/current-definition-pre-reference-20261117/reproduction.v2.json",
      "bytes": 400592,
      "sha256": "1709e85de608f3eddf597fc4bf371780c32a3779bcefcf7ced9aa43a2dd31c75"
    },
    "canonical": "957fe205147fab3a8fc0cb630a573344d9c5c7602c70f7e74bc7f6ae55e3c72d"
  },
  "archived_improvement.v1.json": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/current-definition-pre-reference-20261117/improvement.v1.json",
      "bytes": 11903,
      "sha256": "58a45ef025115d17e07bf7c0600ccfac2c3948463af3f083009ff9a15ac13b9b"
    },
    "canonical": "5b27f414eb22f26b21fce917eca64ee2b0767037afba0e47f74c27ac48925f49"
  },
  "archived_outcomes.v1.json": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/current-definition-pre-reference-20261117/outcomes.v1.json",
      "bytes": 2160,
      "sha256": "edebf4e17f8d7d1aeb91c0802834eff81e546902070f5a7d132ab1acb31e7f83"
    },
    "canonical": "e3da0650889aeb91d806202cfd867ba4d89bfe7b56b316e75ab6ee0197a630e4"
  },
  "retained_improvement": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/improvement.v1.json",
      "bytes": 11903,
      "sha256": "58a45ef025115d17e07bf7c0600ccfac2c3948463af3f083009ff9a15ac13b9b"
    },
    "canonical": "5b27f414eb22f26b21fce917eca64ee2b0767037afba0e47f74c27ac48925f49"
  },
  "pre_outcomes": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/historical/task.pre-outcomes.v1.json",
      "bytes": 21301,
      "sha256": "830df89d0b6c2e206db15b9025f357f942b6084fcd13008d583dd5ef1b066f42"
    },
    "canonical": "46d01d6f1b7eff94fa791d3142ae6d5a3c488350050b4422cd7f37a4e071a7ba"
  },
  "improvement": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/improvement.reference.v1.json",
      "bytes": 16054,
      "sha256": "c9b3201bafdad76018a1553c822c686c0c06035db9e91ec82d799d20ffd97fa7"
    },
    "canonical": "1af8b6c2f545c08f2e281c01d92f3fac9d22a31dad207b979a964c88818162dc"
  },
  "reproduction": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/reproduction.v2.json",
      "bytes": 484183,
      "sha256": "a54119dd20b84008064ea4f16956b61c2ecbc1926f48987f23f2fe24690406d1"
    },
    "canonical": "0c87c41d35804ccfdea5562b1d50766d3b8a84a067429e7ce2ec477953ac938c"
  },
  "task": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/task.json",
      "bytes": 31718,
      "sha256": "5c4e1af6794f068015c5750e2d99e1560b35f04cb472c56446f01c884a237029"
    },
    "canonical": "ebdb3965539591eb489c3d6d3a13650e03d69cba549dfceb3c90dbf510f0a895"
  },
  "outcomes": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/outcomes.v1.json",
      "bytes": 2579,
      "sha256": "b357dfcf0f0bf086cfa06e4f2373d5e0748981b20f71af7fe615b5d3d79ebb00"
    },
    "canonical": "871ba4890f193dc660b2a5634a37ad80a72d78f4915bdc20715436ed0a3710df"
  },
  "receipt": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/original-reference-20261117/RECEIPT.json",
      "bytes": 16051,
      "sha256": "2d8a98f82cf860c74877bfa870f918eb9cac88352b6a23e8015c56d46c5c5273"
    },
    "canonical": "afbe1c16266eccadc21fbf6afc0ff25f46272249162c1be924556de6405de764"
  },
  "reference": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/original-reference-20261117/REFERENCE.json",
      "bytes": 485111,
      "sha256": "d822f284c2d781f920841705a63fec38d3267ee5c62e5dd5635272cf087e49c9"
    },
    "canonical": "9580c7b4879c741a2fbb1973b1b92542f052f92b4b9bbe32122c412d230d505f"
  },
  "scope": {
    "pin": {
      "path": "docs/provenance/paper-outcome-scope-decisions.v1.json",
      "bytes": 523962,
      "sha256": "e71fe3e869e8f48ffcf18d8e685b86f30027e8eb1dde8ce676ac1948c1943aea"
    },
    "canonical": "a6c4d4d2660ab84cc4e62459e1b67a315903ad6428578b6e6073561bc316c559"
  },
  "descriptor": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/reference-successor.v1.json",
      "bytes": 24103,
      "sha256": "ab4ec7d457e190b466e1fc9117a0a5e95ac02e823dbafb5811a863219f2b7326"
    },
    "canonical": "83287a0e670b55097b4e1aa70c8a67a64eade9ca18d901c7d2ffdaae9e83cefa"
  }
}

SCOPE_PIN = approved_pin("scope")

# A separate, exact second stage. The original reference authority above remains
# immutable. This stage admits no protocols, submitted results or scientific win.
_FIGURE3B_SEAL = object()


def figure3b_pin(name):
    return copy.deepcopy(_FIGURE3B_APPROVED[name]['pin'])


def is_figure3b_selected(row):
    return (row.get('id') == TASK and
            row.get('paper_outcomes', {}).get('primary_policy_revision') == figure3b_pin('descriptor'))


def is_figure3b(value):
    return type(value) is _Figure3bAuthenticated and value._seal is _FIGURE3B_SEAL


class _Figure3bAuthenticated:
    __slots__ = ('_payload', '_legacy', '_seal')

    def __init__(self, documents, legacy, seal):
        object.__setattr__(self, '_payload', _encode(documents))
        object.__setattr__(self, '_legacy', legacy)
        object.__setattr__(self, '_seal', seal)

    def __setattr__(self, name, value):
        raise AttributeError('Authenticated LANGUAGE Figure3b is immutable')

    def __delattr__(self, name):
        raise AttributeError('Authenticated LANGUAGE Figure3b is immutable')

    def snapshot(self):
        return json.loads(self._payload)

    @property
    def primary_improvement(self):
        return self.snapshot()['improvement']

    @property
    def retained_improvement(self):
        return self._legacy.retained_improvement

    @property
    def descriptor_pin(self):
        return figure3b_pin('descriptor')

    @property
    def candidate_interface(self):
        return None

    @property
    def author_reproduction_routes(self):
        return None

    @property
    def members(self):
        return self._legacy.members + [figure3b_pin('descriptor'), figure3b_pin('improvement')]

    @property
    def public_provenance(self):
        provenance = self._legacy.public_provenance
        provenance.update(figure3b_scope_decision=figure3b_pin('root_decision'),
            figure3b_previous_task=figure3b_pin('previous_task'),
            figure3b_previous_outcomes=figure3b_pin('previous_outcomes'),
            selected_input_preparation=figure3b_pin('selected_inputs'),
            selected_fixed_engineering_control=figure3b_pin('fixed_control'))
        return provenance


def projection_improvement(authenticated):
    """Keep the initial historical projection independent of current selection."""
    if is_figure3b(authenticated):
        return authenticated._legacy.primary_improvement
    _need(type(authenticated) is _Authenticated and authenticated._seal is _SEAL,
          'Authenticated LANGUAGE projection context required')
    return authenticated.primary_improvement


def _figure3b_read(name, read_pin):
    value = read_pin(figure3b_pin(name), 'LANGUAGE Figure3b ' + name)
    _need(_digest(value) == _FIGURE3B_APPROVED[name]['canonical'],
          'LANGUAGE Figure3b parsed identity mismatch: ' + name)
    return value


def _authenticate_figure3b(*, task_id, revision_pin, primary_pin, reproduction_pin,
                          previous_pin, retained_improvement_pin, read_pin):
    _need(task_id == TASK, 'Unexpected LANGUAGE Figure3b owner')
    _need(revision_pin == figure3b_pin('descriptor') and primary_pin == figure3b_pin('improvement'),
          'Unreviewed LANGUAGE Figure3b selection')
    for selected, name in ((reproduction_pin, 'reproduction'), (previous_pin, 'pre_outcomes'),
                           (retained_improvement_pin, 'retained_improvement')):
        _require_pin(selected, name)
    documents = {name: _figure3b_read(name, read_pin) for name in _FIGURE3B_APPROVED
                 if name not in ('task', 'outcomes')}
    _need(_digest(documents['previous_task']) == _APPROVED['task']['canonical'] and
          _digest(documents['previous_outcomes']) == _APPROVED['outcomes']['canonical'],
          'LANGUAGE Figure3b predecessor differs from reference authority')

    def reference_read(member_pin, label):
        # The caller already authenticated these archived raw bytes above. Only
        # the exact old pin is redirected; path-only and missing-file fallbacks
        # would let the old stage accidentally consume a new root outcome file.
        if member_pin == approved_pin('outcomes'):
            return copy.deepcopy(documents['previous_outcomes'])
        return read_pin(member_pin, label)

    legacy = authenticate(task_id=TASK, revision_pin=approved_pin('descriptor'),
        primary_pin=approved_pin('improvement'), reproduction_pin=reproduction_pin,
        previous_pin=previous_pin, retained_improvement_pin=retained_improvement_pin,
        read_pin=reference_read)
    descriptor = documents['descriptor']
    _need(descriptor['schema_version'] == 'language-figure3b-successor/v1' and descriptor['task_id'] == TASK,
          'Invalid LANGUAGE Figure3b descriptor')
    _need(documents['improvement']['disposition'] == 'design_ready' and
          documents['improvement']['source_paper'] == legacy.primary_improvement['source_paper'],
          'LANGUAGE Figure3b cannot qualify or replace the source paper')
    outcomes = copy.deepcopy(documents['previous_outcomes'])
    for change in descriptor['outcome_replacements']:
        _replace(outcomes, change)
    _need(_digest(outcomes) == _FIGURE3B_APPROVED['outcomes']['canonical'] and
          all(item['status'] == 'unresolved' and item['protocol'] is None for item in outcomes['pairing'].values()),
          'LANGUAGE Figure3b outcomes must remain the exact unresolved transition')
    documents['outcomes'] = outcomes
    return _Figure3bAuthenticated(documents, legacy, _FIGURE3B_SEAL)


def _project_figure3b(base_dual_task, authenticated):
    _need(is_figure3b(authenticated), 'Authenticated LANGUAGE Figure3b required')
    documents = authenticated.snapshot()
    result = project(base_dual_task, authenticated._legacy)
    _need(result == documents['previous_task'], 'LANGUAGE Figure3b reference projection differs')
    for change in documents['descriptor']['task_replacements']:
        _replace(result, change)
    raw = _encode(result)
    expected = figure3b_pin('task')
    _need(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'],
          'LANGUAGE Figure3b current task differs from exact projection')
    return result


def figure3b_summary(authenticated, outcomes, reproduction, improvement, engine):
    """Closed metadata-only summary; this is not a general scoped-result engine."""
    _need(is_figure3b(authenticated), 'Authenticated LANGUAGE Figure3b required')
    documents, legacy = authenticated.snapshot(), authenticated._legacy.snapshot()
    _need(outcomes == documents['outcomes'] and improvement == documents['improvement'] and
          reproduction == legacy['reproduction'], 'LANGUAGE Figure3b outcome context differs')
    policy_errors = engine.improvement.contract_validate(improvement, TASK)
    _need(not policy_errors, 'Invalid LANGUAGE Figure3b improvement contract: ' + '; '.join(policy_errors))
    errors = engine.outcomes_validate(legacy['outcomes'], reproduction, legacy['improvement'])
    _need(not errors, 'LANGUAGE retained full-panel pair is invalid: ' + '; '.join(errors))
    result = engine.summary(legacy['outcomes'], reproduction, legacy['improvement'])
    _need(not result['errors'] and len(result['cells']) == 4 and
          all(cell['scientific_outcome'] == 'unknown' and cell['receipt'] is None for cell in result['cells']),
          'LANGUAGE retained outcome summary cannot carry a scientific result')
    for cell in result['cells']:
        if cell['outcome'] == 'improvement':
            cell['eligibility'] = improvement['disposition']
            cell['endpoint_eligible'] = False
        cell['pairing_status'] = outcomes['pairing'][cell['outcome']]['status']
        cell['condition_available'] = False
    result['assurance'] = ('Authenticated original full reproduction and selected Figure3b continuous improvement policies. '
        'All four cells remain unknown; no instantiated protocol, AI result, binary win, population inference or current SOTA.')
    return result


def adoption(row, read_pin):
    """Return only the fixed second-stage row and two projected current outputs."""
    _need(row.get('id') == TASK and row.get('track') == 'paper', 'Unexpected LANGUAGE adoption owner')
    declared = row['paper_outcomes']
    for selected, name in ((row['specification'], 'task'), (declared['outcomes'], 'outcomes'),
        (declared['primary_policy_revision'], 'descriptor'), (declared['primary_improvement_contract'], 'improvement'),
        (declared['reproduction_contract'], 'reproduction')):
        _require_pin(selected, name)
    authenticated = authenticate(task_id=TASK, revision_pin=figure3b_pin('descriptor'),
        primary_pin=figure3b_pin('improvement'), reproduction_pin=declared['reproduction_contract'],
        previous_pin=declared['previous_specification'],
        retained_improvement_pin=row['specification_revision']['improvement_contract'], read_pin=read_pin)
    task = project(authenticated._legacy.snapshot()['archived_task.json'], authenticated)
    _need(row['title'] == task['title'], 'LANGUAGE Figure3b cannot change the registry title')
    result = copy.deepcopy(row)
    result['specification'] = figure3b_pin('task')
    result['paper_outcomes'].update(primary_policy_revision=figure3b_pin('descriptor'),
        primary_improvement_contract=figure3b_pin('improvement'), outcomes=figure3b_pin('outcomes'))
    return result, task, authenticated.snapshot()['outcomes']

_FIGURE3B_APPROVED = {
  "descriptor": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/figure3b-successor.v1.json",
      "bytes": 40993,
      "sha256": "1013f10b61350f226e118f06112fde31bd3cd253f66cf5054e8b778fb09a6fc9"
    },
    "canonical": "e9be0bcc4df64a134f3db0934ca280c5d04e1757d9d3f2e7da0c7ddd646be2ab"
  },
  "improvement": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/improvement.figure3b.v1.json",
      "bytes": 18134,
      "sha256": "a386a7008887eedf386613a2e82ae90e21c7222e81ee7653cbc105b442beaf85"
    },
    "canonical": "8e7e087d2a40b5070210fa415859cbf1cf71d4bc4fd41bfedf75c500de2e6ffa"
  },
  "task": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/task.json",
      "bytes": 28518,
      "sha256": "7cc30f5590ebbeb0a8c7114e2df70e1fe2f1d34821684bea4d1998dce2442098"
    },
    "canonical": "258f384f38c2679c3caa512de8f39cf6844e498c2479fc01cb4c3b7128b69052"
  },
  "outcomes": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/outcomes.v1.json",
      "bytes": 1979,
      "sha256": "ac2c888555b163fdf3879446d5ef4b06377124bf1ef14e16f2464cf9e4cba289"
    },
    "canonical": "f834a661de413e9ff0c591dc7cc6feb4ed84d38e5f9ebcd1d0859fc97122604a"
  },
  "previous_task": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/current-definition-pre-figure3b-20261117/task.json",
      "bytes": 31718,
      "sha256": "5c4e1af6794f068015c5750e2d99e1560b35f04cb472c56446f01c884a237029"
    },
    "canonical": "ebdb3965539591eb489c3d6d3a13650e03d69cba549dfceb3c90dbf510f0a895"
  },
  "previous_outcomes": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/current-definition-pre-figure3b-20261117/outcomes.v1.json",
      "bytes": 2579,
      "sha256": "b357dfcf0f0bf086cfa06e4f2373d5e0748981b20f71af7fe615b5d3d79ebb00"
    },
    "canonical": "871ba4890f193dc660b2a5634a37ad80a72d78f4915bdc20715436ed0a3710df"
  },
  "root_decision": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/proposals/figure3b-improvement-scope-v1/ROOT_SELECTION.json",
      "bytes": 3075,
      "sha256": "4038501cc3050e8bbd7f1968c05768f9a0ed0322725f9e167466b694965cb762"
    },
    "canonical": "3bdb0ac24e1ee2a06282ffcfe6be16c7022fa48edd34224576ece4b7f8f3fc6e"
  },
  "selected_inputs": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/original-selected-inputs-20261117/RECEIPT.json",
      "bytes": 8102,
      "sha256": "e5b2f32727da09bbaf654a37b82333a5aae6b781af6596cff49865ca305c4b49"
    },
    "canonical": "59e0476569050581864194f0a1182bf9ef40fe17da49865658c4f08270448852"
  },
  "fixed_control": {
    "pin": {
      "path": "benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/original-selected-fixed-control-20261117/RECEIPT.json",
      "bytes": 9213,
      "sha256": "c641fe0e764b3fd3f0af517db3391b0c4b38fc72d150b47a0bb51f194d04bbcf"
    },
    "canonical": "e867f076297bff527aa0c79ad33820e6978b17d0a5e11017f526bb15a48cfe88"
  }
}
