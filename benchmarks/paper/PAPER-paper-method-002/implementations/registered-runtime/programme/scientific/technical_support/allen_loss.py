"""Selected exact soft-DTW/window definitions; no source runner or target literals."""
from functools import partial
import jax
import jax.numpy as jnp

def kth_cost_diag_impl(x, y, k, cost_fn=lambda x, y: (x - y) ** 2, penalty_fn=None):
    n, m = len(x), len(y)
    start_row, start_col = (-k,0)

    # Create arrays of row and column indices
    rows = jnp.arange(n) 
    cols = jnp.arange(m)
    rows = rows + start_row
    cols = cols + start_col
    rows = jnp.where(rows < 0, n , rows)
    cols = jnp.where(cols < 0, m , cols)

    # There seems to be jax.grad bug with out of bounds indices or inf values.
    # So we define our own backpropagation rule.
    x_k = jnp.take(x, rows, fill_value=jnp.inf)
    y_k = jnp.take(y, cols, fill_value=jnp.inf)
    c_k = jax.vmap(cost_fn)(x_k, y_k)

    if penalty_fn is not None:
        penalty_k = jax.vmap(penalty_fn)(rows, cols)
        c_k = c_k + penalty_k

    return c_k, x, y

@partial(jax.custom_vjp, nondiff_argnums=(3, 4))
@partial(jax.jit, static_argnames=("cost_fn", "penalty_fn"))
def kth_cost_diag(x, y, k, cost_fn=lambda x, y: (x - y) ** 2, penalty_fn=None):
    val, _, _ = kth_cost_diag_impl(x, y, k, cost_fn, penalty_fn)
    return val


def kth_cost_diag_fwd(x, y, k, cost_fn, penalty_fn):
    val, x, y = kth_cost_diag_impl(x, y, k, cost_fn, penalty_fn)
    return val, (x,y,k)

def kth_cost_diag_bwd(cost_fn, penalty_fn, res, g):
    x,y,k = res
    
    rows = jnp.arange(x.shape[0]) 
    cols = jnp.arange(y.shape[0])
    rows = rows - k
    cols = cols
    
    grad_x = jax.vmap(jax.grad(cost_fn, argnums=0))(x[rows], y[cols])
    grad_y = jax.vmap(jax.grad(cost_fn, argnums=1))(x[rows], y[cols])
    
    # Initialize zero gradients for x and y
    zero_grad_x = jnp.zeros_like(x)
    zero_grad_y = jnp.zeros_like(y)

    # Scatter updates only to the indices used in the forward pass
    grad_x_full = zero_grad_x.at[rows].add(grad_x * g)
    grad_y_full = zero_grad_y.at[cols].add(grad_y * g)

    return grad_x_full, grad_y_full, None

kth_cost_diag.defvjp(kth_cost_diag_fwd, kth_cost_diag_bwd)

def pad_inf(inp, before, after):
    return jnp.pad(inp, (before, after), constant_values=jnp.inf)

@partial(jax.jit, static_argnames=("cost_fn", "penalty_fn"))
def dtw_distance(x, y, cost_fn=lambda x, y: (x - y) ** 2, penalty_fn=None):
    # Highly optimized linear memory and parallel time algorithm.
    
    H, W = x.shape[0], y.shape[0]
    x = x[::-1]  # Get antidiagonals...

    two_ago = kth_cost_diag(x, y, -H + 1, cost_fn=cost_fn, penalty_fn=penalty_fn)
    one_ago = (
        kth_cost_diag(x, y, -H + 2, cost_fn=cost_fn, penalty_fn=penalty_fn) + two_ago[0]
    )
    
    init = (
            pad_inf(two_ago, 1, 0),
            pad_inf(one_ago, 1, 0)
    )

    def scan_step(carry, k):
        two_ago, one_ago = carry
        current_antidiagonal = kth_cost_diag(
            x, y, k, cost_fn=cost_fn, penalty_fn=penalty_fn
        )

        diagonal = two_ago[:-1]
        right    = one_ago[:-1]
        down     = one_ago[1:]
        best     = jnp.min(jnp.stack([diagonal, right, down], axis=-1), axis=-1)

        next_row = best + current_antidiagonal
        next_row = pad_inf(next_row, 1, 0)

        return (one_ago, next_row), None

    ks = jnp.arange(-H + 3,H)

    carry, ys = jax.lax.scan(scan_step, init, ks, unroll=8)
    return carry[1][-1]


def softmin_impl(x, gamma=1.):
    return -gamma * jax.scipy.special.logsumexp(x / -gamma, axis=-1)

softmin = jax.custom_vjp(softmin_impl, nondiff_argnums=(1,))

def softmin_fwd(array, gamma):
    return softmin(array, gamma), (array / -gamma, )

def softmin_bwd(_,res, g):
    scaled_array, = res
    grad = jnp.where(jnp.isinf(scaled_array),
        jnp.zeros(scaled_array.shape),
        jax.nn.softmax(scaled_array) * jnp.expand_dims(g, -1)
    )
    return grad,

softmin.defvjp(softmin_fwd, softmin_bwd)

@partial(jax.jit, static_argnums=(2, 3, 4))
def soft_dtw_distance(
    x, y, gamma=1.0, cost_fn=lambda x, y: (x - y) ** 2, penalty_fn=None
):
    
    H, W = x.shape[0], y.shape[0]

    x = x[::-1]
    two_ago = kth_cost_diag(x, y, -H + 1, cost_fn=cost_fn, penalty_fn=penalty_fn)
    one_ago = (
        kth_cost_diag(x, y, -H + 2, cost_fn=cost_fn, penalty_fn=penalty_fn) + two_ago[0]
    )
    
    
    init = (
            pad_inf(two_ago, 1, 0),
            pad_inf(one_ago, 1, 0)
    )

    def scan_step(carry, k):
        two_ago, one_ago = carry
        current_antidiagonal = kth_cost_diag(
            x, y, k, cost_fn=cost_fn, penalty_fn=penalty_fn
        )

        diagonal = two_ago[:-1]
        right    = one_ago[:-1]
        down     = one_ago[1:]

        best     = softmin(jnp.stack([diagonal, right, down], axis=-1),gamma=gamma)

        next_row = best + current_antidiagonal
        next_row = pad_inf(next_row, 1, 0)

        return (one_ago, next_row), None

    ks = jnp.arange(-H + 3,H)

    carry, _ = jax.lax.scan(scan_step, init, ks, unroll=4)
    return carry[1][-1]


def window_reduce(x, reduce_fn, window_size=100, stride=50):
    ids = jnp.arange(window_size,x.shape[0], stride)
    
    def scan_fn(x, i):
        start = i - window_size
        x_val = jax.lax.dynamic_slice(x, (start,), (window_size,))
        val = reduce_fn(x_val)
        return x,val
    
    return jax.lax.scan(scan_fn, x, ids)[-1]
