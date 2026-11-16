"""Train-only linear-Gaussian reference building blocks, authored not executed.

The missing original hLDS producer is NOT reconstructed by guessing its clocks.
Schedules/constraints below must be independently qualified against original
producers for native use. Prospective variants get distinct method identities.
"""
def filter_sequence(observations,transition,noise,C,R,m0,P0,observation_masks):
 import numpy as np
 x=np.asarray(observations,float);m=np.asarray(m0,float);P=np.asarray(P0,float);filtered=[];predicted=[];loglik=0.
 if len(transition)!=len(x)or len(noise)!=len(x)or len(observation_masks)!=len(x):raise ValueError('complete time schedule')
 for t,row in enumerate(x):
  F=np.asarray(transition[t],float);Q=np.asarray(noise[t],float);m=F@m;P=F@P@F.T+Q;predicted.append((m.copy(),P.copy()))
  use=np.asarray(observation_masks[t],bool);H=C[use];rr=R[np.ix_(use,use)];y=row[use]
  if not np.all(np.isfinite(y)):raise ValueError('unavailable observation is not zero')
  if len(y):
   S=H@P@H.T+rr;residual=y-H@m;K=np.linalg.solve(S,H@P).T;I=np.eye(len(m));m=m+K@residual
   # Joseph form preserves the declared covariance calculation.
   P=(I-K@H)@P@(I-K@H).T+K@rr@K.T
   sign,logdet=np.linalg.slogdet(S)
   if sign<=0:raise ValueError('singular innovation covariance')
   loglik-=.5*(len(y)*np.log(2*np.pi)+logdet+residual@np.linalg.solve(S,residual))
  filtered.append((m.copy(),P.copy()))
 return {'filtered':filtered,'predicted':predicted,'log_likelihood':float(loglik)}

def training_smoother(filtered,predicted,transition):
 """Training E-step only. A prediction worker must call filter_sequence instead."""
 import numpy as np
 means=[x[0].copy()for x in filtered];cov=[x[1].copy()for x in filtered];lag=[None]*len(filtered)
 for t in range(len(filtered)-2,-1,-1):
  J=np.linalg.solve(predicted[t+1][1],transition[t+1]@filtered[t][1]).T
  means[t]=filtered[t][0]+J@(means[t+1]-predicted[t+1][0]);cov[t]=filtered[t][1]+J@(cov[t+1]-predicted[t+1][1])@J.T;lag[t+1]=cov[t+1]@J.T
 return means,cov,lag

def fit_ordinary_lds(train_counts,initial,iterations,tolerance):
 """Prospective ordinary LDS ML-EM. Exactly train input; no hidden test refit."""
 import numpy as np
 x=np.sqrt(np.asarray(train_counts,float))
 if x.ndim!=2 or np.any(~np.isfinite(x)):raise ValueError('training count domain')
 F,C,Q,R,m0,P0=[np.asarray(initial[k],float).copy()for k in('F','C','Q','R','m0','P0')];history=[]
 if iterations<1 or tolerance<0:raise ValueError('predeclared optimizer settings')
 for step in range(iterations):
  fs=[np.eye(len(F))]+[F]*(len(x)-1);qs=[np.zeros_like(Q)]+[Q]*(len(x)-1);filtered=filter_sequence(x,fs,qs,C,R,m0,P0,[np.ones(x.shape[1],bool)]*len(x));m,p,lag=training_smoother(filtered['filtered'],filtered['predicted'],fs)
  Exx=[p[t]+np.outer(m[t],m[t])for t in range(len(x))];cross=[lag[t]+np.outer(m[t],m[t-1])for t in range(1,len(x))]
  denominator=sum(Exx[:-1]);Fnew=np.linalg.solve(denominator.T,sum(cross).T).T;Qnew=sum(Exx[t]-Fnew@cross[t-1].T-cross[t-1]@Fnew.T+Fnew@Exx[t-1]@Fnew.T for t in range(1,len(x)))/(len(x)-1)
  cross_observation=sum(np.outer(x[t],m[t])for t in range(len(x)))
  Cnew=np.linalg.solve(sum(Exx).T,cross_observation.T).T
  Rnew=sum(np.outer(x[t],x[t])-np.outer(x[t],m[t])@Cnew.T-Cnew@np.outer(m[t],x[t])+Cnew@Exx[t]@Cnew.T for t in range(len(x)))/len(x)
  history.append({'iteration':step,'log_likelihood':filtered['log_likelihood']})
  F,C,Q,R=Fnew,Cnew,(Qnew+Qnew.T)/2,(Rnew+Rnew.T)/2;m0,P0=m[0],p[0]
  if step and abs(history[-1]['log_likelihood']-history[-2]['log_likelihood'])<=tolerance:break
 return {'F':F,'C':C,'Q':Q,'R':R,'m0':m0,'P0':P0,'optimizer_history':history,'input_role':'training_only','native_equivalence':False}

def hierarchical_schedule(A,B,D,fast_noise,slow_noise,trial_ids,boundary_policy):
 """Build 1slow+dfast clocks from an explicitly named qualified boundary rule."""
 import numpy as np
 if boundary_policy not in('carry_fast_use_previous_slow','reset_fast_at_trial_start'):raise ValueError('unbound hLDS boundary convention')
 d=A.shape[0];matrices=[];noise=[]
 for t,k in enumerate(trial_ids):
  boundary=t==0 or trial_ids[t-1]!=k;F=np.zeros((d+1,d+1));Q=np.zeros_like(F);F[0,0]=D if boundary else 1.;Q[0,0]=slow_noise if boundary else 0.
  if not boundary or boundary_policy=='carry_fast_use_previous_slow':F[1:,0]=B;F[1:,1:]=A
  Q[1:,1:]=fast_noise;matrices.append(F);noise.append(Q)
 return matrices,noise

