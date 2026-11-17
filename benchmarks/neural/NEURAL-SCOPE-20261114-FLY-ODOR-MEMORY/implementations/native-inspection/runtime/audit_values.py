"""Independent Fly source-to-report audit, conditional on pinned shared MAT traversal.

No authentic input is opened at import. The producer's archive/report functions
are never called. A private clone of its exact structural matrix bytecode replaces
only the trial callback; selected payload unpacking and all summaries are ours.
"""
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys
import time
import types
import zipfile
from fractions import Fraction

CONSUMER_ROOT=Path(__file__).resolve().parent/'inspector'
SOURCE_PINS={
 'structural_stream.py':(10793,'dbeaee4950f7836e05e5b5b16293fa3e83d5de2b61cda5f89ab7392ce4d44577'),
 'optional_inputs.py':(3346,'5b77dd933d18e49dc5288120923de02a5847566bb04c3576d3b7130e28da4ff6'),
 'diagnostics.py':(7053,'8e82fb14f735de65d7b85c47dba60512a97093c71497a6bf6f850dc2cd18d6e8'),
 'value_consumer.py':(27350,'3096cc19ae99d302d41fdf29a40d129cbd7c1d797bfdaa85c5af9583e2ea089c')}
PLAN_BYTES=3419523
PLAN_SHA='7eb06156b8ce98b9bb00f078ef64e8b57e99c5e1e234dc4c7222372a4d40b10c'
OPTIONAL_BYTES=125940
OPTIONAL_SHA='e25d53f30c0404164f89553cf414c92c145bcb33eec341973cd4a43dc88ac034'
OPTIONAL=('shift','allo_pos')
ARCHIVE_BYTES=789165393
ARCHIVE_SHA='6c263d5037fef4e84c1ed33fa03b6673da35cb8a8cb3aace340a1db58b300302'
JSON_TRIAL_CAP=4*1024*1024
JSON_SMALL_CAP=65536
FIELDS=('filename','thorname','thortime','fps','wind_speed','winddir','wind_on','odor_on','closed_loop',
        'calc_ts','wind','odor','calc_heading','calc_speed','frame','dff_ts','dff_green','dff_red','dff_diff',
        'plume_t','plume_x','plume_y','plume_speed','plume_valve')
STRINGS=('filename','thorname','thortime')
SCALARS=('fps','wind_speed','winddir','wind_on','odor_on','closed_loop')
BEHAVIOR=('wind','odor','calc_heading','calc_speed','plume_t','plume_x','plume_y','plume_speed','plume_valve')
PRIMITIVES={1:('b',1),2:('B',1),3:('h',2),4:('H',2),5:('i',4),6:('I',4),
            7:('f',4),9:('d',8),12:('q',8),13:('Q',8)}
INT_RANGES={8:(-2**7,2**7-1),9:(0,2**8-1),10:(-2**15,2**15-1),11:(0,2**16-1),
            12:(-2**31,2**31-1),13:(0,2**32-1),14:(-2**63,2**63-1),15:(0,2**64-1)}
C=None

class AuditError(ValueError):pass
def need(ok,code):
    if not ok:raise AuditError(code)
def identity(s):
    return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
def exact_json(a,b,code):
    need(json.dumps(a,sort_keys=True,separators=(',',':'),allow_nan=False)==
         json.dumps(b,sort_keys=True,separators=(',',':'),allow_nan=False),code)
def strict_pairs(items):
    out={}
    for key,value in items:
        need(key not in out,'duplicate_json_key')
        out[key]=value
    return out
def reject_constant(_):raise AuditError('nonstandard_json_constant')
def decode(raw):
    try:return json.loads(raw.decode('ascii'),object_pairs_hook=strict_pairs,parse_constant=reject_constant)
    except AuditError:raise
    except (UnicodeError,ValueError):raise AuditError('invalid_ascii_json') from None

