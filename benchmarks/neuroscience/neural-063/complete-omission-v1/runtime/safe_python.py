"""Restricted scientific Python used equally in G/R and F/I.

This is capability reduction in addition to a fresh kernel-isolated container;
it is not claimed to be a security sandbox on its own. No imports, filesystem,
reflection, subprocess, object dtypes or checkpoint access are exposed to scripts.
"""
import ast

class ScriptError(ValueError): pass
NAMES={'abs','min','max','sum','len','range','enumerate','zip','sorted','float','int','bool','list','dict','tuple','round','all','any','print','plot','np','sp','math','data','inputs','artifacts','result'}
NUMPY={'array','asarray','zeros','ones','eye','arange','linspace','concatenate','stack','column_stack','row_stack','vstack','hstack','mean','median','std','var','sum','prod','min','max','argmin','argmax','argsort','sort','clip','where','isfinite','isnan','isinf','sqrt','square','abs','exp','log','log1p','tanh','sin','cos','diff','gradient','cumsum','cumprod','percentile','quantile','reshape','transpose','einsum','dot','matmul','outer','diag','diagonal','triu','tril','unique','bincount','histogram','searchsorted','interp','cov','corrcoef','meshgrid','repeat','tile','take','ravel','flatten','squeeze','nanmean','nanstd','nanmedian','nan_to_num','polyfit','polyval','convolve','pi','e','inf','nan','float64','int64','bool_','newaxis','linalg','fft'}
LINALG={'solve','lstsq','svd','qr','eigh','eigvalsh','cholesky','inv','pinv','norm','cond','matrix_rank','det','slogdet'}
FFT={'fft','ifft','rfft','irfft','fftfreq','rfftfreq','fftshift','ifftshift'}
SCIPY={'linalg','signal','stats','special','optimize','interpolate','integrate'}
SCIPY_CALLS={'linalg':LINALG|{'cho_factor','cho_solve','svdvals','solve_triangular'},'signal':{'savgol_filter','butter','sosfilt','sosfiltfilt','detrend','resample','resample_poly','correlate','welch','find_peaks'},'stats':{'zscore','rankdata','pearsonr','spearmanr','linregress','norm','t','describe'},'special':{'expit','logit','softmax','logsumexp','erf','gammaln'},'optimize':{'minimize','least_squares','curve_fit','nnls','lsq_linear'},'interpolate':{'interp1d','CubicSpline','PchipInterpolator'},'integrate':{'trapezoid','simpson','cumulative_trapezoid'}}
METHODS={'shape','size','ndim','T','dtype','mean','sum','std','var','min','max','argmin','argmax','reshape','ravel','flatten','transpose','squeeze','astype','copy','tolist','item','get','keys','values','items','append','extend','count','index'}
MATH={'sqrt','exp','log','log1p','sin','cos','tanh','fabs','floor','ceil','isfinite','fsum','pi','e'}
FORBIDDEN=(ast.Import,ast.ImportFrom,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef,ast.Await,ast.With,ast.AsyncWith,ast.Try,ast.Raise,ast.Delete,ast.Global,ast.Nonlocal,ast.While,ast.Yield,ast.YieldFrom)

def validate_code(code):
 if not isinstance(code,str) or not code or len(code.encode())>1_000_000: raise ScriptError('bounded nonempty scientific script required')
 tree=ast.parse(code,'<scientific-script>','exec')
 assigned=set(NAMES)
 for node in ast.walk(tree):
  if isinstance(node,FORBIDDEN): raise ScriptError('unsupported scientific script capability')
  if isinstance(node,ast.Name):
   if node.id.startswith('_'): raise ScriptError('private/reflection names denied')
   if isinstance(node.ctx,ast.Store): assigned.add(node.id)
  if isinstance(node,ast.arg): assigned.add(node.arg)
 for node in ast.walk(tree):
  if isinstance(node,ast.Name) and node.id not in assigned: raise ScriptError('unprovided name: '+node.id)
  if isinstance(node,ast.Attribute):
   if node.attr.startswith('_'): raise ScriptError('private/reflection attributes denied')
   root=node.value
   if isinstance(root,ast.Name) and root.id=='np': ok=node.attr in NUMPY
   elif isinstance(root,ast.Name) and root.id=='sp': ok=node.attr in SCIPY
   elif isinstance(root,ast.Name) and root.id=='math': ok=node.attr in MATH
   elif isinstance(root,ast.Attribute) and isinstance(root.value,ast.Name) and root.value.id=='np': ok=(root.attr=='linalg' and node.attr in LINALG) or (root.attr=='fft' and node.attr in FFT)
   elif isinstance(root,ast.Attribute) and isinstance(root.value,ast.Name) and root.value.id=='sp': ok=node.attr in SCIPY_CALLS.get(root.attr,set())
   else: ok=node.attr in METHODS
   if not ok: raise ScriptError('unprovided scientific attribute: '+node.attr)
  if isinstance(node,ast.Call):
   for kw in node.keywords:
    if kw.arg=='dtype' and not (isinstance(kw.value,ast.Attribute) and isinstance(kw.value.value,ast.Name) and kw.value.value.id=='np' and kw.value.attr in {'float64','int64','bool_'}): raise ScriptError('only explicit numeric dtypes allowed')
  if isinstance(node,ast.Constant) and isinstance(node.value,str) and ('__' in node.value or '\x00' in node.value): raise ScriptError('reflection/binary strings denied')
 return tree
