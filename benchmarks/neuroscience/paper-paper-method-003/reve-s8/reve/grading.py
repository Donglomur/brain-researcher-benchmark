from .deadline import boundary
from .custody import Custody,custody,failure_notice,observation,reader_details
"""Protected scoring after whole bank closure; never executes participant source."""
from .errors import require
from .objects import Reader,canonical,digest,fields,finite_rows
from .metrics import classification,binary_ranking,probability_diagnostics,person_weights,paired_cluster_bootstrap,holm_full_union


class Grader:
    def __init__(self,controller,target_root,target_index_pin):
        self.custody=Custody();self.guard=controller.guard;self.guard()
        require(controller.closed is not None,'global barrier required')
        target_selection=controller.authority.target_access(controller.closed)
        require(target_selection['root']==str(target_root) and target_selection['index']==target_index_pin,'unselected target store')
        self.controller=controller;self.reader=Reader(target_root,target_selection['byte_cap'],target_selection['file_cap'],guard=self.guard)
        try:self.index=self.reader.json(target_index_pin)
        except BaseException as exc:
            state=custody(controller);state.observations.append({'phase':'protected_index','reader':self.reader})
            failure_notice(controller,exc,'Grader.__init__','protected_index_failed',lambda:{'original_error':state.record(),**reader_details(self.reader)})
            raise
        fields(self.index,('schema','plan','targets','scientific_audits'))
        require(self.index['schema']=='reve-protected-target-index-v1' and self.index['plan']==controller.plan_receipt['plan'],'target index source scope')
        controller.ledger.append('protected_targets_opened',{'closed_bank':controller.closed['receipt'],'index':target_index_pin})
        self.targets={};self.predictions={};self.product_read_bytes=0;self.product_read_files=0;self.product_consumed_bytes=0;self.product_partial_observations=[];self.selection=target_selection

    @boundary
    def target(self,key):
        if key not in self.targets:
            require(key in self.index['targets'],'target missing')
            d=self.reader.json(self.index['targets'][key]);fields(d,('events','labels','people','classes','support'))
            require(len(d['events'])==len(d['labels'])==len(d['people'])>0 and len(set(d['events']))==len(d['events']),'target support')
            require(all(type(y) is int and 0<=y<len(d['classes']) for y in d['labels']),'target class')
            self.targets[key]=d
        return self.targets[key]

    @boundary
    def available(self,key):
        require(key in self.controller.plan['prediction_groups'],'unknown passive prediction group')
        return all(x in self.controller.collector.products for x in self.controller.plan['prediction_groups'][key]['members'])

    @boundary
    def prediction(self,key):
        if key not in self.predictions:
            group=self.controller.plan['prediction_groups'][key];rows={};representations=set();states=set();members=[]
            for member in group['members']:
                item=self.controller.collector.products[member];p=item['product'];require(p['kind']=='prediction','nonprediction grader input')
                d=p['details'];obj=d['scores']['object'];values=finite_rows(self.read_product(member,obj),[len(d['events']),len(d['classes'])],d['scores']['dtype']);K=len(d['classes'])
                require(d['classes']==group['classes'] and d['support']==group['support'],'actual group support')
                for i,event in enumerate(d['events']):require(event not in rows,'duplicate actual event');rows[event]=values[i*K:(i+1)*K]
                representations.add(d['representation']);states.add(d['state']);members.append(item['identity'])
            require(set(rows)==set(group['events']) and len(representations)==len(states)==1,'whole actual case prediction closure')
            details={**group,'representation':next(iter(representations)),'state':next(iter(states)),'actual_member_identity':digest(canonical(members))}
            self.predictions[key]=(details,[rows[event] for event in group['events']])
        return self.predictions[key]

    @boundary
    def score(self,prediction_id,target_id,purpose):
        if not self.available(prediction_id):
            missing=[x for x in self.controller.plan['prediction_groups'][prediction_id]['members'] if x not in self.controller.collector.products]
            jobs=[j for j in self.controller.plan['jobs'] if set(j['expected_outputs'])&set(missing)]
            return {'status':'unavailable','prediction':prediction_id,'metrics':None,'reason':'required_prediction_products_missing','missing_products':missing,'original_terminal_statuses':{j['id']:self.controller.collector.terminal.get(j['id'],{}).get('status','not_terminal') for j in jobs}}
        d,rows=self.prediction(prediction_id);t=self.target(target_id)
        require(d['events']==t['events'] and d['classes']==t['classes'] and d['support']==t['support'],'prediction/target exact support')
        if purpose in ('I-person','I-person-montage'):require(d['representation'] in ('probabilities','hard_ncm'),'protected score requires declared probabilities')
        self.guard()
        w=[1.0]*len(rows) if purpose in ('R-paper','R-native') else person_weights(t['people'])
        self.guard()
        metrics=classification(t['labels'],rows,len(t['classes']),w,guard=self.guard)
        self.guard()
        if len(t['classes'])==2:metrics.update(binary_ranking(t['labels'],[r[1] for r in rows],w,guard=self.guard))
        self.guard()
        if d['representation']!='raw_logits':metrics.update(probability_diagnostics(t['labels'],rows,w,guard=self.guard))
        return {'status':'scored','prediction':prediction_id,'prediction_identity':d['actual_member_identity'],
                'target_identity':self.index['targets'][target_id],'purpose':purpose,'representation':d['representation'],'metrics':metrics,
                'events':len(rows),'people':len(set(t['people'])),'source_qualification':False}

    @boundary
    def compare(self,manifest):
        expected=self.controller.scope.contrast_roster();require(len(manifest)==160,'complete confirmatory contrast manifest')
        rows=[]
        for item in manifest:
            self.guard()
            fields(item,('arm','dataset','condition','reference','runs','target','bootstrap_seed','alias_joint_manifest'))
            base={k:item[k] for k in ('arm','dataset','condition','reference')}
            require(base in expected,'contrast outside fixed union')
            require(item['runs'] and item['alias_joint_manifest'],'run/joint alias evidence')
            from .references import admit_contrast_runs,close_reference_bank
            admit_contrast_runs(self.controller,item)
            if not hasattr(self,'reference_banks'):self.reference_banks=close_reference_bank(self.controller.plan['reference_policies'],self.controller)
            family='|'.join(item[k] for k in ('dataset','condition','reference'))
            if not self.reference_banks[family]['complete']:
                rows.append({**base,'estimate':None,'p_value':None,'interval':None,'status':'unavailable','reason':'incomplete original reference run bank','reference_bank':self.reference_banks[family]});continue
            if any(not self.available(x[k]) for x in item['runs'] for k in ('candidate','reference')):
                rows.append({**base,'estimate':None,'p_value':None,'interval':None,'status':'unavailable'});continue
            t=self.target(item['target']);pairs=[]
            for run in item['runs']:
                programmes={p['id']:p for p in self.controller.plan['programmes']}
                cs=self.controller.plan['prediction_groups'][run['candidate']];rs=self.controller.plan['prediction_groups'][run['reference']]
                cp=programmes[cs['programme']];rp=programmes[rs['programme']]
                require(cp['role']=='candidate' and cp['arm']==item['arm'] and rp['role']=='reference','candidate/reference role swap')
                require(cs['dataset']==rs['dataset']==item['dataset'] and cs['condition']==rs['condition']==item['condition'] and rs['method']==item['reference'],'contrast dataset/condition/method binding')
                a,ar=self.prediction(run['candidate']);b,br=self.prediction(run['reference'])
                require(a['events']==b['events']==t['events'] and a['support']==b['support']==t['support'] and a['classes']==b['classes']==t['classes'],'paired complete biological/class support')
                pairs.append({'labels':t['labels'],'candidate':ar,'reference':br})
            uncertainty=paired_cluster_bootstrap(t['people'],pairs,len(t['classes']),item['bootstrap_seed'],guard=self.guard)
            rows.append({**base,**uncertainty,'status':'computed_unqualified'})
        adjusted=holm_full_union(rows,expected)
        self.controller.ledger.append('protected_comparisons_closed',{'manifest':digest(canonical(manifest)),'rows':adjusted,'target_reader_cost':{'bytes':self.reader.bytes,'files':self.reader.files}})
        return adjusted

    @boundary
    def read_product(self,key,obj):
        item=self.controller.collector.products[key]
        require(obj in item['product']['objects'],'unowned scientific audit object')
        require(self.product_read_bytes+obj['bytes']+1<=self.selection['product_read_byte_cap'] and self.product_read_files+1<=self.selection['product_read_file_cap'],'whole protected product-read budget')
        reader=Reader(item['output_root'],obj['bytes']+1,1,guard=self.guard)
        details={'reader':reader};custody(self).observations.append(details)
        def finish(d):
            self.product_read_bytes+=reader.bytes;self.product_read_files+=reader.files;self.product_consumed_bytes+=reader.consumed_bytes;self.product_partial_observations.extend(reader.partial_observations)
        with observation(self,'Grader.read_product',details,refresh=finish):return reader.read(obj)

    @boundary
    def audit_products(self,manifest):
        from . import audit
        expected={k for k,s in self.controller.plan['required_products'].items() if s['kind'] in ('loss_trace','schedule_trace','soup','corpus','preprocessing','architecture','state')}
        require({r['product'] for r in manifest}==expected and len(manifest)==len(expected),'complete scientific product audit roster')
        results=[]
        for row in manifest:
            self.guard()
            fields(row,('product','kind','oracle'));identifier=row['product']
            if identifier not in self.controller.collector.products:
                results.append({'product':identifier,'kind':row['kind'],'status':'unavailable','scientifically_qualified':False});continue
            require(row['oracle'] in self.index['scientific_audits'],'unselected independent scientific oracle')
            oracle=self.reader.json(self.index['scientific_audits'][row['oracle']])
            require(oracle['kind']==row['kind']==self.controller.collector.products[identifier]['product']['kind'],'scientific audit type join')
            fn={'loss_trace':audit.loss,'schedule_trace':audit.schedule,'soup':audit.soup}.get(row['kind'],audit.passive_contract)
            result=fn(self,identifier,oracle);results.append(result)
        self.controller.ledger.append('scientific_audits_closed',{'manifest':digest(canonical(manifest)),'results':results,'product_reader_cost':{'bytes':self.product_read_bytes,'files':self.product_read_files}})
        return results