def load_consumer():
    global C
    if C is not None:return C
    bodies={}
    for name,(size,digest) in SOURCE_PINS.items():
        p=CONSUMER_ROOT/name
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as f:
            s=os.fstat(f.fileno())
            need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size==size,'source_extent')
            b=f.read(size+1)
            need(identity(s)==identity(os.fstat(f.fileno())),'source_open_custody')
        need(len(b)==size and hashlib.sha256(b).hexdigest()==digest,'source_sha')
        need(identity(s)==identity(p.lstat()),'source_custody')
        bodies[name]=b
    sentinel=object()
    aliases=('structural_stream','optional_inputs','diagnostics')
    old={name:sys.modules.get(name,sentinel) for name in aliases}
    try:
        for name in aliases:
            module=types.ModuleType(name);module.__file__=str(CONSUMER_ROOT/(name+'.py'))
            sys.modules[name]=module
            exec(compile(bodies[name+'.py'],module.__file__,'exec'),module.__dict__)
        consumer=types.ModuleType('_fly_audit_pinned_consumer')
        consumer.__file__=str(CONSUMER_ROOT/'value_consumer.py')
        exec(compile(bodies['value_consumer.py'],consumer.__file__,'exec'),consumer.__dict__)
    finally:
        for name in aliases:
            if old[name] is sentinel:sys.modules.pop(name,None)
            else:sys.modules[name]=old[name]
    C=consumer
    return C

def finite(x):return type(x) is int or math.isfinite(x)
def spelling(x):
    if type(x) is int:return {'integer':str(x)}
    if not math.isfinite(x):return {'nonfinite':'nan' if math.isnan(x) else '+inf' if x>0 else '-inf'}
    return {'binary_float_hex':x.hex()}
def ranges(indices):
    out=[]
    for i in indices:
        if out and out[-1][1]==i:out[-1][1]=i+1
        else:out.append([i,i+1])
    return out
def summary(values):
    positions=[i for i,x in enumerate(values) if finite(x)]
    observed=[values[i] for i in positions]
    return dict(elements=len(values),finite=len(observed),nan=sum(isinstance(x,float) and math.isnan(x) for x in values),
        positive_infinity=sum(x==math.inf for x in values),negative_infinity=sum(x==-math.inf for x in values),
        finite_index_runs=ranges(positions),zero=sum(x==0 for x in observed),
        minimum=spelling(min(observed)) if observed else None,maximum=spelling(max(observed)) if observed else None)
def clock(values):
    result=summary(values)
    bad=[i for i in range(1,len(values)) if finite(values[i-1]) and finite(values[i]) and values[i]<=values[i-1]]
    increasing=[]
    for i,x in enumerate(values):
        if not finite(x):continue
        if increasing and increasing[-1][1]==i and values[i-1]<x:increasing[-1][1]=i+1
        else:increasing.append([i,i+1])
    result.update(nonincreasing_edges_right_index=bad,strictly_increasing_finite_runs=increasing,gap_threshold_applied=False)
    return result
def commands(values,times):
    events=[];missing=0
    for left_index,(a,b) in enumerate(zip(values,values[1:])):
        if not finite(a) or not finite(b):missing+=1;continue
        if a==b:continue
        right_index=left_index+1
        left=times[left_index] if left_index<len(times) else None
        right=times[right_index] if right_index<len(times) else None
        events.append(dict(left_index=left_index,right_index=right_index,**{'from':spelling(a),'to':spelling(b)},
            left_clock=None if left is None else spelling(left),right_clock=None if right is None else spelling(right),
            clock_bracket_strict_finite=left is not None and right is not None and finite(left) and finite(right) and left<right))
    return dict(changes=events,adjacent_pairs_with_nonfinite_command=missing,command_elements=len(values),
        clock_elements=len(times),physical_offset_inference=False)
def frames(values,times):
    integral=[finite(x) and (type(x) is int or x.is_integer()) for x in values]
    domain=[ok and 1<=x<=len(times) for x,ok in zip(values,integral)]
    seen=set();duplicates=[];jumps=[]
    for i,x in enumerate(values):
        if not domain[i]:continue
        k=int(x)
        if k in seen:duplicates.append(i)
        seen.add(k)
        if i and domain[i-1] and k!=int(values[i-1])+1:
            jumps.append(dict(right_index=i,previous=str(int(values[i-1])),current=str(k)))
    support={i+1 for i,x in enumerate(times) if finite(x)}
    integers=[int(x) for x,ok in zip(values,integral) if ok]
    return dict(elements=len(values),minimum_integral_frame=str(min(integers)) if integers else None,
        maximum_integral_frame=str(max(integers)) if integers else None,
        nonintegral_or_nonfinite_indices=[i for i,ok in enumerate(integral) if not ok],
        outside_saved_clock_domain_indices=[i for i,ok in enumerate(domain) if not ok],
        duplicate_occurrence_indices=duplicates,nonconsecutive_edges=jumps,
        padding_support_matches_finite_saved_clock=all(domain) and not duplicates and seen==support,
        frame_indices_absent_from_finite_saved_clock=sorted(seen-support),
        finite_saved_clock_positions_absent_from_frame=sorted(support-seen),positions_one_based=True,no_alignment_or_repair=True)

