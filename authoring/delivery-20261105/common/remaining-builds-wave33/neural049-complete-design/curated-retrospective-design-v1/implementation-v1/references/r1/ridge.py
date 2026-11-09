"""R1 exact full-coordinate primal/dual Cholesky ridge."""
def solve(np,z,y,lam):
    n,p=z.shape
    if n<1 or lam<=0: raise ValueError('ridge scope')
    if p<=n:
        a=z.T@z+n*lam*np.eye(p,dtype=np.float64)
        l=np.linalg.cholesky(a)
        beta=np.linalg.solve(l.T,np.linalg.solve(l,z.T@y)); route='primal'
    else:
        a=z@z.T+n*lam*np.eye(n,dtype=np.float64)
        l=np.linalg.cholesky(a)
        beta=z.T@np.linalg.solve(l.T,np.linalg.solve(l,y)); route='dual'
    if not np.isfinite(beta).all(): raise ValueError('ridge numerical failure')
    return {'beta':beta,'intercept':0.0,'route':route}

def infer(np,state,z):
    return z@state['beta']+state['intercept']
