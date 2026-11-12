"""Complete bounded record transport and target-last collection."""
from __future__ import annotations
from .common import require, encode, decode, identity, FRAME_LIMIT, RESULT_LIMIT

class Records:
    def __init__(self, store, prefix, role, producer, *, row_limit=RESULT_LIMIT):
        self.store,self.prefix,self.role,self.producer=store,prefix,role,producer
        self.row_limit=row_limit;self.parts=[];self.buffer=[];self.bytes=0;self.count=0;self.closed=False

    def append(self, record):
        require(not self.closed,'SEALED_RECORD_STREAM')
        b=encode(record,self.row_limit)+b'\n'
        if self.bytes+len(b)>FRAME_LIMIT:self.flush()
        self.buffer.append(b);self.bytes+=len(b);self.count+=1

    def flush(self):
        if not self.buffer:return
        part=self.store.write(f'{self.prefix}/rows-{len(self.parts):08d}.jsonl',b''.join(self.buffer),
                              role=self.role,producer=self.producer,media_type='application/x-ndjson')
        self.parts.append(part);self.buffer=[];self.bytes=0

    def seal(self):
        require(not self.closed,'DUPLICATE_STREAM_SEAL');self.flush();self.closed=True
        level=self.parts;depth=0
        # Recursive index keeps every control object bounded without dropping later shards.
        while True:
            groups=[];current=[]
            for item in level:
                proposal={'schema':'finite_record_index_v1','depth':depth,'members':current+[item]}
                if len(encode(proposal,16*FRAME_LIMIT))>FRAME_LIMIT-256 and current:
                    groups.append(current);current=[]
                current.append(item)
            if current or not groups:groups.append(current)
            new=[]
            for index,group in enumerate(groups):
                new.append(self.store.write_json(f'{self.prefix}/index-{depth:02d}-{index:08d}.json',
                    {'schema':'finite_record_index_v1','depth':depth,'members':group,
                     'total_records':self.count if len(groups)==1 else None},
                    role='sealed_record_index',producer=self.producer))
            if len(new)==1:return {'root':new[0],'records':self.count,'leaf_parts':len(self.parts),
                                   'role':self.role,'producer':self.producer}
            level=new;depth+=1

    @staticmethod
    def iterate(store,sealed):
        def walk(desc):
            value=store.json(desc,{'sealed_record_index'})
            for member in value['members']:
                store.meter.checkpoint('next_sealed_record_member')
                if value['depth']:
                    yield from walk(member)
                else:
                    body=store.read(member,{sealed['role']})
                    for line in body.splitlines():
                        store.meter.checkpoint('next_sealed_record')
                        yield decode(line,RESULT_LIMIT)
        count=0
        for row in walk(sealed['root']):count+=1;yield row
        require(count==sealed['records'],'SEALED_RECORD_CENSUS_MISMATCH')

