"""Generate separately identified observation wrappers around full native figures.

Original MATLAB source is never edited. The wrapper preserves every original
body statement and only captures the resulting workspace. Any unsupported
function form is a qualification refusal, not a guessed truncated producer.
"""
import hashlib,re
from pathlib import Path

def instrument_figure(original_body,expected_sha256):
 if hashlib.sha256(original_body).hexdigest()!=expected_sha256:raise ValueError('native source pin')
 text=original_body.decode();lines=text.splitlines()
 match=re.fullmatch(r'function\s+([A-Za-z][A-Za-z0-9_]*)\(([^()]*)\)\s*',lines[0])
 if not match:raise ValueError('unqualified native function signature')
 if sum(bool(re.match(r'^\s*function\b',x))for x in lines)!=1:raise ValueError('nested function instrumentation not qualified')
 while lines and not lines[-1].strip():lines.pop()
 if lines[-1].strip()!='end':raise ValueError('native terminal outer end not bound')
 name,args=match.groups();params=[x.strip()for x in args.split(',')if x.strip()]
 if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',x)for x in params):raise ValueError('unsupported parameter syntax')
 newname='ofc_capture_'+name
 # Original body remains in identical statement order. The added capture has
 # a separately recorded transform identity and requires native equivalence.
 capture="""
ofc_names = who;
ofc_products = struct();
for ofc_index=1:length(ofc_names)
 ofc_name=ofc_names{ofc_index};
 if startsWith(ofc_name,'ofc_'), continue; end
 ofc_value=eval(ofc_name);
 if ~isa(ofc_value,'function_handle') && ~isa(ofc_value,'matlab.graphics.Graphics')
  ofc_products.(ofc_name)=ofc_value;
 end
end
end
"""
 body=('function ofc_products = '+newname+'('+args+')\n'+'\n'.join(lines[1:-1])+capture).encode()
 return {'name':newname,'parameters':params,'body':body,'original_sha256':expected_sha256,'instrumented_sha256':hashlib.sha256(body).hexdigest(),'transform':'rename_outer_function_preserve_all_body_append_workspace_capture_v1','native_equivalence_qualified':False}

def resolve_product(tree,field_path):
 """Traverse a qualified producer workspace field path; never evaluate text."""
 value=tree
 for key in field_path:
  if isinstance(key,str):
   if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',key):raise ValueError('invalid source field')
   value=value[key]
  elif type(key)is int and key>=0:value=value[key]
  else:raise ValueError('invalid field index')
 return value
