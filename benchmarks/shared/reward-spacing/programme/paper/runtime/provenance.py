"""Typed scientific provenance and stopped-output artifact authentication.

No JSON declaration supplied by a candidate substitutes for collected bytes.
Protected reference contracts define semantic artifact roles; regenerated files
are not required to have the reference file's encoding or byte digest.
"""
import base64
import binascii
import copy
from pathlib import PurePosixPath
from types import MappingProxyType
from reward_common import (need,integer,strict_json_loads,canonical_json_bytes,sha256,
                           object_sha256,unique_records,verify_pin)


def digest(value):
    need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),'SHA-256 digest')
    return value


def text(value):
    need(type(value) is str and bool(value),'Nonempty scientific identifier');return value


def cohort(value):
    need(type(value) is dict and set(value)=={'schema','registry_sha256','unit','members','eligibility_branch'},
         'Typed cohort/exclusion manifest')
    need(value['schema']=='reward_cohort_manifest_v2','Cohort schema');digest(value['registry_sha256'])
    need(value['unit'] in ('animal','model_iteration','group','design','image'),'Declared cohort unit')
    text(value['eligibility_branch']);members=unique_records(value['members'],['unit_id'])
    for row in members.values():
        need(set(row)=={'unit_id','condition','source_identity_sha256','included','exclusion_reason','session_ordinals','trial_ids'},
             'Complete member identity, eligibility and observation support')
        text(row['unit_id']);text(row['condition']);digest(row['source_identity_sha256'])
        need(type(row['included']) is bool,'Explicit inclusion flag')
        need((row['included'] and row['exclusion_reason'] is None) or
             (not row['included'] and type(row['exclusion_reason']) is str and row['exclusion_reason']),
             'Explicit exclusion reason; no outcome omission by absent row')
        need(type(row['session_ordinals']) is list and row['session_ordinals']==sorted(set(row['session_ordinals'])),
             'Unique source-ordered session support')
        for n in row['session_ordinals']:integer(n,'documented session ordinal',1)
        need(type(row['trial_ids']) is list and len(row['trial_ids'])==len(set(row['trial_ids'])),'Unique trial support')
        for trial in row['trial_ids']:text(trial)
    need(value['members'] or value['unit']=='design','Nonempty observational cohort')
    result=copy.deepcopy(value);result['members']=sorted(result['members'],key=lambda r:r['unit_id']);return result


def statistic(value):
    fields={'schema','recipe_id','replication_unit','estimand','method','alternative','multiplicity','units',
            'source_contract_sha256','parameters','aggregation'}
    need(type(value) is dict and set(value)==fields,'Typed statistical/estimand recipe')
    need(value['schema']=='reward_statistical_recipe_v2','Statistical schema')
    for key in ('recipe_id','replication_unit','estimand','method','alternative','aggregation'):text(value[key])
    digest(value['source_contract_sha256']);need(type(value['parameters']) is dict,'Declared analysis parameters')
    need(type(value['units']) is dict and value['units'],'Explicit scientific units')
    for key,unit in value['units'].items():text(key);text(unit)
    m=value['multiplicity'];need(type(m) is dict and set(m)=={'method','family_id','hypotheses'},'Multiplicity family')
    text(m['method']);text(m['family_id']);need(type(m['hypotheses']) is list and len(m['hypotheses'])==len(set(m['hypotheses'])),
                                             'Unique hypothesis family')
    for h in m['hypotheses']:text(h)
    canonical_json_bytes(value)  # No nonfinite analysis parameter or undeclared object.
    return copy.deepcopy(value)


def artifact_contracts(value):
    need(type(value) is list and value,'Required artifact role contract')
    roles=unique_records(value,['role'])
    for c in roles.values():
        need(set(c)=={'role','validator_id','media_type','required','axes','source_contract_sha256'},
             'Typed artifact/content contract')
        for k in ('role','validator_id','media_type'):text(c[k])
        need(type(c['required']) is bool,'Required artifact marker');digest(c['source_contract_sha256'])
        axes=unique_records(c['axes'],['axis'])
        for ax in axes.values():
            need(set(ax)=={'axis','label','unit'},'Typed scientific axis')
            for v in ax.values():text(v)
    need(any(c['required'] for c in value),'At least one required scientific artifact')
    return roles


def artifact_pin(value):
    need(type(value) is dict and set(value)=={'path','bytes','sha256','role','media_type'},'Typed candidate artifact pin')
    relative=value['path'];text(relative);p=PurePosixPath(relative)
    need(not p.is_absolute() and '\\' not in relative and '..' not in p.parts and str(p)==relative and relative!='.',
         'Normalized relative artifact path')
    integer(value['bytes'],'artifact bytes',1);digest(value['sha256']);text(value['role']);text(value['media_type'])
    return value