class Collector:
    def __init__(self,plan,store,journal,meter,expected):
        self.plan,self.store,self.journal,self.meter=plan,store,journal,meter
        self.expected={x['id']:x for x in expected}
        require(len(self.expected)==len(expected),'DUPLICATE_EXPECTED_PRODUCT')
        self.observed={};self.sealed=None
        self.streams={
            'participant':Records(store,'collection/participant','sealed_own_product',plan.hash),
            'reference':Records(store,'collection/reference','reference_product',plan.hash)}

    def add(self,identifier,record,*,issuer,source,state,input_identity,support_identity):
        self.meter.checkpoint('before_product_collection')
        require(self.sealed is None and identifier in self.expected,'UNEXPECTED_OR_LATE_PRODUCT')
        require(identifier not in self.observed,'DUPLICATE_PRODUCT')
        expected=self.expected[identifier]
        binding={'issuer':issuer,'source':source,'state':state,'input_identity':input_identity,
                 'support_identity':support_identity}
        for key,value in binding.items():require(value==expected[key],'PRODUCT_CONTRACT_SUBSTITUTION',key)
        require(record['process_receipt']['event']=='PROCESS_COMPLETE','MISSING_ORIGINAL_PROCESS_SUCCESS')
        completion=record.get('completion',record.get('process_completion'))
        require(completion and completion['telemetry']['original_wait_complete']
                and completion['telemetry']['descendants_closed']
                and completion['telemetry']['observation_complete'],'INCOMPLETE_PRODUCT_CUSTODY')
        from .objects import put_object
        response=put_object(self.store,'collection/objects/'+identity(identifier),record['response'],
                            producer=record['product_sha256'],
                            role='sealed_own_product' if issuer.startswith('participant') else 'reference_product')
        product={'id':identifier,'binding':binding,'product_sha256':record['product_sha256'],
                 'process_receipt':record['process_receipt'],'response_object':response}
        kind='participant' if issuer.startswith('participant') else 'reference'
        require(issuer.startswith(('participant','reference')),'UNKNOWN_PRODUCT_ISSUER_NAMESPACE')
        self.streams[kind].append(product);self.observed[identifier]=identity(product)
        return product

    def seal(self,reports,resources,ancestry,capsule,operator_receipts):
        self.meter.checkpoint('before_global_collection_seal')
        require(set(self.observed)==set(self.expected),'INCOMPLETE_FULL_PRODUCT_COLLECTION',
                sorted(set(self.expected)-set(self.observed)))
        require(reports['terminal_complete'] and resources['complete'],'REPORT_OR_RESOURCE_NOT_CLOSED')
        require(operator_receipts['covered']==sorted(set(self.plan.contracts.operators)-{'O28','O29','O30'}),
                'OPERATOR_CUSTODY_INCOMPLETE')
        stream={k:v.seal() for k,v in self.streams.items()}
        self.meter.checkpoint('after_record_seal_before_global_commit')
        from .objects import put_object
        operators=put_object(self.store,'collection/operator-evidence',operator_receipts,
                             producer=self.plan.hash)
        self.sealed={'schema':'finite_global_collection_seal_v1','plan_sha256':self.plan.hash,
             'products':stream,'expected_products_sha256':identity(self.expected),
             'observed_products_sha256':identity(self.observed),'reports':reports,
             'resources':resources,'ancestry_sha256':identity(ancestry),
             'capsule_sha256':identity(capsule),'operator_receipts':operators}
        descriptor=self.store.write_json('collection/GLOBAL_SEAL.json',self.sealed,
                                         role='global_collection_seal',producer=self.journal.head)
        self.meter.checkpoint('global_commit_complete')
        self.journal.append('GLOBAL_COLLECTION_COMMITTED',{'seal':descriptor})
        return descriptor

class TargetAccess:
    def __init__(self,authority,plan,store,journal,meter,seal):
        self.authority,self.plan,self.store,self.journal,self.meter=authority,plan,store,journal,meter
        self.seal=seal;self.count=0

    def check(self,effect):
        self.meter.checkpoint('target_access_admission')
        self.journal.append('TARGET_ACCESS_START',{'effect':effect,'seal':self.seal,'ordinal':self.count})
        # Critical post-START and pre-open checks share the ORIGINAL meter/deadline.
        self.meter.checkpoint('immediately_after_target_START')
        self.authority.admit(plan=self.plan.hash,source_manifest=self.plan.value['source_manifest_sha256'],
             route=self.plan.route,input_registry=self.plan.value['input_registry_sha256'],effect=effect)
        seal=self.store.json(self.seal,{'global_collection_seal'})
        require(seal['plan_sha256']==self.plan.hash,'WRONG_GLOBAL_SEAL')
        self.meter.checkpoint('immediately_before_protected_target_open')
        self.count+=1
        receipt=self.journal.append('TARGET_ACCESS_ADMITTED',{'effect':effect,'ordinal':self.count,
            'original_seal':self.seal,'authority':self.authority.hash})
        self.meter.checkpoint('after_target_admission_receipt_before_effect')
        return receipt
