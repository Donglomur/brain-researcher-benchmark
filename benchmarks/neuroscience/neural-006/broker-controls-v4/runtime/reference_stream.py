"""Per-fit durable acknowledgment; a record is not a native-completion receipt."""
from protocol import TARGETS, exact_keys, need

class ReferenceSession:
    native=True
    initial=None
    def __init__(self,custody,number,case):
        self.custody=custody;self.number=number;self.sequence=0;self.pending=None
        self.slots=[(target,arm) for target in TARGETS for arm in ('N','R','V','J')]
        self.completed=[];self.calls=0;self.finished=False;self.value=None;self.receipts=[]
        self.case=case;self.context_seen=False;self.normalizers=[];self.unacknowledged=None
    def exchange(self,message):
        exact_keys(message,('event','sequence','payload'),'reference_event_fields')
        need(not self.finished and type(message['sequence']) is int and message['sequence']==self.sequence+1 and message['sequence']<=32,'reference_event_sequence')
        self.sequence+=1;kind=message['event'];payload=message['payload']
        if kind=='context':
            need(not self.context_seen and self.sequence==1,'single_reference_context')
            need(payload['participant']==self.case['participant'] and payload['training_rows']==len(self.case['training']) and
                 payload['training_groups']==len(self.case['clusters']) and payload['source_rows']==[r['source_row'] for r in self.case['query']],'reference_context_identity')
            self.context_seen=True
        elif kind=='normalizer':
            need(self.context_seen and self.pending is None and len(self.normalizers)<2 and
                 len(self.completed)==4*len(self.normalizers) and payload['target']==TARGETS[len(self.normalizers)],'reference_normalizer_order')
            self.normalizers.append(payload['target'])
        elif kind=='fit_start':
            need(self.pending is None and len(self.completed)<8,'reference_slot_order')
            need(len(self.normalizers)==len(self.completed)//4+1,'normalizer_before_fitting')
            need((payload['target'],payload['arm'])==self.slots[len(self.completed)],'reference_slot_identity')
            self.pending={'slot':self.slots[len(self.completed)],'call_announced':False}
        elif kind=='fit_call':
            need(self.pending is not None and not self.pending['call_announced'],'reference_call_identity')
            need(type(payload['calls']) is int and payload['calls']==self.calls+1,'reference_call_count');self.calls+=1
            self.pending['call_announced']=True;self.custody.charge_fits(1)
        elif kind=='fit_result':
            need(self.pending is not None and (payload['target'],payload['arm'])==self.pending['slot'],'reference_result_identity')
            need(payload['diagnostic']['fit_called'] is self.pending['call_announced'],'reference_call_disposition')
            self.completed.append({'target':payload['target'],'arm':payload['arm'],'status':payload['diagnostic']['status']})
            self.pending=None
        elif kind=='final':
            need(self.normalizers==list(TARGETS) and len(self.completed)==8 and self.pending is None and payload['actual_fit_calls']==self.calls,'reference_complete_inventory')
            self.value=payload;self.finished=True
        else:raise ValueError('unknown_reference_event')
        self.unacknowledged={'event':kind,'sequence':self.sequence}
        receipt=self.custody.write('native-reference-%05d-event-%02d.json'%(self.number,self.sequence),message)
        self.receipts.append(receipt)
        self.unacknowledged=None
        return {'ack':self.sequence,'durable_record_sha256':receipt['sha256']}