class SealedArtifacts:
    """Evaluator-owned immutable bytes constructed after stopped-output capture."""
    def __init__(self,bodies,submission_sha256):
        digest(submission_sha256);need(all(type(b) is bytes for b in bodies.values()),'Collected artifact bytes')
        self._bodies=MappingProxyType(dict(bodies));self.submission_sha256=submission_sha256

    def bytes_for(self,pin):
        artifact_pin(pin);need(pin['path'] in self._bodies,'Required artifact absent from stopped output')
        body=self._bodies[pin['path']]
        need(len(body)==pin['bytes'] and sha256(body)==pin['sha256'],'Artifact bytes do not match submitted pin')
        return body

    @property
    def paths(self):return frozenset(self._bodies)


def collect_reproduction_bundle(body,expected_stopped_pin,max_bytes=16777216):
    need(type(body) is bytes and len(body)==expected_stopped_pin['bytes'] and sha256(body)==expected_stopped_pin['sha256'],
         'Exact stopped-output bundle identity')
    value=strict_json_loads(body,max_bytes)
    need(type(value) is dict and set(value)=={'schema','panels','artifacts'} and
         value['schema']=='reward_reproduction_submission_v2','Reproduction bundle schema')
    unique_records(value['panels'],['panel_id']);bodies={};size=0
    for artifact in value['artifacts']:
        need(type(artifact) is dict and set(artifact)=={'pin','encoding','data'},'Artifact envelope')
        pin=artifact_pin(artifact['pin']);need(artifact['encoding']=='base64','Explicit artifact byte encoding')
        need(type(artifact['data']) is str,'Encoded artifact text')
        try:data=base64.b64decode(artifact['data'],validate=True)
        except (ValueError,binascii.Error):raise ValueError('Invalid artifact base64')
        size+=len(data);need(size<=max_bytes,'Artifact output admission bound')
        need(pin['path'] not in bodies,'Duplicate artifact path')
        need(len(data)==pin['bytes'] and sha256(data)==pin['sha256'],'Collected artifact content identity')
        bodies[pin['path']]=data
    store=SealedArtifacts(bodies,sha256(body))
    declared=set()
    for row in value['panels']:
        pins=row.get('artifact_pins',[])
        need(type(pins) is list,'Typed panel artifact list')
        for pin in pins:artifact_pin(pin);declared.add(pin['path'])
    need(declared==store.paths,'Exact declared/collected artifact closure')
    return {'panels':value['panels'],'artifacts':store,'stopped_submission_sha256':sha256(body)}


def scientific_json(body,panel,contract):
    """Semantic numerical artifact check; whitespace/encoding may differ.

    This validator qualifies a data/table artifact, not arbitrary raster/SVG/PDF
    geometry. Figure/image contracts need their separately qualified validator.
    """
    need(contract['media_type']=='application/json','Scientific JSON media type')
    value=strict_json_loads(body,16777216)
    expected={'schema':'reward_scientific_artifact_v2','panel_id':panel['panel_id'],'role':contract['role'],
              'axes':contract['axes'],'scientific_value':panel['value'],
              'cohort_sha256':object_sha256(cohort(panel['cohort_manifest'])),
              'statistical_recipe_sha256':object_sha256(statistic(panel['statistical_recipe'])),
              'source_contract_sha256':contract['source_contract_sha256']}
    need(value==expected,'Artifact scientific content, axes, units or provenance do not match panel')
    return {'semantic_content_match':True,'validator_id':'scientific_json_v1','figure_geometry_qualified':False}


def validate_panel_provenance(reference,candidate,artifacts,validators=None):
    """Run before comparing numeric values. Reference is evaluator-owned."""
    need(candidate['panel_id']==reference['panel_id'],'Scientific panel identity')
    need(cohort(reference['cohort_manifest'])==cohort(candidate['cohort_manifest']),
         'Exact adjudicated cohort/exclusion/observation support')
    need(statistic(reference['statistical_recipe'])==statistic(candidate['statistical_recipe']),
         'Exact scientific estimand, unit, inference and multiplicity recipe')
    contracts=artifact_contracts(reference['artifact_contract']);pins=unique_records(candidate['artifact_pins'],['role'])
    need({k for k,c in contracts.items() if c['required']}<=set(pins)<=set(contracts),'Required artifact roles')
    need(isinstance(artifacts,SealedArtifacts),'Evaluator-collected stopped artifact bytes required')
    registry={'scientific_json_v1':scientific_json}
    if validators:
        need(not(set(validators)&set(registry)),'Cannot override built-in scientific validator');registry.update(validators)
    results=[]
    for key,pin in pins.items():
        artifact_pin(pin);contract=contracts[key]
        need(pin['media_type']==contract['media_type'],'Artifact contract media type')
        need(contract['validator_id'] in registry,'Required artifact content validator is unqualified/unavailable')
        body=artifacts.bytes_for(pin)
        check=registry[contract['validator_id']](body,candidate,contract)
        need(type(check) is dict and check.get('semantic_content_match') is True,'Artifact scientific content validation failed')
        results.append({'role':key[0],'path':pin['path'],'bytes':len(body),'sha256':sha256(body),
                        'contract_sha256':object_sha256(contract),'validation':check})
    return {'cohort_match':True,'statistical_recipe_match':True,'artifacts':results,
            'stopped_submission_sha256':artifacts.submission_sha256}