def exact_ratio(x):
    x=Fraction(x)
    return dict(numerator=str(x.numerator),denominator=str(x.denominator))

def independent_clock_diagnostics(values,fps):
    distribution={};bad=[];missing=0
    nominal=Fraction(1)/Fraction(fps) if finite(fps) and fps>0 else None
    comparisons=dict(below=0,equal=0,above=0,above_two=0)
    for right in range(1,len(values)):
        a,b=values[right-1],values[right]
        if not finite(a) or not finite(b):missing+=1;continue
        gap=Fraction(b)-Fraction(a)
        if gap>0:
            distribution[gap]=distribution.get(gap,0)+1
            if nominal is not None:
                comparisons['below' if gap<nominal else 'above' if gap>nominal else 'equal']+=1
                if gap>nominal*2:comparisons['above_two']+=1
        else:
            bad.append(dict(left_index=right-1,right_index=right,left=spelling(a),right=spelling(b),
                            difference_seconds=exact_ratio(gap)))
    return dict(positive_gap_distribution=[dict(gap_seconds=exact_ratio(g),count=distribution[g])
                                          for g in sorted(distribution)],
        positive_edges=sum(distribution.values()),nonincreasing_edges=bad,
        adjacent_edges_with_nonfinite_endpoint=missing,declared_fps=spelling(fps),
        nominal_interval_seconds=None if nominal is None else exact_ratio(nominal),
        positive_gap_vs_declared_interval=None if nominal is None else comparisons,
        strict_finite_runs=clock(values)['strictly_increasing_finite_runs'],
        clock_repaired=False,sampling_rate_inferred=False,gap_comparison_is_not_eligibility=True)

def independent_command_boundaries(values,times):
    groups=ranges([i for i,x in enumerate(values) if finite(x)])
    rows=[]
    for begin,end in groups:
        rows.append(dict(start_index=begin,end_index_exclusive=end,
            first_state=spelling(values[begin]),last_state=spelling(values[end-1]),
            left_state_nonzero_without_observed_onset=values[begin]!=0,
            right_state_nonzero_without_observed_offset=values[end-1]!=0,
            left_missing_command_boundary=begin!=0,right_missing_command_boundary=end!=len(values),
            first_clock=spelling(times[begin]) if begin<len(times) else None,
            last_clock=spelling(times[end-1]) if end<=len(times) else None))
    return dict(finite_command_runs=rows,command_elements=len(values),clock_elements=len(times),
                length_match=len(values)==len(times),physical_censoring_not_inferred=True)

def upper_bound(values,threshold):
    """Independent binary search for the first represented value > threshold."""
    left,right=0,len(values)
    while left<right:
        middle=(left+right)//2
        if values[middle]<=threshold:left=middle+1
        else:right=middle
    return left

def independent_window(groups,anchor,before,after):
    low,high=anchor-before,anchor+after
    support=[]
    for begin,end,values in groups:
        a,b=upper_bound(values,low),upper_bound(values,high)
        bracket=values[0]<=low and values[-1]>=high
        if a<b or bracket:
            support.append(dict(clock_run=[begin,end],sample_range=[begin+a,begin+b],
                sample_count=b-a,run_brackets_both_boundaries=bracket))
    return dict(lower_open_seconds=exact_ratio(low),upper_closed_seconds=exact_ratio(high),
                original_run_support=support,coverage_fraction=None,eligibility=None)

