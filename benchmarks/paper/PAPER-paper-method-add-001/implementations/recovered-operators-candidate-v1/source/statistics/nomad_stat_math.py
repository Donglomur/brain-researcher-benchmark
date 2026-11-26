"""Bounded exact arithmetic over supplied binary64 values; no historical defaults."""
import hashlib
import json
import math
from fractions import Fraction

CAPS=('input_cells','items','integer_bits','operations','metadata_bytes','copy_bytes',
      'live_bytes','dp_states','json_bytes','json_nodes','identifier_chars')
class Refusal(RuntimeError):
    def __init__(self,code,details=None):
        super().__init__(code);self.code=code;self.details={} if details is None else details

def need(ok,code,**details):
    if not ok:raise Refusal(code,details)

def fields(v,keys):need(type(v) is dict and set(v)==set(keys),'closed_schema',required=list(keys))

def integer(v,name,minimum=0):
    need(type(v) is int and minimum<=v<2**63,'finite_integer',field=name);return v

def pin(v):
    fields(v,('bytes','sha256'));integer(v['bytes'],'pin.bytes')
    need(type(v['sha256']) is str and len(v['sha256'])==64 and all(c in '0123456789abcdef' for c in v['sha256']),'sha256')
    return v

def bytes_pin(v):return {'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}

class Budget:
    def __init__(self,limits):
        fields(limits,CAPS)
        self.limits={k:integer(v,k,1) for k,v in limits.items()}
        self.attempted={k:0 for k in CAPS};self.used={k:0 for k in CAPS};self.live=0;self.peak=0
    def take(self,**amounts):
        for k,v in amounts.items():
            need(k in CAPS and type(v) is int and v>=0,'budget_dimension');self.attempted[k]+=v
        need(all(self.used[k]+v<=self.limits[k] for k,v in amounts.items()),'capacity',amounts=amounts)
        for k,v in amounts.items():self.used[k]+=v
    def hold(self,n):
        need(type(n) is int and n>=0,'live_extent');self.attempted['live_bytes']+=n
        need(self.live+n<=self.limits['live_bytes'],'live_capacity',requested=n)
        self.live+=n;self.peak=max(self.peak,self.live)
    def release(self,n):need(0<=n<=self.live,'owned_live_release');self.live-=n
    def bits(self,n):need(n<=self.limits['integer_bits'],'integer_precision_capacity',bits=n)
    def operands(self,*values):
        for v in values:need(type(v) is Fraction,'exact_rational');self.bits(max(abs(v.numerator).bit_length(),v.denominator.bit_length()))
    def add(self,a,c):
        self.operands(a,c);g=math.gcd(a.denominator,c.denominator)
        ad=a.denominator//g;cd=c.denominator//g
        self.bits(max(abs(a.numerator).bit_length()+cd.bit_length(),abs(c.numerator).bit_length()+ad.bit_length())+1)
        self.bits(ad.bit_length()+c.denominator.bit_length());self.take(operations=1)
        return Fraction(a.numerator*cd+c.numerator*ad,ad*c.denominator)
    def mul(self,a,c):
        self.operands(a,c);g=math.gcd(abs(a.numerator),c.denominator);h=math.gcd(abs(c.numerator),a.denominator)
        an=a.numerator//g;cd=c.denominator//g;cn=c.numerator//h;ad=a.denominator//h
        self.bits(abs(an).bit_length()+abs(cn).bit_length());self.bits(ad.bit_length()+cd.bit_length());self.take(operations=1)
        return Fraction(an*cn,ad*cd)
    def div(self,a,c):
        need(c!=0,'nonzero_denominator');return self.mul(a,Fraction(c.denominator,c.numerator))
    def number(self,v):
        need(type(v) is float and math.isfinite(v),'finite_binary64')
        self.bits(1076);self.take(operations=1);return Fraction(*v.as_integer_ratio())
    def snapshot(self):return {'limits':dict(self.limits),'attempted':dict(self.attempted),'used':dict(self.used),'live':self.live,'peak':self.peak}

def budget(v):return v if type(v) is Budget else Budget(v)

def rational(v,b):
    b.operands(v);b.take(metadata_bytes=2*((b.limits['integer_bits']+3)//4)+32)
    return {'numerator_hex':format(v.numerator,'x'),'denominator_hex':format(v.denominator,'x')}

def from_rational(v,b):
    fields(v,('numerator_hex','denominator_hex'))
    for key in v:
        s=v[key];need(type(s) is str and len(s)<=1+(b.limits['integer_bits']+3)//4,'bounded_rational_encoding')
    n=int(v['numerator_hex'],16);d=int(v['denominator_hex'],16);need(d>0,'rational_denominator')
    b.bits(max(abs(n).bit_length(),d.bit_length()));return Fraction(n,d)

def projected(v):
    try:x=float(v)
    except OverflowError:return {'value':None,'status':'binary64_overflow'}
    if not math.isfinite(x):return {'value':None,'status':'binary64_overflow'}
    if v and x==0:return {'value':None,'status':'binary64_nonzero_underflow'}
    return {'value':x,'status':'finite'}

def _extent(v,b,depth=0,seen=None):
    need(depth<=64,'json_depth');b.take(json_nodes=1)
    if v is None:return 4
    if type(v) is bool:return 5
    if type(v) is int:need(abs(v)<2**63,'metadata_integer_extent');return 21
    if type(v) is float:need(math.isfinite(v),'finite_json');return 32
    if type(v) is str:need(len(v)<=b.limits['identifier_chars'],'string_extent');return 6*len(v)+2
    need(type(v) in (list,tuple,dict),'ordinary_json_type')
    if seen is None:seen=set()
    need(id(v) not in seen,'cyclic_json');seen.add(id(v))
    try:
        if type(v) is dict:
            need(all(type(k) is str for k in v),'string_json_keys')
            n=2+sum(_extent(k,b,depth+1,seen)+_extent(x,b,depth+1,seen)+2 for k,x in v.items())
        else:n=2+sum(_extent(x,b,depth+1,seen)+1 for x in v)
        need(n<=b.limits['json_bytes'],'json_extent');return n
    finally:seen.remove(id(v))

def encode(v,b):
    n=_extent(v,b);b.take(metadata_bytes=2*n,copy_bytes=n);b.hold(3*n)
    try:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
    finally:b.release(2*n)  # retain conservative encoded-body loan until Budget disposal

def decode(raw,b):
    need(type(raw) is bytes and len(raw)<=b.limits['json_bytes'],'bounded_json_bytes')
    b.take(metadata_bytes=65*len(raw),copy_bytes=len(raw));b.hold(65*len(raw))
    def unique(pairs):
        out={}
        for k,v in pairs:need(k not in out,'duplicate_json_key');out[k]=v
        return out
    try:
        value=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(Refusal('nonfinite_json')))
        _extent(value,b);return value
    finally:pass  # decoded-object upper loan retained until Budget disposal

def quantiles(values,policy,limits):
    b=budget(limits);need(policy in ('linear_type7','inverted_cdf'),'explicit_quantile_policy')
    need(type(values) in (list,tuple),'exact_value_sequence');n=len(values);b.take(items=n)
    if not n:return {'status':'undefined_empty','count':0,'policy':policy,'values':None}
    need(all(type(v) is Fraction for v in values),'exact_quantile_values')
    
    for value in values:b.operands(value)
    b.bits(2*max(max(abs(v.numerator).bit_length(),v.denominator.bit_length()) for v in values))
    lease=n*(256+4*((b.limits['integer_bits']+7)//8));b.hold(lease);b.take(copy_bytes=lease,operations=n*max(1,n.bit_length()))
    try:
        order=sorted(values);out={}
        for name,q in (('q1',Fraction(1,4)),('median',Fraction(1,2)),('q3',Fraction(3,4))):
            if policy=='inverted_cdf':i=max(0,(n*q.numerator+q.denominator-1)//q.denominator-1);value=order[i]
            else:
                position=Fraction(n-1)*q;i=position.numerator//position.denominator;f=position-i
                value=order[i] if f==0 else b.add(order[i],b.mul(f,b.add(order[i+1],-order[i])))
            out[name]={'exact':rational(value,b),**projected(value)}
        return {'status':'computed','count':n,'policy':policy,'values':out}
    finally:b.release(lease)

STAT_KEYS=('algorithm','difference_arithmetic','zero_policy','tie_policy','alternative','all_zero','continuity','quantile_policy','multiplicity','scope')
def signed_rank(differences,profile,limits):
    b=budget(limits);fields(profile,STAT_KEYS)
    need(profile['algorithm']=='conditional_sign_midrank_v1' and profile['difference_arithmetic']=='exact_score_rationals'
         and profile['zero_policy']=='wilcox' and profile['tie_policy']=='exact_midrank'
         and profile['alternative'] in ('greater','less','two-sided') and profile['all_zero'] in ('p_one','undefined')
         and profile['continuity']=='none' and profile['quantile_policy'] in ('linear_type7','inverted_cdf')
         and profile['multiplicity']=='none_report_only','fully_explicit_supported_statistical_operator')
    need(profile['scope'] in ('original_unresolved','test_only','selected_operator_not_historical'), 'explicit_statistical_scope')
    need(type(differences) in (list,tuple) and all(type(x) is Fraction for x in differences),'exact_full_paired_differences')
    n=len(differences)
    if profile['scope']=='original_unresolved':
        b.take(items=n,metadata_bytes=32*n);b.hold(32*n)
        return {'operator':'defined_conditional_sign_distribution_not_historical_scipy',
            'scope':profile['scope'],'status':'unavailable_historical_statistical_profile',
            'support_count':n,'zero_positions':[i for i,v in enumerate(differences) if not v],
            'rank2_by_position':None,'tie_groups':None,'positive_rank2':None,'negative_rank2':None,
            'alternative':profile['alternative'],'profile':dict(profile),'pvalue':None,'original_parity':False}
    for value in differences:b.operands(value)
    if n:b.bits(2*max(max(abs(v.numerator).bit_length(),v.denominator.bit_length()) for v in differences))
    b.take(items=n,operations=n*max(1,n.bit_length()))
    lease=n*(512+4*((b.limits['integer_bits']+7)//8));b.hold(lease);b.take(copy_bytes=lease)
    try:
        nonzero=sorted((abs(x),i,1 if x>0 else -1) for i,x in enumerate(differences) if x)
        ranks=[0]*n;ties=[];i=0
        while i<len(nonzero):
            j=i+1
            while j<len(nonzero) and nonzero[j][0]==nonzero[i][0]:j+=1
            rank2=i+1+j
            for _,index,sign in nonzero[i:j]:ranks[index]=rank2
            if j-i>1:ties.append({'absolute_difference':rational(nonzero[i][0],b),'positions':[v[1] for v in nonzero[i:j]],'rank2':rank2})
            i=j
        weights=[ranks[i] for _,i,_ in nonzero];positive=sum(ranks[i] for _,i,sign in nonzero if sign>0)
        total=sum(weights);effective=len(weights);zeros=[i for i,x in enumerate(differences) if not x]
        out={'operator':'defined_conditional_sign_distribution_not_historical_scipy','scope':profile['scope'],
             'support_count':n,'effective_nonzero':effective,'zero_positions':zeros,'rank2_by_position':ranks,
             'tie_groups':ties,'positive_rank2':positive,'negative_rank2':total-positive,'alternative':profile['alternative'],
             'profile':dict(profile),'pvalue':None,'original_parity':False}
        if profile['scope']=='original_unresolved':out['status']='unavailable_historical_statistical_profile';return out
        if n==0 or effective==0 and profile['all_zero']=='undefined':out['status']='undefined_empty_or_all_zero';return out
        states=total+1;need(states<=b.limits['dp_states'],'exact_distribution_state_capacity',required=states)
        b.bits(effective+1)
        # One entire integer DP array is reserved before allocation. Upper-bound
        # each Python integer by the full2^effective bit extent, including zeros.
        dp_bytes=states*(64+(effective+8)//8);work=effective*states
        b.take(operations=work,copy_bytes=dp_bytes);b.hold(dp_bytes)
        try:
            counts=[0]*states;counts[0]=1;occupied=0
            for weight in weights:
                for j in range(occupied,-1,-1):counts[j+weight]+=counts[j]
                occupied+=weight
            denominator=1<<effective
            b.take(operations=2*states)
            lower=sum(counts[j] for j in range(positive+1));upper=sum(counts[j] for j in range(positive,states))
            numerator=upper if profile['alternative']=='greater' else lower if profile['alternative']=='less' else min(denominator,2*min(lower,upper))
            probability=Fraction(numerator,denominator)
            out.update(status='computed',pvalue={'exact':rational(probability,b),**projected(probability)},
                       distribution={'states':states,'sign_assignments_hex':format(denominator,'x'),
                                     'tail_rule':'inclusive; two-sided=min(1,2*min(lower,upper))','logical_DP_update_upper':work,'preflight_bytes':dp_bytes})
            return out
        finally:b.release(dp_bytes)
    finally:b.release(lease)