def fit_hierarchical(train_counts,trial_ids,initial,iterations,tolerance,boundary_policy):
 """Structured1slow+10fast EM under an explicit prequalified clock policy.

 Original native equivalence remains unestablished. No silent covariance ridge,
 retry, skipped session or guessed native boundary convention is introduced.
 """
 import numpy as np
 x=np.sqrt(np.asarray(train_counts,float));A=np.asarray(initial['A'],float);B=np.asarray(initial['B'],float);D=float(initial['D']);Q=np.asarray(initial['fast_noise'],float);q=float(initial['slow_noise']);Cfast=np.asarray(initial['C'],float);R=np.asarray(initial['R'],float);m0=np.asarray(initial['m0'],float);P0=np.asarray(initial['P0'],float)
 if A.shape!=(10,10)or B.shape!=(10,)or len(x)!=len(trial_ids)or len(x)<2:raise ValueError('complete1slow10fast training geometry')
 within=[t for t in range(1,len(x))if trial_ids[t]==trial_ids[t-1]];boundary=[t for t in range(1,len(x))if trial_ids[t]!=trial_ids[t-1]]
 if not within or not boundary:raise ValueError('training requires within/across-trial support')
 history=[]
 for step in range(iterations):
  fs,qs=hierarchical_schedule(A,B,D,Q,q,trial_ids,boundary_policy);fs[0]=np.eye(11);qs[0]=np.zeros((11,11));C=np.column_stack((np.zeros(x.shape[1]),Cfast))
  filtered=filter_sequence(x,fs,qs,C,R,m0,P0,[np.ones(x.shape[1],bool)]*len(x));m,p,lag=training_smoother(filtered['filtered'],filtered['predicted'],fs)
  second=[p[t]+np.outer(m[t],m[t])for t in range(len(x))];cross={t:lag[t]+np.outer(m[t],m[t-1])for t in range(1,len(x))}
  fastrows=within if boundary_policy=='reset_fast_at_trial_start'else within+boundary
  denominator=sum(second[t-1]for t in fastrows);numerator=sum(cross[t][1:,:]for t in fastrows);coeff=np.linalg.solve(denominator.T,numerator.T).T;Bnew=coeff[:,0];Anew=coeff[:,1:]
  Dnew=sum(cross[t][0,0]for t in boundary)/sum(second[t-1][0,0]for t in boundary)
  qnew=sum(second[t][0,0]-2*Dnew*cross[t][0,0]+Dnew**2*second[t-1][0,0]for t in boundary)/len(boundary)
  fast_residual=sum(second[t][1:,1:]-coeff@cross[t][1:,:].T-cross[t][1:,:]@coeff.T+coeff@second[t-1]@coeff.T for t in fastrows)
  count=len(fastrows)
  if boundary_policy=='reset_fast_at_trial_start':fast_residual+=sum(second[t][1:,1:]for t in boundary);count+=len(boundary)
  Qnew=np.eye(10)*np.trace(fast_residual)/(10*count)
  obs_cross=sum(np.outer(x[t],m[t][1:])for t in range(len(x)));Cnew=np.linalg.solve(sum(z[1:,1:]for z in second).T,obs_cross.T).T
  Rnew=sum(np.outer(x[t],x[t])-np.outer(x[t],m[t][1:])@Cnew.T-Cnew@np.outer(m[t][1:],x[t])+Cnew@second[t][1:,1:]@Cnew.T for t in range(len(x)))/len(x)
  history.append({'iteration':step,'log_likelihood':filtered['log_likelihood']});A,B,D,Q,q,Cfast,R=Anew,Bnew,Dnew,Qnew,qnew,Cnew,(Rnew+Rnew.T)/2;m0,P0=m[0],p[0]
  if q<0 or not np.all(np.isfinite(Q)):raise ValueError('invalid ML covariance; no hidden regularization')
  if step and abs(history[-1]['log_likelihood']-history[-2]['log_likelihood'])<=tolerance:break
 return {'A':A,'B':B,'D':D,'fast_noise':Q,'slow_noise':q,'C':Cfast,'R':R,'m0':m0,'P0':P0,'optimizer_history':history,'boundary_policy':boundary_policy,'native_equivalence':False,'input_role':'training_only'}

def held_neuron_filter(model,peer_sqrt_counts,target_index,transition,noise,state):
 """Target loading trained previously; entire current test target excluded."""
 import numpy as np
 C=np.asarray(model['C']);mask=np.ones(C.shape[0],bool);mask[target_index]=False;x=np.zeros((1,C.shape[0]));x[0,mask]=peer_sqrt_counts
 result=filter_sequence(x,[transition],[noise],C,np.asarray(model['R']),state['mean'],state['covariance'],[mask]);m,p=result['filtered'][0]
 return {'prediction':float(C[target_index]@m),'state':{'mean':m,'covariance':p},'mode':'filter_only','target_test_observed':False}

def svd_coordinate_gauge(C,A,B,states):
 import numpy as np
 U,s,Vt=np.linalg.svd(C,full_matrices=False)
 if np.any(s<=0):raise ValueError('unidentified C-SVD gauge')
 T=np.diag(s)@Vt;Ti=np.linalg.inv(T)
 return {'C':U,'A':T@A@Ti,'B':T@B,'states':states@T.T,'T':T,'inverse':Ti,'native_exact_order_sign_qualification_required':True}