def independent_odor_windows(command,times):
    groups=[(a,b,[Fraction(x) for x in times[a:b]])
            for a,b in clock(times)['strictly_increasing_finite_runs']]
    rows=[]
    for right,(a,b) in enumerate(zip(command,command[1:]),1):
        if not finite(a) or not finite(b) or a==0 or b!=0:continue
        valid=right<len(times) and finite(times[right-1]) and finite(times[right]) and times[right-1]<times[right]
        endpoints=None
        if valid:
            endpoints=[]
            for label,index in [('left',right-1),('right',right)]:
                anchor=Fraction(times[index])
                endpoints.append(dict(endpoint=label,anchor_seconds=exact_ratio(anchor),
                    history_10s=independent_window(groups,anchor,10,0),
                    goal_1s=independent_window(groups,anchor,1,0),
                    horizon_5s=independent_window(groups,anchor,0,5)))
        rows.append(dict(left_index=right-1,right_index=right,strict_finite_clock_bracket=valid,
            anchor_interpretation='both_observed_command_bracket_endpoints_not_physical_offset',
            endpoint_windows=endpoints))
    return dict(observed_nonzero_to_zero_changes=rows,control_pseudo_offsets=None,
                physical_offsets=None,outcome_values_read_for_diagnostics=False,eligibility_assigned=False)

def independent_join_diagnostics(values):
    times=values['calc_ts']
    return dict(behavior_clock=independent_clock_diagnostics(times,values['fps'][0]),
        imaging_clock=independent_clock_diagnostics(values['dff_ts'],float('nan')),
        imaging_clock_status='released_nominal_clock_not_hardware_qualified',
        command_boundaries={k:independent_command_boundaries(values[k],times) for k in ('odor','wind','plume_valve')},
        odor_command_window_boundaries=independent_odor_windows(values['odor'],times),
        biological_animal=None,condition=None,physical_offsets=None,trial_retained=True,scientific_admission=False)

def join_optional_metadata(plan,supplement):
    """Independent descriptor join; never calls the producer's optional loader."""
    need(supplement['schema']=='fly-native-optional-descriptors-v1' and
         supplement['base_plan_bytes']==PLAN_BYTES and supplement['base_plan_sha256']==PLAN_SHA,'optional_base_identity')
    base,extra=plan['files'],supplement['files']
    need(len(base)==len(extra)==42 and sum(x['trial_count'] for x in base)==1345,'full_optional_population')
    need(len({x['archive_member_id'] for x in base})==42,'unique_plan_members')
    totals=dict.fromkeys(OPTIONAL,0);file_totals=dict.fromkeys(OPTIONAL,0);joined=[]
    classes={'double','single','int8','uint8','int16','uint16','int32','uint32','int64','uint64'}
    for source,addition in zip(base,extra):
        need(all(source[k]==addition[k] for k in ('archive_member_id','official_lookup_index','trial_count')),'optional_file_identity')
        need(len(source['trials'])==len(addition['trials'])==source['trial_count'],'optional_trial_count')
        rows=[];presence=None
        for index,(old,row) in enumerate(zip(source['trials'],addition['trials'])):
            need(old['trial_index_zero_based']==row['trial_index_zero_based']==index,'optional_trial_order')
            fields=row['fields'];need(set(fields)==set(OPTIONAL),'optional_dispositions')
            available=frozenset(k for k in OPTIONAL if fields[k] is not None)
            if presence is None:
                presence=available
                for k in available:file_totals[k]+=1
            need(available==presence,'optional_uniform_source_presence')
            for k in available:
                node=fields[k]
                need(set(node)=={'class','dims','complex','logical'} and node['class'] in classes
                     and node['complex'] is False and type(node['logical']) is bool,'optional_typed_descriptor')
                shape=node['dims']
                need(type(shape) is list and 2<=len(shape)<=16 and
                     all(type(n) is int and n>=0 for n in shape) and math.prod(shape)<=20000,'optional_shape')
                totals[k]+=1
            rows.append(dict(old,optional_fields=fields))
        joined.append(dict(source,trials=rows))
    need(all(totals[k]==235 and file_totals[k]==7 for k in OPTIONAL),'optional_complete_support')
    return dict(plan,files=joined)

