"""R1 complete direct split-scan squared-error boosted trees, no library model."""
import math

def thresholds(np,z):
    n,p=z.shape; out=[]
    for f in range(p):
        ordered=np.sort(z[:,f],kind='stable')
        vals=[]
        for j in range(1,64):
            t=float(ordered[(j*n+63)//64-1])
            if t<float(ordered[-1]) and (not vals or t!=vals[-1]): vals.append(t)
        out.append(vals)
    return out

def leaf(np,residual,rows,l2):
    return float(np.sum(residual[rows],dtype=np.float64))/(len(rows)+l2)

def split_gain(left_sum,left_n,right_sum,right_n,l2):
    return left_sum**2/(left_n+l2)+right_sum**2/(right_n+l2)-(left_sum+right_sum)**2/(left_n+right_n+l2)

def tree_fit(np,z,residual,edges,max_leaves,l2,budget):
    n,p=z.shape; floor=max(2,math.ceil(.05*n))
    leaves={'':np.arange(n,dtype=np.int64)}; nodes={}
    while len(leaves)<max_leaves:
        best=None
        for path,rows in sorted(leaves.items()):
            budget.tick()
            if len(rows)<2*floor: continue
            for f in range(p):
                for rank,t in enumerate(edges[f]):
                    left=rows[z[rows,f]<=t]; right=rows[z[rows,f]>t]
                    if min(len(left),len(right))<floor: continue
                    a=float(np.sum(residual[left],dtype=np.float64)); b=float(np.sum(residual[right],dtype=np.float64))
                    gain=split_gain(a,len(left),b,len(right),l2)
                    if not math.isfinite(gain): budget.fail('tree gain overflow')
                    if gain<=0: continue
                    key=(-gain,f,rank,path)
                    if best is None or key<best[0]: best=(key,path,f,t,left,right)
        if best is None: break
        _,path,f,t,left,right=best
        nodes[path]={'feature':f,'threshold':t,'left':path+'0','right':path+'1'}
        del leaves[path]; leaves[path+'0']=left; leaves[path+'1']=right
    for path,rows in sorted(leaves.items()): nodes[path]={'value':leaf(np,residual,rows,l2),'count':len(rows)}
    return nodes

def tree_predict(np,tree,z):
    out=np.empty(len(z),np.float64)
    for i,row in enumerate(z):
        path=''
        while 'value' not in tree[path]:
            node=tree[path]; path=node['left'] if row[node['feature']]<=node['threshold'] else node['right']
        out[i]=tree[path]['value']
    return out

def fit_boost(np,z,y,config,budget):
    initial=float(np.sum(y,dtype=np.float64)/len(y)); pred=np.full(len(y),initial,np.float64)
    edges=thresholds(np,z); forest=[]
    budget.begin("boost_trees",config["trees"])
    for k in range(config['trees']):
        budget.enter('boost_trees'); tree=tree_fit(np,z,y-pred,edges,config['leaves'],config['leaf_l2'],budget)
        forest.append(tree); pred+=.05*tree_predict(np,tree,z)
        if not np.isfinite(pred).all(): budget.fail('boosting overflow')
        budget.complete('boost_trees')
    return {'initial':initial,'learning_rate':.05,'thresholds':edges,'trees':forest,'completed_trees':len(forest)}

def infer(np,state,z,budget):
    pred=np.full(len(z),state['initial'],np.float64)
    for tree in state['trees']:
        budget.tick(); pred+=state['learning_rate']*tree_predict(np,tree,z)
    return pred
