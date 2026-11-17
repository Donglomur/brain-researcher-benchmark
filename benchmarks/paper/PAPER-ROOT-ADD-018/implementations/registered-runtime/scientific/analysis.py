"""Full decoder/MI/history reference source, with explicit frozen supports."""
def reward_decoder(train_latent,train_labels,validation_latent,validation_labels,test_latent,regularization_grid,seed):
 import numpy as np
 from sklearn.svm import SVC
 from sklearn.metrics import balanced_accuracy_score
 if set(train_labels)!={1,2,3,4,5}or set(validation_labels)!={1,2,3,4,5}:raise ValueError('five-class fit/validation support')
 results=[];models=[]
 for c in regularization_grid:
  model=SVC(C=c,kernel='linear',class_weight='balanced',random_state=seed).fit(train_latent,train_labels);score=balanced_accuracy_score(validation_labels,model.predict(validation_latent));results.append({'C':c,'validation_BA':float(score)});models.append(model)
 best=max(range(len(results)),key=lambda i:(results[i]['validation_BA'],-i));chosen=models[best]
 # Model-selection policy must explicitly select whether final train+validation
 # refit is allowed. This function returns the train-only selected model.
 return {'predictions':chosen.predict(test_latent),'model':chosen,'validation_attempts':results,'selected_index':best,'test_labels_seen':False}

def native_reward_folds(latent,labels,folds,regularization,seed):
 """Exact balanced original fold keys must be supplied from qualified producer."""
 from sklearn.svm import SVC
 import numpy as np
 if len(folds)!=10:raise ValueError('native10fold requirement')
 outputs=[]
 for index,fold in enumerate(folds):
  train=np.asarray(fold['train'],int);test=np.asarray(fold['test'],int)
  if set(train)&set(test):raise ValueError('fold overlap')
  if set(np.asarray(labels)[train])!={1,2,3,4,5}or set(np.asarray(labels)[test])!={1,2,3,4,5}:raise ValueError('native class support')
  model=SVC(C=regularization,kernel='linear',random_state=seed).fit(np.asarray(latent)[train],np.asarray(labels)[train]);outputs.append({'fold':index,'test_keys':test,'predictions':model.predict(np.asarray(latent)[test])})
 return outputs

def ross_bits(values,labels,neighbors,seed):
 import numpy as np
 from sklearn.feature_selection import mutual_info_classif
 x=np.asarray(values,float).reshape(-1,1);y=np.asarray(labels)
 if len(x)!=len(y)or not np.all(np.isfinite(x)):raise ValueError('complete MI support')
 return float(mutual_info_classif(x,y,discrete_features=False,n_neighbors=neighbors,random_state=seed)[0]/np.log(2))

def native_mi(values,blocks,qualified_permutations,neighbors,seed):
 import numpy as np
 if len(qualified_permutations)!=1000:raise ValueError('native1000nulls')
 n=len(values);truth=ross_bits(values,blocks,neighbors,seed);null=[]
 for p in qualified_permutations:
  if sorted(p)!=list(range(n)):raise ValueError('null exact full support')
  null.append(ross_bits(values,np.asarray(blocks)[p],neighbors,seed))
 return {'bits':truth,'null_bits':null,'native_tail_policy_unbound_until_qualified':True}

def slow_history_ols(slow,offers,session_ids):
 import numpy as np
 import statsmodels.api as sm
 rows=[];targets=[];keys=[]
 for t in range(10,len(offers)):
  if any(session_ids[j]!=session_ids[t]for j in range(t-10,t+1)):continue
  rows.append([1,*[offers[t-j]for j in range(11)]]);targets.append(slow[t]);keys.append(t)
 if not rows:raise ValueError('no complete current+10prior support')
 fit=sm.OLS(np.asarray(targets),np.asarray(rows)).fit()
 return {'keys':keys,'coefficients':fit.params,'t_statistics':fit.tvalues,'pvalues':fit.pvalues,'residuals':fit.resid,'session_reset':True}

def association_products(rows,policy):
 """Prospective association only; qualified blocked nulls, no causal claim."""
 groups={}
 for r in rows:groups.setdefault((r['group_keys']['rat'],r['group_keys']['session']),[]).append(r)
 output=[]
 for key,rs in groups.items():
  specification=policy['session_estimators']['/'.join(key)]
  values=[r['prediction']['latent']for r in rs];labels=[r['target']['block']for r in rs]
  result=native_mi(values,labels,specification['blocked_permutations'],specification['neighbors'],specification['seed'])
  output.append({'rat':key[0],'session':key[1],**result,'claim':'descriptive_association_only','null_kind':'prequalified_blocked'})
 return output
