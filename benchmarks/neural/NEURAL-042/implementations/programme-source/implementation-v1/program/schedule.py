"""One full canonical programme; variants never add task identities."""
from contracts import TASK,CELLS,identities
from core import need


def cell_id(cell):
    need(tuple(cell)in CELLS,'selected core cell')
    return '-'.join(cell)


def schedule(roster):
    identities(roster,36)
    authors=[{'identity':'author/'+mode+'/'+tool,'kind':'author','mode':mode,'tool':tool} for mode in ('F','I')for tool in ('T0','T1')]
    cases=[{'identity':'case/'+cell_id(c)+'/'+p,'kind':'case','cell':list(c),'person':p}for c in CELLS for p in roster]
    refs=[{'identity':'reference/'+r+'/'+w+'/'+p,'kind':'reference','reference':r,'world':w,'person':p}for r in ('R1','R2')for w in ('O','D')for p in roster]
    ref_groups=[{'identity':'reference-group/'+r+'/'+w,'kind':'reference_group','reference':r,'world':w}for r in ('R1','R2')for w in ('O','D')]
    groups=[{'identity':'group/'+cell_id(c),'kind':'group','cell':list(c)}for c in CELLS]
    return authors+cases+refs+ref_groups+groups


def disposition(planned,events):
    ids=[r['identity']for r in planned];need(len(ids)==len(set(ids)),'unique fixed full schedule')
    entered=set();completed=set();failed=set();last=None
    for e in events:
        if e.get('kind')not in ('phase_entered','phase_completed','phase_failed'):continue
        k=e['identity'];need(k in ids,'no foreign phase');last=k
        if e['kind']=='phase_entered':need(k not in entered,'phase entered once');entered.add(k)
        elif e['kind']=='phase_completed':need(k in entered and k not in completed|failed,'one completion after entry');completed.add(k)
        else:need(k in entered and k not in completed|failed,'one failure after entry');failed.add(k)
    sets={'completed':sorted(completed),'failed':sorted(failed),'entered_incomplete':sorted(entered-completed-failed),'unentered':sorted(set(ids)-entered)}
    need(sum(map(len,sets.values()))==len(ids),'disjoint full failure accounting')
    return {'identities':sets,'counts':{k:len(v)for k,v in sets.items()},'last_phase':last,'expected':len(ids)}