def trial(values,typed,original):
    available={k for k in OPTIONAL if original['optional_fields'][k] is not None}
    need(set(values)==set(typed)==set(FIELDS)|available,'all_trial_fields')
    for k in SCALARS:need(len(values[k])==1,'scalar_extent')
    times=values['calc_ts'];shape=typed['dff_green']['dims']
    by_row={}
    for k in ('dff_green','dff_red','dff_diff'):
        dims=typed[k]['dims']
        if len(dims)==2 and dims[0]:
            counts=[0]*dims[0]
            for i,x in enumerate(values[k]):counts[i%dims[0]]+=finite(x)
            by_row[k]=counts
        else:by_row[k]=None
    result=dict(trial_index_zero_based=original['trial_index_zero_based'],condition=None,biological_animal=None,
        physical_offsets=None,fields={k:typed[k] for k in FIELDS},saved_strings={k:values[k] for k in STRINGS},
        scalars={k:spelling(values[k][0]) for k in SCALARS},
        clocks={k:clock(values[k]) for k in ('calc_ts','dff_ts')},
        virtual_plume_frame_index=summary(values['plume_t']),frame=frames(values['frame'],times),
        behavior_length_mismatches=[k for k in BEHAVIOR if len(values[k])!=len(times)],
        commands={k:commands(values[k],times) for k in ('odor','wind','plume_valve')},
        literal_declaration_checks={scalar:dict(declared_scalar=spelling(values[scalar][0]),
            vector_has_finite_nonzero=any(finite(x) and x!=0 for x in values[vector]),
            semantic_inconsistency_not_inferred=True) for scalar,vector in (('odor_on','odor'),('wind_on','wind'))},
        imaging_shape_matches_own_clock=len(shape)==2 and shape[1]==len(values['dff_ts']) and
            typed['dff_red']['dims']==shape and typed['dff_diff']['dims']==shape,
        imaging_empty=any(len(values[k])==0 for k in ('dff_ts','dff_green','dff_red','dff_diff')),
        imaging_finite_by_source_row=by_row,disposition='native_values_inspected_no_scientific_eligibility_assigned')
    optional={}
    for k in OPTIONAL:
        if k not in available:
            optional[k]=dict(source_present=False,descriptor=None,values_or_changes=None)
        else:
            optional[k]=dict(source_present=True,descriptor=typed[k],
                values_or_changes=[spelling(x) for x in values[k]] if k=='shift' else commands(values[k],times),
                command_boundary_diagnostics=None if k=='shift' else independent_command_boundaries(values[k],times),
                condition_not_inferred=True)
    result['optional_fields']=optional
    result['source_join_diagnostics']=independent_join_diagnostics(values)
    return result

class ReportStream:
    """Known producer JSONL order, bounded one-trial value; duplicate keys refused."""
    def __init__(self,path,budget):
        self.fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);self.f=os.fdopen(self.fd,'rb');self.before=os.fstat(self.fd)
        try:
            need(stat.S_ISREG(self.before.st_mode) and self.before.st_nlink==1 and
                 stat.S_IMODE(self.before.st_mode)==0o600 and self.before.st_size<=budget.caps['report_bytes'],'private_report_extent')
        except BaseException:
            self.f.close()
            raise
        self.budget=budget;self.buf=b'';self.at=0;self.read_bytes=0;self.position=0;self.sha=hashlib.sha256()
        self.trials=0
    def close(self):self.f.close()
    def peek(self):
        if self.at==len(self.buf):
            self.budget.check()
            self.buf=self.f.read(min(8192,self.budget.caps['report_bytes']+1-self.read_bytes));self.at=0
            self.read_bytes+=len(self.buf);self.sha.update(self.buf)
            need(self.read_bytes<=self.budget.caps['report_bytes'],'report_total_cap')
        return self.buf[self.at:self.at+1]
    def take(self):
        b=self.peek();need(bool(b),'truncated_report');self.at+=1;self.position+=1;return b
    def char(self,b):need(self.take()==b,'report_delimiter')
    def value(self,cap=JSON_SMALL_CAP):
        raw=bytearray();stack=[];inside=False;escape=False
        first=self.peek();need(first not in (b'',b' ',b'\t',b'\r',b'\n'),'unexpected_report_whitespace')
        while True:
            b=self.peek()
            if not inside and not stack and raw and b in (b'',b',',b'}',b']',b'\n'):break
            b=self.take();raw.extend(b);need(len(raw)<=cap,'report_value_cap')
            if inside:
                if escape:escape=False
                elif b==b'\\':escape=True
                elif b==b'"':inside=False
            elif b==b'"':inside=True
            elif b in (b'{',b'['):
                stack.append(b);need(len(stack)<=64,'report_depth')
            elif b in (b'}',b']'):
                need(stack and stack.pop()==(b'{' if b==b'}' else b'['),'report_bracket')
                if not stack:break
            elif not stack and first==b'"' and not inside:break
            if first==b'"' and raw[-1:]==b'"' and len(raw)>1 and not inside:break
        return decode(bytes(raw))
    def record(self):
        value=self.value();self.char(b'\n');return value
    def keyed(self,key,value=None,compare=True):
        exact_json(self.value(),key,'file_key_order');self.char(b':');got=self.value()
        if compare:exact_json(got,value,'file_metadata')
        return got
    def begin_file(self,expected):
        self.char(b'{');self.keyed('record_type','file')
        for key,value in [('archive_member_id',expected['archive_member_id']),('official_lookup_index',expected['official_lookup_index']),
                          ('population_label',expected['population_label']),('trial_count',expected['trial_count'])]:
            self.char(b',');self.keyed(key,value)
        self.char(b',');exact_json(self.value(),'trials','trials_key');self.char(b':');self.char(b'[');self.trials=0
    def next_trial(self):
        if self.trials:self.char(b',')
        item=self.value(JSON_TRIAL_CAP);self.trials+=1;return item
    def finish_file(self,tail):
        self.char(b']')
        for key,value in tail.items():
            self.char(b',');self.keyed(key,value)
        self.char(b'}');self.char(b'\n')
    def closed(self):
        need(self.peek()==b'','trailing_report')
        need(self.read_bytes==self.before.st_size,'report_extent_changed')
        need(identity(os.fstat(self.fd))==identity(self.before),'report_custody')
        return dict(bytes=self.read_bytes,sha256=self.sha.hexdigest())

