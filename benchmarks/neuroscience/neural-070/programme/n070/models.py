"""Fixed train-only block projections and grouped inner selection; worker only."""
from .core import need
from .protocol import ALPHAS
class Projection:
    def fit(self,x,rank):
        import numpy as np
        need(x.ndim==2 and np.isfinite(x).all(),"Finite training feature block")
        self.mean=x.mean(0);self.scale=x.std(0,ddof=0);self.scale[self.scale==0]=1
        z=(x-self.mean)/self.scale
        need(rank<=min(len(x)-1,x.shape[1]),"Precommitted rank must be supported; no test-adaptive reduction")
        self.basis=np.linalg.svd(z,full_matrices=False)[2][:rank].T
        return self
    def transform(self,x):return ((x-self.mean)/self.scale)@self.basis
class Readout:
    def fit(self,records,y,alpha):
        import numpy as np
        self.projections={};self.blocks=tuple(k for k in ("appearance","motion")if k in records[0])
        for key in self.blocks:
            self.projections[key]=Projection().fit(np.stack([r[key]for r in records]),100 if key=="appearance"else 10)
        self.categories="category"in records[0]
        self.vocab=sorted({c for r in records for c in r.get("category",[])})if self.categories else []
        z=self.design(records);self.xmean=z.mean(0);z=z-self.xmean
        need(np.isfinite(y).all()and y.ndim==2 and len(z)==len(y),"Complete finite aligned training targets")
        self.ymean=y.mean(0);self.coef=np.linalg.solve(z.T@z+alpha*np.eye(z.shape[1]),z.T@(y-self.ymean))
        return self
    def design(self,records):
        import numpy as np
        blocks=[self.projections[k].transform(np.stack([r[k]for r in records]))for k in self.blocks]
        if self.categories:
            # Vocabulary is fit on training videos; an explicit unknown count is kept.
            v={c:i for i,c in enumerate(self.vocab)};a=np.zeros((len(records),len(v)+1))
            for i,r in enumerate(records):
                for c in r["category"]:a[i,v.get(c,len(v))]+=1
            blocks.append(a)
        need(blocks,"At least one specified feature block")
        return np.concatenate(blocks,axis=1)
    def predict(self,records):return (self.design(records)-self.xmean)@self.coef+self.ymean
def choose_and_predict(features,beta,rows,training_videos,query_videos,inner):
    import numpy as np
    from .normalization import fold_responses
    need(set(inner)==set(training_videos),"Inner validation contained in outer training")
    candidates=[]
    for layer in ("layer1","layer2","layer3","layer4"):
        lookup=features[layer]
        for alpha in ALPHAS:
            total=0.;count=0
            for f in range(5):
                tr=[v for v in training_videos if inner[v]!=f];va=[v for v in training_videos if inner[v]==f]
                yt,yv,_=fold_responses(beta,rows,tr,va)
                model=Readout().fit([lookup[v]for v in tr],yt,alpha)
                residual=model.predict([lookup[v]for v in va])-yv
                total+=float((residual**2).sum());count+=residual.size
            candidates.append((total/count,layer,alpha))
    loss,layer,alpha=min(candidates)
    yt,_,_=fold_responses(beta,rows,training_videos,training_videos)
    lookup=features[layer];model=Readout().fit([lookup[v]for v in training_videos],yt,alpha)
    return model.predict([lookup[v]for v in query_videos]),{
        "layer":layer,"alpha":alpha,"appearance_rank":100,"motion_rank":10,
        "inner_loss_equal_video_coordinate":loss,"training_videos":list(training_videos),
        "normalization":"training_video_only_by_original_session_ddof1",
        "category_vocabulary":model.vocab}

