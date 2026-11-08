"""Concrete private MAT selector/extractor; actual source schema remains gated.

Only independently admitted exact field paths/units/axes may be used. There is
no automatic discovery, guessed bstruct field, synthetic clock or data callback.
Actual MAT access is disabled in the shipped deployment and not exercised by
source construction controls.
"""
import io
from fractions import Fraction
from ach_util import need,integer,finite,require_pin,pin_bytes,read_exact,exact_fields,finish_owned

def select(root,steps):
    need(type(steps) is list and len(steps)<=64,'bounded exact source selector')
    value=root
    for step in steps:
        exact_fields(step,('operation','key'),'exact field/index operation')
        if step['operation']=='field':
            key=step['key'];need(type(key) is str and key and not key.startswith('__'),'declared source field')
            if type(value) is dict:
                need(key in value,'actual declared field exists');value=value[key]
            else:
                need(key in getattr(value,'_fieldnames',()),'actual MATLAB struct field exists')
                value=getattr(value,key)
        elif step['operation']=='index':
            key=step['key'];need(type(key) is list and key,'literal multidimensional source index')
            for i in key:integer(i)
            if type(value) in (list,tuple):
                for i in key:need(i<len(value),'source index in bounds');value=value[i]
            else:value=value[tuple(key)]
        else:need(False,'no arbitrary source evaluation or expression')
    return value

def raw_scalar(value):
    if type(value) not in (int,float):
        need(getattr(value,'shape',None)==(),'exact source scalar shape')
        value=value.item()
    finite(value)
    return value

def scalar(value):return finite(raw_scalar(value))

