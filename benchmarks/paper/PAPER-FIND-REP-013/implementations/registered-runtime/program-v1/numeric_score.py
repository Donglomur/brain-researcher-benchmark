"""Method-neutral numerical comparison. Pure stdlib; private loader is lazy.

No candidate source or interpretation prose is examined. Wrong finite values
are scored continuously. Exact keys and missingness establish full denominators.
"""
import csv,io,json,math,re
import schema as S
class Invalid(ValueError):pass
class Unscorable(ArithmeticError):pass

def need(ok,message):
 if not ok:raise Invalid(message)
def finite(token):
 need(type(token) is str and len(token)<=128 and re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',token) is not None,'Numeric token')
 x=float(token);need(math.isfinite(x),'Finite numeric value')
 mantissa=re.split('[eE]',token)[0]
 need(x!=0 or not any(c.isdecimal() and int(c)!=0 for c in mantissa),'Nonzero numeric underflow')
 return x

def bounded_integer(token):
 # finite() has already admitted the syntax and numeric extent. Keep exact
 # decimal identity before float rounding, including Unicode decimal digits.
 mantissa,_,exponent=token.lower().partition('e')
 digits=''.join(str(int(c)) for c in mantissa if c.isdecimal()).lstrip('0')
 if not digits:return 0
 fraction=len(mantissa.partition('.')[2])
 significant=digits.rstrip('0')
 power=(int(exponent) if exponent else 0)-fraction+len(digits)-len(significant)
 need(not mantissa.startswith('-') and power>=0 and len(significant)+power<=10,
      'Bounded integral count/identity')
 # The length check bounds power to at most nine, even for long exponents.
 value=int(significant)*10**power
 need(value<=1000000000,'Bounded integral count/identity')
 return value

def signed_mean(values):
 # Avoid scaling signed terms: small residuals can vanish before cancellation.
 try:return math.fsum(values)/len(values)
 except OverflowError:
  total,denominator=0,1
  for value in values:
   numerator,divisor=value.as_integer_ratio()
   if divisor>denominator:
    total*=divisor//denominator;denominator=divisor
   total+=numerator*(denominator//divisor)
  return total/(denominator*len(values))

def pairs(rows):
 out={}
 for k,v in rows:
  need(k not in out,'Duplicate JSON key');out[k]=v
 return out

def decode_json(raw):
 try:return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_float=finite,
   parse_int=lambda x:int(x) if len(x)<=18 else (_ for _ in ()).throw(Invalid('Integer token bound')),
   parse_constant=lambda x:(_ for _ in ()).throw(Invalid('Nonfinite JSON')))
 except (UnicodeError,ValueError,OverflowError,RecursionError) as e:raise Invalid(str(e)) from e

def table(raw,name):
 spec=S.TABLES[name]
 try:
  csv.field_size_limit(256);reader=csv.DictReader(io.StringIO(raw.decode('utf-8'),newline=''))
  need(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)) and set(reader.fieldnames)==set(spec['columns']),'Exact column names')
  out={}
  for i,row in enumerate(reader):
   need(i<spec['rows'] and set(row)==set(spec['columns']) and all(type(v) is str for v in row.values()),'Bounded complete CSV rows')
   parsed={}
   for col,v in row.items():
    if col in S.STRINGS:
     need(v in (S.CELLS if col=='cell_id' else ('human','mouse')),'Known source identity');parsed[col]=v
    elif v=='':
     need(name=='cells.csv' and col in S.NULLABLE,'Only declared blank fields');parsed[col]=None
    else:
     x=finite(v)
     if col in S.INTEGERS:x=bounded_integer(v)
     parsed[col]=x
   key=tuple(parsed[k] for k in spec['keys']);need(key not in out,'Duplicate row identity');out[key]=parsed
  need(out,'Nonempty table');return out
 except (UnicodeError,csv.Error,ValueError,OverflowError) as e:raise Invalid(str(e)) from e

def generic_json(v,depth=0):
 need(depth<=12,'Bounded JSON nesting')
 if type(v) is dict:
  need(len(v)<=64 and all(type(k) is str and 0<len(k)<=100 for k in v),'Bounded JSON map')
  return {k:generic_json(x,depth+1) for k,x in v.items()}
 if type(v) is list:
  need(len(v)<=20,'Bounded JSON list');return [generic_json(x,depth+1) for x in v]
 if type(v) is str:need(len(v)<=200,'Bounded string');return v
 if type(v) in (int,float):need(math.isfinite(v),'Finite JSON number');return v
 need(type(v) is bool or v is None,'JSON scalar');return v

def canonical_summary(value):
 value=generic_json(value)
 need(type(value) is dict,'Summary object')
 if 'leave_one_cell_out' in value:
  rows=value['leave_one_cell_out'];need(type(rows) is list and all(type(x) is dict and x.get('omitted_cell') in S.CELLS for x in rows),'LOO identities')
  need(len({x['omitted_cell'] for x in rows})==len(rows),'Unique LOO identities')
  value['leave_one_cell_out']=sorted(rows,key=lambda x:x['omitted_cell'])
 return value

def admit(files):
 need(type(files) is dict and set(S.REQUIRED)<=set(files)<=set(S.CAPS),'Exact numerical files plus optional interpretation')
 need(all(type(v) is bytes and 0<len(v)<=S.CAPS[k] for k,v in files.items()) and sum(map(len,files.values()))<=S.TOTAL_CAP,'Per-file and aggregate byte bounds')
 # Optional interpretation is retained but never parsed or scored.
 return {'tables':{n:table(files[n],n) for n in S.TABLES},'summary':canonical_summary(decode_json(files['summary.json']))}

