"""Exposed-development formula reconstruction, explicitly separate from N070 B.

This consumes recomputed FIR/reliability products, not published target tables.
Upstream FSL/FIR, test-half reliability and source-space ROI producers must be
independently bound. Missing upstream producers cannot be replaced by schemas.
"""
from pathlib import Path
from .core import need
from .native.io import load,dump
from .numeric_io import array,save
def correlation(x,y):
    x=x-x.mean(0,keepdims=True);y=y-y.mean(0,keepdims=True)
    return ((x*y).sum(0)/len(x))/((x.std(0)+1e-8)*(y.std(0)+1e-8))
def run(request):
    import numpy as np,torch
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    root=Path("/inputs");out=Path("/output");cap=request["member_bytes"];m=load(root/request["manifest"])
    need(m["upstream_status"]=="independently_recomputed_FIR_reliability_ROI","Published tables are not recomputation")
    x=array(root,m["features"],cap);train=array(root,m["train_reliable"],cap);test=array(root,m["test_reliable"],cap)
    reliability=array(root,m["noise_ceiling"],cap);p=array(root,m["p_values"],cap)
    need(x.shape[0]==1102 and train.shape[:2]==(1000,3) and test.shape[:2]==(102,10),"Literal exposed 1000/102 and 3/10 repeats")
    # Literal author fits separate train/test scalers before AND after train PCA.
    a=StandardScaler().fit_transform(x[:1000]);b=StandardScaler().fit_transform(x[1000:])
    pca=PCA(n_components=100,random_state=42).fit(a)
    a=StandardScaler().fit_transform(pca.transform(a));b=StandardScaler().fit_transform(pca.transform(b))
    a=torch.from_numpy(np.c_[np.ones(1000),a]).float();b=torch.from_numpy(np.c_[np.ones(102),b]).float()
    y=torch.from_numpy(train.mean(1)).float()
    coef=torch.linalg.solve(a.T@a,a.T@y);prediction=(b@coef).numpy()
    rho=reliability[p<.05]/(2-reliability[p<.05])
    score=np.stack([correlation(test[:,rep,:],prediction)for rep in range(10)]).mean(0)/rho
    return dump(out/"literal_development.json",{"status":"exposed_development_reconstruction",
        "prediction":save(out,"prediction.npy",prediction,cap),"score":save(out,"noise_normalized_correlation.npy",score,cap),
        "test_normalization":True,"test_reliability_selection":True,"hidden_generalization":False,
        "not_primary_N070_metric":True,"input_identity":m["upstream_identity"]})