def make_reader(raw,expected,budget,report,ledger):
    consumer=load_consumer()
    class AuditMat(consumer.ValueMat5):
        def __init__(self):
            super().__init__(consumer.Cursor(consumer.HashedStream(raw),budget,charge='zip_bytes'),budget,expected)
            self.wrapper=self.c.raw
            original=consumer.ValueMat5.matrix
            need(not original.__code__.co_freevars,'unexpected_shared_matrix_closure')
            namespace=dict(original.__globals__);namespace['trial_report']=self.finish_trial
            clone=types.FunctionType(original.__code__,namespace,original.__name__,original.__defaults__)
            self.matrix=types.MethodType(clone,self)
        def payload(self,source,length,kind,cls,logical,dims,selected):
            if not selected:source.skip(length);return None,None
            size=math.prod(dims)
            need(size<=20000 and length<=160000,'selected_span_cap')
            budget.add('selected_values',size);budget.check()
            data=source.exact(length);ledger['selected_payload_bytes']+=length
            typed=dict(primitive_tag=kind,byte_order=self.endian,payload_bytes=length,payload_sha256=hashlib.sha256(data).hexdigest())
            if cls==4:
                need(len(dims)==2 and (dims[0]==1 or size==0),'character_shape')
                if kind in (1,2,16):
                    encoding='utf-8' if kind==16 else 'latin-1';decoded=data.decode(encoding,'strict')
                    need(len(decoded)==size,'character_size')
                else:
                    width=2 if kind in (4,17) else 4
                    need(length==size*width,'character_units')
                    encoding=('utf-16-' if width==2 else 'utf-32-')+('le' if self.endian=='<' else 'be')
                    decoded=data.decode(encoding,'strict')
                typed['text_encoding']=encoding
            else:
                fmt,width=PRIMITIVES[kind];need(length==size*width,'numeric_size')
                decoded=list(struct.unpack(self.endian+str(size)+fmt,data)) if size else []
                for value in decoded:
                    if logical:need(value==0 or value==1,'logical_domain')
                    if cls in INT_RANGES:
                        lo,hi=INT_RANGES[cls]
                        need(finite(value) and lo<=value<=hi and (type(value) is int or value.is_integer()),'integer_class_domain')
                    elif cls in (6,7) and finite(value):
                        try:rounded=float(value) if cls==6 else struct.unpack('f',struct.pack('f',value))[0]
                        except (OverflowError,struct.error):raise AuditError('float_class_overflow') from None
                        need(rounded==value,'float_class_precision')
                typed['summary']=summary(decoded)
            budget.check();return decoded,typed
        def finish_trial(self,values,typed,original):
            budget.check()
            wanted=trial(values,typed,original)
            supplied=report.next_trial()
            exact_json(supplied,wanted,'trial_summary_mismatch')
            frame=wanted['frame'];compact=dict(maximum=frame['maximum_integral_frame'],
                all_integral=not frame['nonintegral_or_nonfinite_indices'],
                clock_length=wanted['clocks']['calc_ts']['elements'])
            ledger['trials_compared']+=1;ledger['fields_compared']+=len(FIELDS)
            present=sum(original['optional_fields'][k] is not None for k in OPTIONAL)
            ledger['optional_fields_compared']+=present
            ledger['optional_absent_slots']+=len(OPTIONAL)-present
            ledger['source_join_diagnostics_compared']+=1
            del supplied,wanted
            budget.check();return compact
        def inspect_independent(self):
            consumer.Mat5.run(self)
            need(len(self.rows)==expected['trial_count'] and not self.values,'trial_closure')
            maxima=[int(x['maximum']) for x in self.rows if x['maximum'] is not None]
            integral=all(x['all_integral'] for x in self.rows)
            maximum=max(maxima) if maxima and integral else None
            return dict(file_wide_padding_extent_hypothesis=dict(
                maximum_integral_frame=None if maximum is None else str(maximum),
                all_frames_integral_finite=integral,
                saved_clock_lengths_equal_file_maximum=[x['clock_length']==maximum for x in self.rows],
                writer_application_not_inferred=True),
                complete_mat_stream=True,byte_order=self.endian,numeric_values_inspected=True,
                scientific_admission=False,MAT_bytes=self.wrapper.bytes,MAT_sha256=self.wrapper.sha.hexdigest())
    return AuditMat()

