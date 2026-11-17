"""Numerical worker source only; never imported by construction controls."""
from .core import need, Unsupported
def session_normalizer(beta, rows, training_videos):
    import numpy as np
    need(beta.ndim==2 and len(beta)==len(rows),"Trial-by-coordinate original matrix")
    train=set(training_videos);out={}
    for session in (2,3,4,5):
        indices=[i for i,r in enumerate(rows)if r["session"]==session and r["video"]in train]
        if len(indices)<2:raise Unsupported("No estimable training-only normalization in session")
        values=beta[indices,:]
        if not np.isfinite(values).all():raise Unsupported("Nonfinite original training response; no silent coordinate filtering")
        mean=values.mean(0);scale=values.std(0,ddof=1)
        if not np.isfinite(scale).all()or (scale<=0).any():raise Unsupported("Undefined training-session scale")
        out[session]=(mean,scale)
    return out
def aggregate(beta,rows,videos,normalizer):
    import numpy as np
    from .protocol import repetitions
    out=[]
    for video in videos:
        selected=[i for i,r in enumerate(rows)if r["video"]==video]
        need(len(selected)==repetitions(video),"Complete original repetitions for this person/video")
        values=[]
        for i in selected:
            mean,scale=normalizer[rows[i]["session"]]
            x=(beta[i,:]-mean)/scale
            if not np.isfinite(x).all():raise Unsupported("Nonfinite target; full disposition, not available-case selection")
            values.append(x)
        out.append(np.stack(values).mean(0))
    return np.stack(out)
def fold_responses(beta,rows,training_videos,query_videos):
    normalizer=session_normalizer(beta,rows,training_videos)
    return aggregate(beta,rows,training_videos,normalizer),aggregate(beta,rows,query_videos,normalizer),normalizer

