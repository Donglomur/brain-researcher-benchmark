d=50
alpha=0#1.2

P=200
Qs=np.power(10,np.linspace(np.log10(10),np.log10(1000),10)).astype(int)
#Q=12

dia=jnp.power(jnp.arange(d)+1,-alpha)
M=jnp.diag(jnp.sqrt(dia))

gamma=jnp.square(jnp.sum(dia))/jnp.sum(jnp.square(dia))
print(gamma)

# Random seed initialization
key = random.PRNGKey(0)

numit=200
anss=[]
for Q in Qs:
    ans=[]
    for i in range(numit):
        # Generate a P x d matrix with normally distributed entries
        key, subkey = jax.random.split(key)
        X = random.normal(key, shape=(P, d))
        key, subkey = jax.random.split(key)
        W = random.normal(key, shape=(d, Q))
        
        Phi=jnp.matmul(jnp.matmul(X,M),W)/d
        #ans.append([getest_all(Phi,P,Q)])
        ans.append([getest_all0(Phi,Phi,P,Q)])
    anss.append(ans)
anss=np.squeeze(np.array(anss))

