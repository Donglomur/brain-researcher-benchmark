"""Frozen operator selections and distinct public-training/protected-target readers.

These are file identities, not an issuer of OS isolation or scientific validity.
The caller must independently select the descriptor pin and root before loading.
"""
from dataclasses import dataclass
import hashlib
import math
from n074.contracts import (Population, Endpoint, Case, Design, FitConfig, Protocol,
                            SelectedEvaluationSupport)
from n074.maps import MapValue
from .owned_io import (Pin, Tree, Budget, require, exact_keys as _exact_keys, integer, text,
                       strict_json, digest, separated, canonical_path)


def exact_keys(value, names):
    return _exact_keys(value, names, "closed descriptor schema")


def array(value, name):
    require(type(value) is list, name + ' must be a JSON array')
    return value


def record(value, cls):
    exact_keys(value, tuple(cls.__dataclass_fields__))
    return cls(**value)


@dataclass(frozen=True)
class MapDescriptor:
    person: str
    endpoint: str
    source_identity: str
    path: str
    pin: Pin

    @classmethod
    def parse(cls, row):
        exact_keys(row, ('person', 'endpoint', 'source_identity', 'path', 'pin'))
        for k in ('person', 'endpoint', 'source_identity', 'path'):
            text(row[k], k)
        canonical_path(row['path'], False)
        return cls(row['person'], row['endpoint'], row['source_identity'],
                   row['path'], Pin.parse(row['pin']))


@dataclass(frozen=True)
class Selection:
    identity: str
    population: Population
    designs: tuple
    protocol: Protocol
    support: SelectedEvaluationSupport
    maps: tuple
    maximum_map_bytes: int
    maximum_panel_prediction_bytes: int
    scientific_decisions_identity: str

    @classmethod
    def load(cls, tree, path, pin, budget):
        body = tree.capture(path, pin, budget)
        doc = strict_json(body)
        exact_keys(doc, ('schema', 'population', 'designs', 'protocol', 'support', 'maps',
                         'maximum_map_bytes', 'maximum_panel_prediction_bytes',
                         'scientific_decisions_identity'))
        require(doc['schema'] == 'n074-agent-comparison-selection-v1', 'Unknown selection schema')
        p = doc['population']
        exact_keys(p, ('people', 'endpoints', 'cases', 'declaration_pin', 'taxonomy_pin', 'eligibility_pin'))
        population = Population(tuple(array(p['people'], 'people')),
            tuple(record(e, Endpoint) for e in array(p['endpoints'], 'endpoints')),
            tuple(record(c, Case) for c in array(p['cases'], 'cases')),
            p['declaration_pin'], p['taxonomy_pin'], p['eligibility_pin']).validate()
        designs = []
        for d in array(doc['designs'], 'designs'):
            exact_keys(d, ('endpoint', 'text', 'coefficients', 'provenance'))
            coefficients = tuple(tuple(array(r, 'coefficient')) for r in array(d['coefficients'], 'coefficients'))
            row = Design(d['endpoint'], d['text'], coefficients, d['provenance'])
            row.validate(); designs.append(row)
        require(len(designs) == len(population.endpoints) and
                {d.endpoint for d in designs} == {e.identity for e in population.endpoints},
                'Exactly one selected design per declared endpoint')
        p = doc['protocol']
        exact_keys(p, ('configurations', 'tuning_metric', 'spatial_support_identity', 'selection_identity', 'max_fits'))
        protocol = Protocol(tuple(record(c, FitConfig) for c in array(p['configurations'], 'configurations')),
                            p['tuning_metric'], p['spatial_support_identity'], p['selection_identity'], p['max_fits']).validate()
        support = record(doc['support'], SelectedEvaluationSupport).validate()
        require((support.protocol_identity, support.taxonomy_identity, support.eligibility_identity,
                 support.support_identity) == (protocol.selection_identity, population.taxonomy_pin,
                 population.eligibility_pin, protocol.spatial_support_identity), 'Selection identities disagree')
        maximum = integer(doc['maximum_map_bytes'], 'maximum_map_bytes', minimum=1)
        retained = integer(doc['maximum_panel_prediction_bytes'], 'maximum_panel_prediction_bytes', minimum=1)
        require(8 * support.map_length <= maximum, 'Selected map exceeds its admitted byte cap')
        # One arbitrary candidate plus the three unchanged fixed algorithms.
        require(4 * len(population.cases) * 8 * support.map_length <= retained,
                'Full candidate/reference retention exceeds selected bytes before execution')
        descriptors = tuple(MapDescriptor.parse(r) for r in array(doc['maps'], 'maps'))
        _check_descriptors(descriptors, population, support)
        text(doc['scientific_decisions_identity'], 'scientific_decisions_identity')
        return cls(pin.sha256, population, tuple(designs), protocol, support, descriptors,
                   maximum, retained, doc['scientific_decisions_identity'])