class ReadLedger:
    def __init__(self,handle,ledger,key):self.handle,self.ledger,self.key=handle,ledger,key
    def read(self,n=-1):
        if n == -1:
            n = ARCHIVE_BYTES-self.handle.tell()
            need(0<=n<=131072,'bounded_zip_tail_read')
        need(type(n) is int and n>=0,'bounded_archive_read')
        value=self.handle.read(n);self.ledger[self.key]+=len(value);return value
    def __getattr__(self,k):return getattr(self.handle,k)

def audit_archive(archive_path,plan_path,report_path,*,optional_path,budget=None):
    consumer=load_consumer();budget=budget or consumer.Budget()
    ledger=dict(plan_bytes=0,optional_plan_bytes=0,archive_identity_bytes=0,archive_zip_reads_bytes=0,
                selected_payload_bytes=0,trials_compared=0,fields_compared=0,
                optional_fields_compared=0,optional_absent_slots=0,source_join_diagnostics_compared=0)
    with open(plan_path,'rb') as f:pb=f.read(PLAN_BYTES+1)
    ledger['plan_bytes']=len(pb)
    need(len(pb)==PLAN_BYTES and hashlib.sha256(pb).hexdigest()==PLAN_SHA,'fixed_complete_plan')
    with open(optional_path,'rb') as f:ob=f.read(OPTIONAL_BYTES+1)
    ledger['optional_plan_bytes']=len(ob)
    need(len(ob)==OPTIONAL_BYTES and hashlib.sha256(ob).hexdigest()==OPTIONAL_SHA,'fixed_optional_plan')
    plan=join_optional_metadata(json.loads(pb),json.loads(ob))
    del pb,ob
    report=ReportStream(report_path,budget)
    descriptor=None
    try:
        header=report.record()
        exact_json(header,dict(record_type='header',schema='fly-complete-native-joins-census-jsonl-v2',
            operand_plan_sha256=PLAN_SHA,archive_sha256=ARCHIVE_SHA,
            optional_plan_bytes=OPTIONAL_BYTES,optional_plan_sha256=OPTIONAL_SHA,scientific_admission=False,
            condition_map=None,animal_map=None,physical_offsets=None,byte_caps=budget.caps),'report_header')
        descriptor=os.open(archive_path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(descriptor,'rb') as handle:
            descriptor=None;before=os.fstat(handle.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==ARCHIVE_BYTES,'fixed_archive_extent')
            sha=hashlib.sha256();left=ARCHIVE_BYTES
            while left:
                budget.check();block=handle.read(min(left,65536));ledger['archive_identity_bytes']+=len(block)
                need(block,'archive_truncated');sha.update(block);left-=len(block)
            extra=handle.read(1);ledger['archive_identity_bytes']+=len(extra)
            need(not extra and sha.hexdigest()==ARCHIVE_SHA,'fixed_archive_hash')
            handle.seek(0)
            with zipfile.ZipFile(ReadLedger(handle,ledger,'archive_zip_reads_bytes')) as archive:
                infos=archive.infolist();by_offset={x.header_offset:x for x in infos}
                need(len(by_offset)==len(infos),'duplicate_zip_offset')
                for expected in plan['files']:
                    budget.check();m=expected['native_member'];info=by_offset.get(m['storage_locator']['local_header_offset'])
                    need(info is not None and info.compress_size==m['compressed_bytes'] and
                         info.file_size==m['declared_uncompressed_bytes'] and info.compress_type==m['compression'] and
                         info.CRC==m['crc32'] and not info.is_dir() and not info.flag_bits&1,'member_identity')
                    report.begin_file(expected)
                    with archive.open(info) as raw:
                        reader=make_reader(raw,expected,budget,report,ledger);tail=reader.inspect_independent()
                        need(raw.read(1)==b'' and tail['MAT_bytes']==info.file_size,'member_crc_extent')
                    report.finish_file(tail);del reader,tail
            need(identity(before)==identity(os.fstat(handle.fileno())),'archive_custody')
        footer_start=report.position
        expected_counts=dict(budget.counts);expected_counts['report_bytes']=footer_start
        exact_json(report.record(),dict(record_type='footer',complete_native_census=True,file_count=42,trial_count=1345,
            scientific_admission=False,counters_before_footer=expected_counts),'report_footer')
        report_pin=report.closed()
        need(ledger['trials_compared']==1345 and ledger['fields_compared']==32280 and
             ledger['optional_fields_compared']==470 and ledger['optional_absent_slots']==2220 and
             ledger['source_join_diagnostics_compared']==1345,'comparison_population')
        ledger.update(report_read_bytes=report.read_bytes,zip_member_uncompressed_bytes=budget.counts['zip_bytes'],
            inner_mat_inflated_bytes=budget.counts['mat_expanded'],nodes=budget.counts['nodes'],
            selected_values=budget.counts['selected_values'])
        ledger['explicit_file_reads']=ledger['plan_bytes']+ledger['optional_plan_bytes']+ledger['archive_identity_bytes']+ledger['archive_zip_reads_bytes']+ledger['report_read_bytes']
        ledger['logical_inflation_and_selected_span_debits']=ledger['zip_member_uncompressed_bytes']+ledger['inner_mat_inflated_bytes']+ledger['selected_payload_bytes']
        return dict(schema='fly-independent-native-joins-source-report-audit-v2',status='PASS',files=42,trials=1345,
            fields_compared=32280,optional_fields_compared=470,optional_absent_slots=2220,
            source_join_diagnostics_compared=1345,optional_plan_sha256=OPTIONAL_SHA,
            report=report_pin,archive_sha256=ARCHIVE_SHA,plan_sha256=PLAN_SHA,
            full_source_and_report_comparison=True,scientific_admission=False,
            physical_offset_inference=False,animal_inference=False,shared_structural_parser=True,
            shared_parser_scope='Pinned tag/matrix/container/inflater traversal; independent payload unpack and all report computations.',
            counters=ledger)
    finally:
        if descriptor is not None:os.close(descriptor)
        report.close()

def write_result(path,record):
    data=(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    need(len(data)<=65536,'audit_result_cap')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('archive','plan','optional-plan','report','output'):parser.add_argument('--'+flag,required=True)
    args=parser.parse_args();start=time.monotonic()
    need(not Path(args.output).exists() and not Path(args.output).is_symlink(),'fresh_audit_output')
    try:
        result=audit_archive(args.archive,args.plan,args.report,optional_path=args.optional_plan)
    except Exception as error:
        write_result(args.output,dict(schema='fly-independent-native-joins-source-report-audit-v2',status='FAILED',
            error_type=type(error).__name__,error_code=str(error) if isinstance(error,AuditError) else 'shared_parser_or_io_refusal',
            scientific_admission=False))
        raise SystemExit(1)
    result['sampled_elapsed_seconds_before_result_write']=time.monotonic()-start
    write_result(args.output,result)
    print(json.dumps({'status':'PASS','files':42,'trials':1345,'fields_compared':32280,
        'optional_fields_compared':470,'optional_absent_slots':2220,
        'source_join_diagnostics_compared':1345,'optional_plan_sha256':OPTIONAL_SHA,
        'scientific_admission':False}))
