"""Run unchanged public validator with its sole scalar finiteness dependency."""
import ast,math,types

def load(raw):
    tree=ast.parse(raw)
    attrs=[n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='np']
    if set(attrs)!={'isfinite'}:raise ValueError('Only scalar finiteness allowed in public validator')
    # Original functions/constants stay byte-derived; only unused ndarray package
    # import is replaced on the host. Native scoring imports genuine NumPy.
    tree.body=[n for n in tree.body if not(isinstance(n,ast.Import) and any(a.name=='numpy' for a in n.names))]
    m=types.ModuleType('neural078_public_validation');m.np=types.SimpleNamespace(isfinite=math.isfinite)
    exec(compile(tree,'original-report_contract.py','exec'),m.__dict__);return m

def field_names(report):
    def leaves(v,p=''):
        if type(v)is dict:
            for k in sorted(v):yield from leaves(v[k],p+'/'+k)
        else:yield p
    out=[]
    for r in report['participants']:
        out.extend(r['participant_id']+p for p in leaves({k:v for k,v in r.items() if k!='participant_id'}))
    out.extend('aggregate'+p for p in leaves(report['aggregate']))
    if len(out)!=195 or len(set(out))!=195:raise ValueError('Complete195 field report')
    return sorted(out)