def _check_descriptors(descriptors, population, support):
    expected = {(c.person, c.endpoint, c.source_identity) for c in population.cases if c.status == 'present'}
    require(len(descriptors) == len(expected) and
            {(r.person, r.endpoint, r.source_identity) for r in descriptors} == expected,
            'Descriptors must cover exactly every selected present case')
    require(len({r.path for r in descriptors}) == len(descriptors), 'Map paths must be unique')
    require(all(r.pin.bytes == 8 * support.map_length for r in descriptors), 'Map descriptor geometry differs')


class TrainingReader:
    """Never passed into a submitted programme or host: only fold-scoped bytes are."""
    def __init__(self, selection, tree, budget):
        require(type(selection) is Selection and type(tree) is Tree and type(budget) is Budget,
                'Exact selected training owner contracts required')
        self.selection, self.tree, self.budget = selection, tree, budget
        self.rows = {(r.person, r.endpoint, r.source_identity): r for r in selection.maps}

    def read_training_map(self, person, endpoint, source_identity):
        row = self.rows[(person, endpoint, source_identity)]
        raw = self.tree.capture(row.path, row.pin, self.budget)
        support = self.selection.support
        return MapValue(source_identity, support.support_identity, raw, support.map_length, row.pin.sha256)


class ProtectedOwner:
    """Target descriptor is independently pinned and captured only in evaluation.

    This class must reside in a separately owned evaluator process. It is not a
    Python sandbox, and possession of this object implies target authority.
    """
    def __init__(self, selection, training_tree, target_tree, descriptor_path,
                 descriptor_pin, budget):
        require(type(selection) is Selection, 'Exact separately frozen selection required')
        separated(training_tree, target_tree)
        self.selection, self.tree, self.budget = selection, target_tree, budget
        # These are descriptor metadata, never target maps. The descriptor itself
        # is authenticated before becoming the independent no-argument authority.
        doc = strict_json(target_tree.capture(descriptor_path, descriptor_pin, budget))
        exact_keys(doc, ('schema', 'selection_identity', 'support', 'maps'))
        require(doc['schema'] == 'n074-protected-target-selection-v1' and
                doc['selection_identity'] == selection.identity, 'Protected descriptor selection differs')
        support = record(doc['support'], SelectedEvaluationSupport).validate()
        require(support == selection.support, 'Protected selected support differs')
        rows = tuple(MapDescriptor.parse(r) for r in array(doc['maps'], 'maps'))
        _check_descriptors(rows, selection.population, support)
        training_pins = {(r.person, r.endpoint, r.source_identity): r.pin for r in selection.maps}
        require(all(r.pin == training_pins[r.person, r.endpoint, r.source_identity] for r in rows),
                'Same source identity requires identical training/target content pins')
        self.support = support
        self.rows = {(r.person, r.endpoint, r.source_identity): r for r in rows}

    def authenticate_selected_support(self):
        return self.support

    def read_protected_target(self, person, endpoint, source_identity):
        row = self.rows[(person, endpoint, source_identity)]
        raw = self.tree.capture(row.path, row.pin, self.budget)
        return MapValue(source_identity, self.support.support_identity, raw,
                        self.support.map_length, row.pin.sha256)
