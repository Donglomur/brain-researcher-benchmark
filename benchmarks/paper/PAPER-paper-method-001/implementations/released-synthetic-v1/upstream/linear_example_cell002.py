fig,ax=plt.subplots(1,1,figsize=(2.5,2.5))

fig2,ax2=plt.subplots(1,1,figsize=(2.5,2.2))

ms=7

alpha=0.7

xoi=Qs

ls='-'
lw=1.5

colorvs=['k','g','g','r']
markers=['o','>','<','x']
labels=[r'$\hat{\gamma}_0$', r'$\hat{\gamma}_r$', r'$\hat{\gamma}_c$',r'$\hat{\gamma}$',r'$\hat{\gamma}$']
for i,(colorv,marker,label) in enumerate(zip(colorvs,markers,labels)):
    denom=anss[:,:,i,1]
    numer=anss[:,:,i,0]

    qoi=numer/denom #(num_so_Q_it/np.sqrt(de2_so_a_Q_it*de2_so_b_Q_it))[:,:,i,1]
    
    yval=np.nanmedian(qoi,axis=1)
    lower_error=np.nanquantile(qoi,axis=1,q=0.25)
    upper_error=np.nanquantile(qoi,axis=1,q=0.75)
    asymmetric_error = [yval-lower_error, upper_error-yval]
    ax.errorbar(xoi, yval, yerr=asymmetric_error,c=colorv,marker='',ls='',alpha=1,lw=1,zorder=0)#, fmt='o')
    yval=np.nanmean(qoi,axis=1)
    ax.plot(xoi, yval,c=colorv,marker=marker,ls=ls,alpha=alpha,ms=ms,lw=lw,zorder=0,fillstyle='none',label=label)#, fmt='o')

    ax2.plot(xoi, np.mean(np.square(gamma-qoi),axis=1),c=colorv,marker=marker,ls=ls,alpha=alpha,ms=ms,lw=lw,zorder=0,fillstyle='none',label=label )
    #ax.plot(xoi, np.mean(numer,axis=-1)/np.mean(denom,axis=-1),c=colorv)
ax.plot(xoi,xoi*0+gamma,c='b',label=r'$\gamma$',zorder=-10,alpha=0.5,lw=3)
ax.plot(xoi,1/(1/xoi+1/P+1/gamma),c='m',ls='-',alpha=0.5,lw=3,label=r'$\frac{1}{\gamma} + \frac{1}{P} + \frac{1}{Q}$')
#ax.legend()
ax.legend(loc='upper left', bbox_to_anchor=(1.05, 1))
ax.set_xlabel('Q')
ax.set_xscale('log')
ax.set_ylabel(r'$\gamma$')



fig.savefig("linear_dim.pdf", bbox_inches='tight')

ax2.legend(loc='upper left', bbox_to_anchor=(1.05, 1))
ax2.set_ylabel('MSE')
ax2.set_xlabel('Q')
ax2.set_xscale('log')
ax2.set_yscale('log')

fig2.savefig("linear_dim_mse.pdf", bbox_inches='tight')
