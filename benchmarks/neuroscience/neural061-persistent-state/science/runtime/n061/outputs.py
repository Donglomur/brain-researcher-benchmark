"""Owned expected dispositions. Unselected work has no prediction placeholder."""
from dataclasses import dataclass
from enum import Enum
from .contracts import need
from .catalogue import OutputKey,StudyCatalogue

class Disposition(Enum):
    COMPLETE='complete'
    UNAVAILABLE='scientific_unavailable'
    FAILED='failed'
    UNSTARTED='unstarted'
    HELD='held_missing_producer'

@dataclass(frozen=True)
class Output:
    key:OutputKey
    status:Disposition
    body:object
    receipt:object
    cause:object

class Collection:
    def __init__(self,catalogue):
        self.catalogue=catalogue.validate();self.rows={k:Output(k,Disposition.UNSTARTED,None,None,None) for k in catalogue.expected}
        self.events=[];self.first_error=None;self.cleanup_errors=[];self.seal=None
    def put(self,key,body,receipt,scientific_cause=None):
        need(self.seal is None and self.first_error is None,'live original collection')
        need(type(key) is OutputKey and key in self.rows and self.rows[key].status is Disposition.UNSTARTED,'original output once')
        need(type(body) is dict and body.get('status') in ('complete','unavailable'),'complete or source-prespecified unavailable')
        unavailable=body['status']=='unavailable'
        need((scientific_cause is not None) if unavailable else (scientific_cause is None and receipt is not None),'actual source cause or captured original operation receipt')
        row=Output(key,Disposition.UNAVAILABLE if unavailable else Disposition.COMPLETE,body,receipt,scientific_cause)
        self.rows[key]=row;self.events.append(row);return row
    def fail(self,error):
        if self.first_error is None:self.first_error=error
    def freeze(self):
        need(self.seal is None and self.first_error is None,'no replacement of failed/closed collection')
        need(set(self.rows)==set(self.catalogue.expected),'complete expected graph')
        need(all(x.status in (Disposition.COMPLETE,Disposition.UNAVAILABLE) for x in self.rows.values()),'no missing failed held or unstarted output before target gate')
        self.seal=tuple(self.rows[k] for k in self.catalogue.expected)
        return self.seal
    def validate_seal(self):
        need(type(self.seal) is tuple and len(self.seal)==len(self.catalogue.expected) and self.first_error is None,'actual original complete collection seal')
        need(all(self.rows[k] is r and r.key==k for k,r in zip(self.catalogue.expected,self.seal,strict=True)),'exact source output identity not supplied equivalent body')
        originals={id(e):e for e in self.events}
        need(len(originals)==len(self.events)==len(self.seal) and all(originals.get(id(r)) is r for r in self.seal),'every sealed output has its unique original producer event')
        need(all(r.status in (Disposition.COMPLETE,Disposition.UNAVAILABLE) for r in self.seal),'no partial terminal disposition')
        return self.seal
