"""Native 6144-sample segment support checks, not filter-causality certification."""
import heapq

def validate_segments(rows,partitions,*,force_nonoverlap):
    if not isinstance(rows,list) or not rows or type(force_nonoverlap) is not bool:raise ValueError('Complete segment roster')
    if set(partitions)!={'train','validation','query'}:raise ValueError('Three exact partitions')
    seen=set();owner={}
    for split,indices in partitions.items():
        if not isinstance(indices,list) or not indices:raise ValueError('Every partition has support')
        for idx in indices:
            if type(idx) is not int or not 0<=idx<len(rows) or idx in owner:raise ValueError('Unique complete split indexing')
            owner[idx]=split
    if len(owner)!=len(rows):raise ValueError('All selected source rows assigned exactly once')
    events=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or row['id'] in seen:raise ValueError('Unique original segment identities')
        seen.add(row['id']);a=row.get('start_sample');b=row.get('end_sample')
        if type(a) is not int or type(b) is not int or a<0 or b-a!=6144:raise ValueError('Exact native half-open3s/2048Hz interval')
        events.append((a,b,i))
    # Intervals may touch at a boundary. Overlap across partitions is always forbidden.
    active=[];counts={'train':0,'validation':0,'query':0}
    for a,b,i in sorted(events):
        while active and active[0][0]<=a:
            _,oldsplit=heapq.heappop(active);counts[oldsplit]-=1
        split=owner[i]
        if any(counts[s] for s in counts if force_nonoverlap or s!=split):raise ValueError('Source segment overlap violates declared protocol')
        heapq.heappush(active,(b,split));counts[split]+=1
    return {'selected_rows':len(rows),'partition_counts':{k:len(v) for k,v in partitions.items()},'native_window_overlap_checked':True,'full_filter_support_or_causal_isolation_certified':False}
