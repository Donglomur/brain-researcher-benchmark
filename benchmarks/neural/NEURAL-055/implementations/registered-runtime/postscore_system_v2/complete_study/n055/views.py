"""Actual isolated full-fold views and fixed original neural ablations.

Only a qualified campaign may call this producer. Header/array work is never used
by BUILD ONLY controls. The operator-only alignment schedule never enters a view.
"""
import hashlib
import os
from pathlib import Path
from .common import require,encoded,pin,stamp
from .streaming import copy
from .registry import token

class Views:
    def __init__(self,inputs,journal,budget,profile,public_docs):
        self.inputs=inputs;self.journal=journal;self.budget=budget;self.profile=profile;self.public_docs=public_docs
        self.records=[];self.current={}
        self.base=journal.root/'views';self.base.mkdir()
    def publish(self,path,body):
        self.journal.write(str(path.relative_to(self.journal.root)),body);os.chmod(path,0o444)
        return pin(body)
    def publish_public(self,root):
        from .participant_contract import PUBLIC_V3
        expected={}
        for name,body in self.public_docs.items():
            require(name in ('TASK.md','POLICY.json','CASE_SCHEMA.json','PREDICTION_SCHEMA.json','interface.py')+PUBLIC_V3,'only declared public task docs')
            expected[name]=self.publish(root/name,body)
        return expected
    def transformed(self,path,expected,shape,coordinates,arm,permutation,deadline):
        """Preserve exact C-order float64 geometry; zero bytes encode positive zero."""
        self.budget.check('before qualified neural transform',deadline)
        source=path.with_name(path.name+'.untransformed');path.rename(source)
        self.budget.admit_read(expected['bytes']+4108);self.budget.admit_write(expected['bytes'])
        before=source.lstat();fi=fo=None;first=None;h=hashlib.sha256();observed=0
        record={'role':'actual_neural_control_transform','arm':arm,'expected':expected,'written_bytes':0,'complete':False,'errors':[]};self.records.append(record)
        try:
            fi=os.open(source,os.O_RDONLY|os.O_NOFOLLOW);fo=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
            self.budget.file_created()
            head=os.read(fi,min(4108,expected['bytes']));self.budget.read(len(head));self.budget.check('after header return',deadline)
            geometry=self.inputs.packet.npy_header(head,expected['bytes'],{'shape':shape,'eeg':True})
            offset=geometry['header_bytes'];header=head[:offset]
            def write(body):
                nonlocal observed
                pos=0
                while pos<len(body):
                    try:n=os.write(fo,memoryview(body)[pos:])
                    except BaseException as exc:
                        n=self.budget.failed_write('transform:'+str(path),exc,len(body)-pos)
                        if type(n)is int and 0<n<=len(body)-pos:
                            self.budget.written(n);h.update(memoryview(body)[pos:pos+n]);observed+=n;record['written_bytes']=observed
                        elif n is None:record['unknown_write_extent']=True
                        raise
                    n=self.budget.write_count('transform:'+str(path),n,len(body)-pos)
                    if n is None:record['unknown_write_extent']=True
                    require(n is not None and n>0,'transform actual write progress')
                    self.budget.written(n);h.update(memoryview(body)[pos:pos+n]);observed+=n;record['written_bytes']=observed;pos+=n
                    self.budget.check('after neural-transform write',deadline)
            write(header);rowbytes=17*100*8
            masked=[ch*100+t for ch in range(17) for t,x in enumerate(coordinates['times_seconds']) if (arm=='PRE_ONLY' and x>=0) or (arm=='POST_ONLY' and x<0)]
            order=permutation if arm=='ALIGN_SHUFFLE' else range(shape[0])
            require(len(order)==shape[0] and sorted(order)==list(range(shape[0])),'whole-row control mapping')
            for row in order:
                self.budget.check('before neural-control row',deadline);os.lseek(fi,offset+row*rowbytes,os.SEEK_SET)
                body=bytearray()
                while len(body)<rowbytes:
                    b=os.read(fi,rowbytes-len(body));self.budget.read(len(b));body.extend(b)
                    self.budget.check('after neural-control row return',deadline);require(bool(b),'complete original row')
                if arm=='IMAGE_ONLY':body=bytearray(rowbytes)
                else:
                    for position in masked:body[position*8:position*8+8]=b'\0'*8
                write(body)
            require(observed==expected['bytes'],'whole transformed original extent')
            require(stamp(source.lstat())==stamp(before)==stamp(os.fstat(fi)),'stable intermediate source')
            os.fchmod(fo,0o444);os.fsync(fo);self.budget.check('after neural transform fsync',deadline)
        except BaseException as exc:first=exc;record['errors'].append(('transform',exc))
        finally:
            for role,fd in [('input',fi),('output',fo)]:
                if fd is not None:
                    try:os.close(fd)
                    except BaseException as exc:
                        record['errors'].append(('close_'+role,exc))
                        self.budget.uncertain('transform:'+str(path)+':'+role,'managed_descriptor_closure',exc,descriptor=fd)
                        if first is None:first=exc
            record['sha256']=h.hexdigest()
        if first is not None:
            self.journal.carrier.fail(first,'view-transform');raise first
        source.unlink();self.budget.live_bytes-=expected['bytes']  # Attempts are cumulative, never refunded.
        self.budget.check('after neural transform retirement',deadline);record['complete']=True
        return {'bytes':observed,'sha256':h.hexdigest()}
    def build(self,cell,phase,deadline,alignment=None):
        self.budget.check('before whole original view',deadline);self.inputs.unchanged(cell['outer_person'])
        row=self.inputs.rows[cell['outer_person']];root=self.base/(token(cell)+'-'+phase)
        require(not root.exists(),'fresh full-cell/phase view');root.mkdir();(root/'train').mkdir()
        self.current[str(root)]={'cell':cell,'phase':phase,'complete':False,'expected':{},'stamps':{}}
        selected=row['fit_names'] if phase=='FIT' else set(row['files'])
        expected={};newpins={}
        for name in sorted(selected):
            # Metadata is rewritten below only for actual transformed array pins.
            if name in ('ASSETS.json','TRAINING.json'):continue
            self.budget.check('before full view member',deadline)
            d=row['files'][name];target=root/name
            newpins[name]=copy(row['root']/name,target,d,self.budget,self.records)
            is_train=name.startswith('train/') and name.endswith('.npy');is_query=name=='query.npy'
            should=(cell['arm'] in ('PRE_ONLY','POST_ONLY') and (is_train or is_query)) or (is_query and cell['arm'] in ('IMAGE_ONLY','ALIGN_SHUFFLE'))
            if should:
                perm=alignment if cell['arm']=='ALIGN_SHUFFLE' else None
                if cell['arm']=='ALIGN_SHUFFLE':require(perm is not None and len(perm)==200 and all(i!=j for i,j in enumerate(perm)),'precommitted original derangement')
                newpins[name]=self.transformed(target,newpins[name],(16540,17,100) if is_train else (200,17,100),row['coordinates'],cell['arm'],perm,deadline)
            expected[name]=newpins[name]
        t=dict(row['training']);t['people']=[dict(p,eeg={'path':p['eeg']['path'],**newpins[p['eeg']['path']]}) for p in row['training']['people']]
        expected['TRAINING.json']=self.publish(root/'TRAINING.json',encoded(t))
        if phase=='INFER':
            a=dict(row['assets']);a['training']={'path':'TRAINING.json',**expected['TRAINING.json']};a['query_eeg']={'path':'query.npy',**newpins['query.npy']}
            expected['ASSETS.json']=self.publish(root/'ASSETS.json',encoded(a))
        expected.update(self.publish_public(root))
        expected['CELL.json']=self.publish(root/'CELL.json',encoded(cell))
        host={'schema':'neural055-visible-native-profile-v3','memory_bytes':self.profile['memory_bytes'],'pids':self.profile['pids'],'original_action_deadline':deadline}
        expected['HOST.json']=self.publish(root/'HOST.json',encoded(host))
        value={'schema':'neural055-'+phase.lower()+'-input-v1','training':'TRAINING.json','coordinates':'coordinates.json'}
        if phase=='INFER':value.update(case='CASE.json',assets='ASSETS.json')
        filename='train.json' if phase=='FIT' else 'query.json';expected[filename]=self.publish(root/filename,encoded(value))
        os.chmod(root/'train',0o555);os.chmod(root,0o555)
        stamps={n:stamp((root/n).lstat()) for n in expected};self.current[str(root)]={'expected':expected,'stamps':stamps,'cell':cell,'phase':phase,'complete':True}
        self.budget.check('after full original view',deadline)
        return root,{'cell':cell,'phase':phase,'files':expected,'source_original_case':row['case']['case_id']}
    def retire(self,root,deadline):
        root=Path(root);record=self.current[str(root)]
        files,dirs,_=self.inputs.compat.inventory(root,200000000000,128)
        require(set(files)==set(record['expected']) and {n:v[1] for n,v in files.items()}==record['stamps'],'same whole isolated view')
        os.chmod(root,0o700);os.chmod(root/'train',0o700)
        for name,d in record['expected'].items():
            (root/name).unlink();self.budget.live_bytes-=d['bytes']  # Only live bytes retire.
        (root/'train').rmdir();root.rmdir();del self.current[str(root)]
        self.budget.check('after whole view retirement',deadline)
