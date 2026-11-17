"""Literal qualified Engine operation and exact returned-product admission."""
from pathlib import Path
import hashlib
from core import need, encoded, pin, publish, fresh, capture, parse, relative
from authority import forbid_protected_mounts
from bundle import unpack


class Runtime:
    def __init__(self,selection,frozen,budget,engine,emit,qualification):
        self.selection=selection;self.frozen=frozen;self.budget=budget;self.engine=engine;self.emit=emit;self.qualification=qualification
        self.root=Path(selection['roots']['output']);self.native=fresh(self.root/'native',budget)
        self.derived=fresh(self.root/'derived',budget);self.requests=fresh(self.root/'requests',budget)
        self.results={}

    def source_mounts(self):
        root=Path(self.selection['roots']['source']);result=[]
        for name,d in self.frozen['manifest']['files'].items():
            result.append({'source':str(root/relative(name)),'destination':'/inputs/source/'+name,
                           'pin':d,'bytes_cap':2<<20})
        result.append({'source':self.selection['source_manifest_path'],'destination':'/inputs/source/RUNTIME_SOURCE.json',
                       'pin':self.frozen['pin'],'bytes_cap':2<<20})
        return result

    def run(self,operation,producer,inner,mounts,cutoff,limits,budget=None):
        budget=self.budget if budget is None else budget
        budget.tick(cutoff);need(operation not in self.results,'single attempt for exact operation')
        # Independently enforced native physical resources are distinct from
        # these source-managed logical ceilings. Reserve the complete child
        # allowance before effects; never reset it per I animal or charge zero
        # merely because a failed child did not export its final counters.
        budget.reserve_read(limits['worker_read_bytes'])
        budget.reserve_write(limits['worker_write_bytes'])
        post_cutoff=min(budget.deadline,cutoff+limits['retirement_seconds']+limits['readback_seconds'])
        key=hashlib.sha256(operation.encode()).hexdigest();output=fresh(self.native/key,budget)
        envelope={'schema':'neural058_native_envelope_v1','task':'NEURAL-058','producer':producer,
                  'origin':budget.origin,'deadline':cutoff,'source':self.frozen['pin'],'request':inner,
                  'bundle_limits':self.selection['bundle_limits']}
        need(inner['output_root']=='/scratch/result','fixed scratch producer path')
        raw=encoded(envelope);request_pin=publish(self.requests/(key+'.json'),raw,budget,readonly=True)
        all_mounts=self.source_mounts()+mounts+[{'source':str(self.requests/(key+'.json')),
            'destination':'/inputs/request.json','pin':request_pin,'bytes_cap':4<<20}]
        forbid_protected_mounts(all_mounts,self.selection)
        bootstrap=self.frozen['manifest']['files']['program/bootstrap.py']
        from native_contract import command
        argv=command(self.selection['native_python'],self.frozen['pin'],bootstrap,request_pin,budget.origin,cutoff,limits)
        self.results[operation]={'status':'attempted','request':request_pin,'envelope':envelope}
        self.emit({'kind':'task_operation','task':'NEURAL-058','operation':operation,'request':request_pin,
                   'producer':producer,'cutoff':cutoff,'inner':inner})
        try:
            completed=self.engine.execute(operation,argv,all_mounts,output,limits,cutoff,self.frozen['pin'],
                {'RESULT.n058':self.selection['bundle_limits']['bundle_bytes'],'TERMINAL.json':1<<20})
            terminal_raw,_=capture(output/'TERMINAL.json',completed['artifacts']['TERMINAL.json'],1<<20,budget,readonly=True)
            terminal=parse(terminal_raw)
            need(terminal.get('schema')=='neural058_native_terminal_v1' and terminal.get('task')=='NEURAL-058'
                 and terminal['request']==request_pin and terminal['producer']==producer
                 and terminal['source']==self.frozen['pin'],'exact native terminal request/source producer')
            need(terminal['bundle']==completed['artifacts']['RESULT.n058'],'closed native bundle identity')
            decoded=unpack(output/'RESULT.n058',terminal['bundle'],self.derived/key,budget,self.selection['bundle_limits'])
            members={r['path']:r['pin'] for r in decoded['members']}
            need('RESULT.json' in members and terminal['result']=={'path':'RESULT.json','pin':members['RESULT.json']},'result belongs to closed bundle')
            body,_=capture(Path(decoded['root'])/'RESULT.json',members['RESULT.json'],inner['limits']['metadata_bytes'],budget,readonly=True)
            result=parse(body)
            need(result['request']==pin(encoded(inner)) and result['task']=='NEURAL-058','actual inner producer/result join')
            value={'status':'complete','operation':operation,'envelope':envelope,'request':request_pin,
                   'native':completed,'terminal':terminal,'derived':decoded,'result':result,
                   'result_pin':members['RESULT.json'],'root':decoded['root']}
            self.results[operation]=value;self.emit({'kind':'task_product','task':'NEURAL-058','operation':operation,
                                                   'bundle':terminal['bundle'],'result':members['RESULT.json'],
                                                   'request':request_pin,'derived_members':decoded['members']})
            budget.tick(post_cutoff);return value
        except BaseException as error:
            self.results[operation].update(status='failed',failure_type=type(error).__name__)
            raise
