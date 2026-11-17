"""Immutable publisher identity joins, separate from prepared-file self-description."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import PEOPLE,need,digest,hash_ok
from source_metadata_core import validate_metadata
BINDINGS=json.loads(Path(__file__).with_name('SOURCE_BINDINGS.json').read_text())

def metadata_digest_check(value,expected):
 m=validate_metadata(value);need(digest(m)==expected,'Exact authenticated image metadata and row order');return m

def checked_metadata(value):return metadata_digest_check(value,BINDINGS['normalized_image_metadata_sha256'])

def check_source_asset(row,asset):
 need(asset in BINDINGS['assets'],'Known original asset')
 expected=BINDINGS['assets'][asset]
 need(type(row)is dict and row.get('bytes')==expected['bytes'] and row.get('sha256')==expected['sha256'],'Exact publisher asset/person identity')
 return row

def check_staged_people(people):
 need(type(people)is dict and set(people)==set(PEOPLE),'Allten staged people')
 hashes=[]
 for person in PEOPLE:
  r=people[person];need(r.get('person')==person and r.get('schema')=='neural056_staged_person_v1','Exact stagedperson label');check_source_asset(r.get('archive'),person)
  training=r.get('arrays',{}).get('train',{});need(hash_ok(training.get('sha256')) and type(training.get('bytes'))is int and training['bytes']>0,'Exact prepared training descriptor');hashes.append(training['sha256'])
 need(len(set(hashes))==10,'Distinct prepared training files for allpeople')
 return people
