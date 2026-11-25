"""Fixed source-frame incremental-response decomposition; no inferential test."""
import math
from fractions import Fraction
from delivery_io import need

FIELDS=('matched_increment','unmatched_increment','opto_only','context_interaction',
        'matched_minus_opto','unmatched_minus_opto')
ORIGINAL=('visF1','visF2','vis1OptoF1','vis2OptoF1','optoF1')
REVISION=('matched','unmatched','opto')
BLOCKS=('original_expt1','original_expt2','original_expt3','revision_pool')


def mean(values):
    values=list(values);need(bool(values),'Nonempty arithmetic support')
    # Sum exact represented floats, divide once, then round the finite mean.
    # Per-value division can erase a representable subnormal mean.
    value=float(sum((Fraction(float(v)) for v in values), Fraction())/len(values))
    need(math.isfinite(value),'Finite source arithmetic')
    return value


def decompose(arrays,kind,keys,np):
    expected=ORIGINAL if kind=='original' else REVISION
    need(kind in ('original','revision') and set(arrays)==set(expected),'Exact source condition family')
    shapes={a.shape for a in arrays.values()}
    need(len(shapes)==1,'Matched row/frame condition support')
    shape=next(iter(shapes));need(len(shape)==2 and shape[0]==len(keys),'All declared source rows')
    start,end=(125,128) if kind=='original' else (123,126)
    need(shape[1]>=end,'Explicit source frame window present')
    need(all(a.dtype.kind=='f' and a.dtype.itemsize in (4,8) and not np.isinf(a).any()
             for a in arrays.values()),'Floating source arrays; Infinity is invalid, NaN is missing')
    rows=[]
    for i,key in enumerate(keys):
        selected={name:[float(v) for v in a[i,start:end]] for name,a in arrays.items()}
        valid=all(math.isfinite(v) for values in selected.values() for v in values)
        if valid:
            if kind=='original':
                matched=mean(a-b for a,b in zip(selected['vis1OptoF1'],selected['visF1']))
                unmatched=mean(a-b for a,b in zip(selected['vis2OptoF1'],selected['visF2']))
                opto=mean(selected['optoF1'])
            else:
                # These source arrays already contain the visual subtraction.
                matched=mean(selected['matched']);unmatched=mean(selected['unmatched']);opto=mean(selected['opto'])
            values=(matched,unmatched,opto,matched-unmatched,matched-opto,unmatched-opto)
            need(all(math.isfinite(v) for v in values),'Finite decomposition, no clamping')
        else:values=(None,)*6
        rows.append({'cell_key':key,'availability':'observed' if valid else 'unobserved',
                     **dict(zip(FIELDS,values))})
    valid_rows=[r for r in rows if r['availability']=='observed']
    averages={field:mean(r[field] for r in valid_rows) if valid_rows else None for field in FIELDS}
    return {'cells':rows,'valid_cells':len(valid_rows),'means':averages}


def summarize_blocks(blocks):
    need(set(blocks)==set(BLOCKS),'All original blocks and separate revision pool')
    original=[blocks[key]['means']['context_interaction'] for key in BLOCKS[:3]]
    return {'original_macro_interaction':mean(original) if all(x is not None for x in original) else None,
            'revision_mean_interaction':blocks['revision_pool']['means']['context_interaction']}