def stats(errors):
 need(errors,'Fixed nonempty denominator')
 if not all(math.isfinite(x) for x in errors):raise Unscorable('Difference overflow')
 scale=max(map(abs,errors))
 if scale==0:return {'n':len(errors),'rmse':0.,'mae':0.,'bias':0.,'max_abs_error':0.}
 z=[x/scale for x in errors]
 vals={'rmse':scale*math.sqrt(math.fsum(x*x for x in z)/len(z)),
       'mae':scale*(math.fsum(map(abs,z))/len(z)),
       'bias':signed_mean(errors),'max_abs_error':scale}
 if not all(math.isfinite(x) for x in vals.values()):raise Unscorable('Aggregate overflow')
 # A positive error must never be reported as exact reconstruction merely
 # because the nonnegative aggregate rounded below binary64's minimum.
 if vals['rmse']==0 or vals['mae']==0:raise Unscorable('Nonzero error aggregate underflow')
 return {'n':len(errors),**vals}

def compare_summary(got,ref,path='summary',rows=None):
 rows={} if rows is None else rows
 if type(ref) is dict:
  need(type(got) is dict and set(got)==set(ref),'Summary keys '+path)
  for k in sorted(ref):compare_summary(got[k],ref[k],path+'.'+k,rows)
 elif type(ref) is list:
  need(type(got) is list and len(got)==len(ref),'Summary list coverage '+path)
  for i,(a,b) in enumerate(zip(got,ref)):compare_summary(a,b,path+'.'+str(i),rows)
 elif type(ref) in (int,float):
  need(type(got) in (int,float) and math.isfinite(got),'Summary numeric type '+path)
  e=float(got)-float(ref)
  if not math.isfinite(e):raise Unscorable('Summary difference overflow')
  rows[path]={'signed_error':e,'absolute_error':abs(e),'units':'individual_count' if '.paper_reported_n_individuals.' in path else S.unit(path.rsplit('.',1)[-1])}
 else:need(type(got) is type(ref) and got==ref,'Summary identity '+path)
 return rows

def compare(candidate,reference):
 tables={};missing=[];identity=[]
 for name,spec in S.TABLES.items():
  a,b=candidate['tables'][name],reference['tables'][name]
  if set(a)!=set(b):
   identity.append({'file':name,'candidate_rows':len(a),'required_rows':len(b),'missing_count':len(set(b)-set(a)),'unexpected_count':len(set(a)-set(b)),'missing_examples':[list(k) for k in sorted(set(b)-set(a))[:8]],'unexpected_examples':[list(k) for k in sorted(set(a)-set(b))[:8]]});continue
  for key in sorted(b):
   for col in spec['columns']:
    if (a[key][col] is None)!=(b[key][col] is None):missing.append({'file':name,'key':list(key),'column':col})
    if col in S.STRINGS:need(a[key][col]==b[key][col],'Exact species/identity values')
 if identity or missing:return {'status':'incomplete_numerical_coverage','metrics':None,'topology_key_diagnostics':identity,'missingness_mismatch_count':len(missing),'missingness_examples':missing[:16],'no_matched_subset_score':True}
 for name,spec in S.TABLES.items():
  a,b=candidate['tables'][name],reference['tables'][name];fields={}
  for col in spec['columns']:
   if col in S.STRINGS or col in spec['keys']:continue
   groups={}
   for key in sorted(b):
    if b[key][col] is not None:groups.setdefault(b[key]['cell_id'],[]).append(float(a[key][col])-float(b[key][col]))
   if not groups:
    fields[col]={'n':0,'status':'not_defined_by_reference'};continue
   per={cid:stats(e) for cid,e in sorted(groups.items())};equal=stats([v['rmse'] for v in per.values()])['rmse']
   fields[col]={'units':S.unit(col),'defined_rows':sum(v['n'] for v in per.values()),'defined_cells':len(per),'equal_cell_rmse':equal,'per_cell':per}
   if col in S.INTEGERS:fields[col]['exact_mismatch_count']=sum(x!=0 for e in groups.values() for x in e)
  tables[name]={'required_rows':len(b),'row_identity_exact':True,'fields':fields}
 summary=compare_summary(candidate['summary'],reference['summary'])
 return {'status':'complete_numerically_compared','metrics':{'primary_equal_cell_branch_length_rmse_um':tables['branches.csv']['fields']['length_um']['equal_cell_rmse'],'tables':tables,'summary_scalar_errors':summary},'topology_key_diagnostics':[],'missingness_mismatch_count':0,'no_mixed_unit_composite':True}

def grade(files,load_reference):
 result={'status':'invalid_submission','submission_valid':False,'private_numeric_reference_loads':0,'scientific_success':None,'full_paper_reproduction':False}
 try: candidate=admit(files)
 except (Invalid,TypeError,KeyError) as e:return {**result,'reason':str(e)[:300]}
 result.update(submission_valid=True,private_numeric_reference_loads=None)
 # A loader failure is operational; do not misreport zero private reads.
 reference=admit(load_reference());result['private_numeric_reference_loads']=1
 try:
  value=compare(candidate,reference)
  return {**result,'status':'scored' if value['status']=='complete_numerically_compared' else 'incomplete_numerical_coverage',**{'comparison':value}}
 except Invalid as e:return {**result,'status':'invalid_submission','submission_valid':False,'reason':str(e)[:300]}
 except (Unscorable,OverflowError) as e:return {**result,'status':'unsupported_derived_numerics','reason':str(e)[:300],'comparison':None}
