"""Raw failure and complete output barrier custody; no native authority issued."""
from dataclasses import dataclass,field
from core import need

@dataclass
class Attempt:
    identity:str
    raw_first:BaseException|None=None
    failures:list=field(default_factory=list)
    owned:list=field(default_factory=list)
    known_cost_prefix:list=field(default_factory=list)
    unknown_effects:bool=False
    status:str='started'
    def failed(self,stage,error):
        if self.raw_first is None:self.raw_first=error
        self.failures.append((stage,error));self.unknown_effects=True;self.status='failed'
    def cleanup(self,stage,lookup):
        # Method acquisition and invocation are both inside this independent
        # protected attempt. Every occurrence is retained, even the same object.
        try:lookup()()
        except BaseException as error:self.failed(stage,error)
    def summary(self):
        return {'identity':self.identity,'status':self.status,'failures':[{'stage':s,'type':type(e).__name__} for s,e in self.failures],
            'known_cost_prefix':self.known_cost_prefix,'unknown_effects':self.unknown_effects,'raw_first_retained_in_owner':self.raw_first is not None}
    def raise_first(self):
        if self.raw_first is not None:raise self.raw_first

class Barrier:
    def __init__(self,expected,transport):
        need(type(expected)is tuple and expected and len(set(expected))==len(expected),'finite complete selected cell identities')
        self.expected=expected;self.transport=transport;self.completed={};self.failed=False;self.sealed=False
    def accept(self,identity,receipt,prediction):
        need(not self.failed and not self.sealed and identity in self.expected and identity not in self.completed,'one receipt per selected cell before seal')
        need(any(receipt is row for row in self.transport.receipts),'original retained Transport result owner, not a matching dictionary')
        need(receipt['stage']=='predict' and receipt['cell']==identity,'actual prediction stage owner')
        n=receipt['native'];need(n['natural_exit'] is True and n['exit_code']==0 and n['retirement']['absence_confirmed'] is True,'native natural exit and owned retirement required')
        need(receipt['artifacts']['PREDICTIONS.json']==prediction,'captured exact output authority')
        self.completed[identity]=(receipt,prediction)
    def fail(self):self.failed=True
    def seal(self):
        need(not self.failed and set(self.completed)==set(self.expected),'all fixed/adaptive arms and references captured before targets')
        self.sealed=True
    def target_access(self):
        need(self.sealed and not self.failed,'protected target barrier closed');return True