def clock_value(value,rule):
    """Only a separately declared exact rational clock/rounding policy.

    No actual scale, rounding choice or uncertainty bound is supplied here.
    Source admission must establish all of them for the original recording.
    """
    exact_fields(rule,('numerator','denominator','rounding','maximum_error_ns','evidence_pin'),'declared clock conversion')
    integer(rule['numerator'],1);integer(rule['denominator'],1);integer(rule['maximum_error_ns'])
    require_pin(rule['evidence_pin']);raw=raw_scalar(value)
    exact=Fraction(raw)*Fraction(rule['numerator'],rule['denominator'])
    mode=rule['rounding'];need(mode in ('exact','floor','ceil'),'explicit conservative clock rule')
    if mode=='exact':need(exact.denominator==1,'no undeclared clock quantization');result=exact.numerator
    elif mode=='floor':result=exact.numerator//exact.denominator
    else:result=-((-exact.numerator)//exact.denominator)
    need(abs(exact-result)<=rule['maximum_error_ns'],'declared clock-conversion error bound')
    integer(result)
    return result

def vector(value,expected_count,axis):
    integer(expected_count);integer(axis)
    if type(value) is list:
        need(axis==0 and len(value)==expected_count,'exact declared vector extent')
        return [scalar(x) for x in value]
    shape=getattr(value,'shape',None)
    need(type(shape) is tuple and axis<len(shape) and shape[axis]==expected_count and
         all(n==1 for i,n in enumerate(shape) if i!=axis),'exact declared vector axes, no guessed transpose')
    return [scalar(value[tuple(i if j==axis else 0 for j in range(len(shape)))]) for i in range(expected_count)]

class MatReader:
    def __init__(self,assets,manifest,ledger,execution_admission):
        exact_fields(execution_admission,('operation','assets_pin','mapping_pin','decoder_environment_pin',
            'resource_profile_pin','issuer_observation_pin','actual_data_access_enabled'),'private decoder admission')
        need(execution_admission['actual_data_access_enabled'] is True and
             execution_admission['operation']=='admitted_original_mat_projection','actual data access not selected')
        # Controller obtains this exact record from the independently admitted
        # observer; the dictionary alone is never an authority.
        from ach_util import pin
        need(execution_admission['assets_pin']==pin(assets) and execution_admission['mapping_pin']==pin(manifest),
             'same complete original asset/field mapping')
        for k in ('decoder_environment_pin','resource_profile_pin','issuer_observation_pin'):require_pin(execution_admission[k])
        self.assets,self.manifest,self.ledger=assets,manifest,ledger;self.opened={};self.live={}

    def open(self,asset_id):
        if asset_id in self.opened:return self.opened[asset_id]
        record=self.assets[asset_id]
        exact_fields(record,('path','pin','decoded_extent_bytes','format','source_semantics_pin'),'admitted MAT asset')
        require_pin(record['pin']);require_pin(record['source_semantics_pin'])
        integer(record['decoded_extent_bytes'],1)
        need(record['format']=='mat_v5_scipy_exact_declared_axes','named supported decoder; unsupported source formats refuse')
        token=self.ledger.acquire_live(record['decoded_extent_bytes']+record['pin']['bytes'],'private/MAT-full-decoder')
        try:
            raw=read_exact(record['path'],record['pin'],record['pin']['bytes'],self.ledger)
            # Actual full-input decompression and dependency identity require the
            # separately admitted process/image/resource envelope. No import or
            # decoder invocation occurs in source controls.
            import scipy.io
            value=scipy.io.loadmat(io.BytesIO(raw),struct_as_record=False,squeeze_me=False,mat_dtype=False,
                                  verify_compressed_data_integrity=True)
            self.ledger.tick();self.opened[asset_id]=value;self.live[asset_id]=token
            return value
        except Exception as error:
            finish_owned([('MAT decode failure accounting',lambda:self.ledger.fail('private/MAT-decode',error)),
                ('MAT failed allocation release',lambda:self.ledger.release_live(token))],error)
            raise

    def read(self,selector):
        exact_fields(selector,('asset','steps','shape','axis','scale','units','source_pin','clock_rule'),'exact admitted scalar/vector selector')
        require_pin(selector['source_pin']);need(type(selector['units']) is str and selector['units'],'frozen source units')
        need(selector['asset'] in self.assets and selector['source_pin']==self.assets[selector['asset']]['pin'],
             'selector identifies the exact selected source body before opening')
        scale=finite(selector['scale']);need(scale!=0,'explicit nonzero original unit conversion')
        value=select(self.open(selector['asset']),selector['steps'])
        if selector['units']=='literal_indicator':
            need(selector['shape']==[] and selector['scale']==1 and selector['clock_rule'] is None,
                 'literal indicator has no numeric/time transform')
            raw=value.item() if getattr(value,'shape',None)==() else value
            need(type(raw) in (bool,int,float) and raw in (0,1),'literal source indicator domain')
            return int(raw)
        if selector['units']=='nanoseconds':
            need(selector['shape']==[] and selector['scale']==1,'clock has its separate declared rational conversion')
            return clock_value(value,selector['clock_rule'])
        need(selector['clock_rule'] is None,'non-clock selector cannot add a hidden time conversion')
        if selector['shape']==[]:return finite(scalar(value)*scale)
        need(type(selector['shape']) is list and len(selector['shape'])==1,'explicit complete vector shape')
        return [finite(v*scale) for v in vector(value,selector['shape'][0],selector['axis'])]

    def close(self):
        self.opened.clear()
        pending=list(self.live.values());self.live.clear()
        finish_owned([('MAT live reservation release',lambda token=token:self.ledger.release_live(token)) for token in pending])

def extract_private(study,mapping,reader):
    """Source-owned extraction, not an injected ready-made row/prediction API."""
    exact_fields(mapping,('schema','study_structure_pin','queries','field_records','source_audit_pin'),'complete original projection mapping')
    from ach_util import pin
    structural={k:study[k] for k in ('task','animals','paired_animals','sessions','queries','eligible_sessions')}
    need(mapping['schema']=='ach_original_source_projection_v1' and mapping['study_structure_pin']==pin(structural),
         'same original full study field mapping')
    require_pin(mapping['source_audit_pin'])
    need(set(mapping['queries'])=={q['id'] for q in study['queries']},'every original eligible query')
    targets={};epochs={};fields={}
    for q in study['queries']:
        m=mapping['queries'][q['id']]
        exact_fields(m,('target','epochs','observation_end','target_available'),'actual target/channel/clock selectors')
        observed=reader.read(m['observation_end']);available=reader.read(m['target_available'])
        need(observed==q['observation_end_ns'] and available==q['target_available_ns'],
             'authentic absolute clocks equal admitted canonical ledger')
        need(m['observation_end']['units']==m['target_available']['units']=='nanoseconds' and
             m['target']['units']=='seconds','exact clock and protected target units')
        need(m['observation_end']['clock_rule']['rounding'] in ('exact','floor') and
             m['target_available']['clock_rule']['rounding'] in ('exact','ceil'),
             'observation cannot move later and target release cannot move earlier')
        seconds=reader.read(m['target']);need(seconds>0,'source-defined positive protected target')
        t={'animal':q['animal'],'session':q['session'],'trial':q['target_trial'],'kind':q['target_kind'],
           'available_ns':q['target_available_ns'],'seconds':seconds}
        need(q['target_key'] not in targets or targets[q['target_key']]==t,'same physical target source truth')
        targets[q['target_key']]=t;channels={}
        need(set(m['epochs'])=={'D','ACh'},'complete channel mapping/disposition')
        for index,name in enumerate(('D','ACh')):
            e=m['epochs'][name]
            if q['channel_mask'][index]==0:need(e is None,'genuinely absent modality');channels[name]=None
            else:
                exact_fields(e,('times','values'),'actual channel epoch selectors')
                need(e['times']['units']=='relative_seconds','original neural epoch timing')
                channels[name]={'times':reader.read(e['times']),'values':reader.read(e['values'])}
        epochs[q['id']]=channels
    for m in mapping['field_records']:
        exact_fields(m,('animal','session','trial','field','value','observed','available','target_aliases','source_pin'),
                     'complete privately audited behavior field mapping')
        key=(m['animal'],m['session'],m['trial'],m['field']);need(key not in fields,'unique private source field')
        require_pin(m['source_pin']);need(m['observed']['units']=='literal_indicator','declared observation indicator')
        observed=reader.read(m['observed']);need(observed in (0,1),'literal source observation mask')
        need(m['available']['units']=='nanoseconds' and m['available']['clock_rule']['rounding'] in ('exact','ceil'),
             'behavior availability cannot move earlier')
        fields[key]={'value':reader.read(m['value']) if observed else None,'observed':bool(observed),
            'available_ns':reader.read(m['available']),'target_aliases':list(m['target_aliases']),'source_pin':m['source_pin']}
        integer(fields[key]['available_ns'])
    return {'targets':targets,'epochs':epochs,'fields':fields,'source_mapping_pin':pin(mapping),
            'actual_semantic_authenticity_requires_independent_admission':True}
