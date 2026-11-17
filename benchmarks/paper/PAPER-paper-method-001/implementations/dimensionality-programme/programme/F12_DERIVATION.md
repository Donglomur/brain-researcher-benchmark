# F12: certified finite-radius centered-kernel population truth

This document supplies a mathematical derivation and an executable-source
construction, not an executed scientific result. `finite_ball_truth.py` has not
been imported or run. Numerical qualification, the protected runtime, complete
source review, and the original programme's 24 gates remain outstanding. The
derivation is local to the explicitly specified prospective F12 distribution; it
does not recover an absent original-paper figure producer.

## Target and interface

Let `X` be uniform on the Euclidean ball of radius `a` centered at zero in `d`
dimensions. The exact grid is
`d in {1,2,3,5,8}` and `a in {1/20,1/10,1/5,7/20,1/2,3/4}`.
All expectations below use independent copies of `X`. The feature is
`sin(W.X+b)`, with independent `W ~ N(0,I_d)` and `b` uniform on
`[-pi/2,pi/2]`. The target is the participation ratio of the population feature
covariance after centering across `X`. It is not the sample covariance PR, a
random-feature approximation, or intrinsic dimension `d`.

The issuer-only producer interface is:

```python
truth(dimension, radius_fraction)
# radius_fraction: Fraction or [integer numerator, positive integer denominator]
# returns {'gamma': float, 'certificate': JSON-compatible rational bounds}
```

Binary float radii are rejected. Integer pairs must be the canonical pairs
listed above, checked before fraction construction; this prevents unbounded
integer-normalization work from a noncanonical representation. For example,
the caller supplies `(7,20)`, not `.35`. No observation array, seed, fitted model, candidate output, or
estimated rank is an input to truth. The generator must use its already sealed
private dimension and exact cell radius. A `TruthCertificateError` is a failed
required preparation, never an invitation to substitute dimension or an
estimated truth. The complete certificate and emitted scalar are protected
preparation products; only the scalar authorized for the appropriate
development/calibration or protected evaluation lane may subsequently be
released. The parent controller remains responsible for namespace, source
identity, receipt, output-binding and access-barrier enforcement.

## Kernel and covariance identities

The product-to-sum identity gives

`sin(u+b) sin(v+b) = [cos(u-v) - cos(u+v+2b)] / 2`.

The second cosine averages to zero over the phase interval, a complete period
of `2b`. The Gaussian characteristic function then gives

`k(x,y) = E_(W,b)[sin(W.x+b) sin(W.y+b)]
        = (1/2) exp(-||x-y||^2/2)`.

Write `phi_x` for the feature as an element of the Hilbert space over `(W,b)`;
its squared norm is `k(x,x)=1/2`. Its mean is `mu=E phi_X` and its positive
trace-class covariance is `C=E[(phi_X-mu) tensor (phi_X-mu)]`. Bounded norms
justify all expectation interchanges below. Define

`alpha = E k(X,Y)`, `beta = E k(X,Y)^2`,
`m(x)=E_Y k(x,Y)`, and `eta = E_X m(X)^2 = E k(X,Y) k(X,Z)`.

Then `||mu||^2=alpha` and

`T = tr(C) = 1/2 - alpha`.

The centered kernel is `kc(x,y)=k(x,y)-m(x)-m(y)+alpha`.
Expanding its square under independent `X,Y` gives

`D = tr(C^2) = E kc(X,Y)^2 = beta - 2 eta + alpha^2`.

For clarity, `E[k(X,Y)m(X)] = eta`, `E[m(X)m(Y)]=alpha^2`,
and `E[m(X)]=alpha`; collecting these terms yields the stated expression.
The finite-radius population truth is `gamma = T^2/D`.

The three integrations therefore reduce to

`alpha = (1/2) E exp(-S/2)`,
`beta = (1/4) E exp(-S)`,
`eta = (1/4) E exp(-H/2)`,

where `S=||X-Y||^2` and `H=||X-Y||^2+||X-Z||^2`.
The shared `X` in `eta` is essential. Squaring an unconditional pair mean would
produce `alpha^2` instead of `eta` and would give the wrong centered target.

## Exact polynomial integration over balls

For a uniform ball, radius and direction are independent. The radial density is
`d r^(d-1)/a^d` for `0 <= r <= a`, so for every nonnegative integer `s`,

`M_s = E ||X||^(2s) = d a^(2s)/(d+2s)`.

For a uniform unit-sphere direction `U` and fixed unit vector `e`, sign symmetry
makes odd projection moments zero, and the even moments are

`S_j = E (U.e)^(2j)
     = (1*3*...*(2j-1)) / [d(d+2)...(d+2j-2)]`, `S_0=1`.

One derivation for `d>1` is to integrate the first-coordinate sphere density
proportional to `(1-u^2)^((d-3)/2)` and apply the beta-integral recurrence;
equivalently, normalized independent standard Gaussian coordinates give the
same recurrence `S_j/S_(j-1)=(2j-1)/(d+2j-2)`. For `d=1`, the direction is
uniform on `{-1,+1}`, and the displayed formula also equals one. Thus this
identity covers every selected dimension without a limiting implementation.

Put `A=||X||^2`, `B=||Y||^2`, `F=||Z||^2`, `U=X.Y`, `V=X.Z`.
Conditional on the radii and the direction of `X`, the projections onto `Y`
and `Z` are independent. Consequently,

`E[A^p B^q U^(2j)] = M_(p+j) M_(q+j) S_j`,

`E[A^p B^q F^r U^(2i) V^(2j)]
 = M_(p+i+j) M_(q+i) M_(r+j) S_i S_j`.

An odd power of either dot product vanishes after flipping the corresponding
independent vector `Y` or `Z`. These identities integrate every term in the
finite multinomial expansions, without discretizing the ball or sampling it.

For the pair distance,

`E S^n = sum_(p+q+2j=n)
 [n!/(p! q! (2j)!)] 2^(2j) M_(p+j) M_(q+j) S_j`.

For the shared-center distance sum,

`E H^n = sum_(p+q+r+2i+2j=n)
 [n!/(p! q! r! (2i)! (2j)!)]
 2^(p+2i+2j) M_(p+i+j) M_(q+i) M_(r+j) S_i S_j`.

These are exactly `_pair_distance_moment` and `_shared_distance_moment`.
All nonzero terms are nonnegative; the negative dot-product signs disappear
only because their surviving exponents are even. At `n=0`, each formula is
one. The degree indices never exceed 25 in this implementation. Every radius
is rational, so every moment, coefficient and subsequent finite sum is a
`Fraction`. No floating arithmetic enters these integrations.

## Deterministic Taylor enclosure

For `q >= 0`, Taylor's theorem with its signed Lagrange remainder gives

`P_25(q) <= exp(-q) <= P_24(q)`,
`P_N(q)=sum_(n=0)^N (-q)^n/n!`.

This inequality does not require the individual series terms to decrease.
Its sign follows from the `(N+1)`st derivative `(-1)^(N+1) exp(-xi)`.
The gap between these adjacent polynomials is `q^25/25!`. The three integrands
have `q=S/2`, `q=S`, and `q=H/2`. Since `||X-Y|| <= 2a`, all are bounded by
`qmax=4a^2 <= 9/4`. Integrating the polynomial bounds with the exact moments
therefore encloses each exponential expectation. Intersecting with `[0,1]`
is valid and can only improve the enclosure.

Let `delta=(4a^2)^25/25!`. Each exponential expectation has interval width at
most `delta`. Uniformly over the grid,

`delta <= (9/4)^25/25! < 5e-16`.

A coarse entirely rational verification is
`(9/4)^25=(9/4)*(81/16)^12 < (9/4)*6^12 < 5,000,000,000`
and `25! = 15,511,210,043,330,985,984,000,000 > 10^25`.
No rounded exponential or numerical integration is used to certify the error.

## Denominator positivity and uniform termination

The algebraic kernel expansion

`k(x,y)=(1/2) e^(-||x||^2/2) e^(-||y||^2/2)
        sum_alpha x^alpha y^alpha / alpha!`

is an explicit positive feature representation. Among its features are
`psi_j(x)=2^(-1/2) e^(-||x||^2/2) x_j`, for `j=1,...,d`.
Each has mean zero by sign symmetry. If `v_j=Var(psi_j(X))`, then

`v_j = (1/2) E[e^(-||X||^2) X_j^2]
     >= (1/2) e^(-a^2) a^2/(d+2)`.

The trace of the covariance is the sum of all feature variances, so
`T >= d a^2 e^(-a^2)/[2(d+2)]`. Its squared Hilbert-Schmidt norm is the sum of
the squares of every feature-covariance entry; retaining only these `d`
diagonal entries yields

`D >= d a^4 e^(-2a^2)/[4(d+2)^2] > 0`.

These inequalities are valid for the population covariance regardless of the
chosen equivalent Hilbert-space feature representation. They do not assume
that the covariance has rank `d`.

Use `e^(-u) >= 1-u` with `u=a^2/2`. Since `a<=3/4`,

`e^(-a^2) >= (1-a^2/2)^2 >= (23/32)^2 > 1/2`,
`e^(-2a^2) >= (1-a^2/2)^4 > 1/4`.

These rational lower bounds are inserted in the source before division. They
give the convenient uniform bounds `T >= 1/4800` and `D >= 1/32,000,000`:
`d/(d+2)>=1/3`, `d/(d+2)^2>=2/25` over the selected dimensions, and
`a^2>=1/400`, `a^4>=1/160000`.

The covariance is positive trace-class, so `T^2 >= D` and `gamma>=1`.
Also `1-e^(-u)<=u` implies
`T=(1/2)E[1-e^(-S/2)] <= E S/4 = d a^2/[2(d+2)]`.
Combining this with the lower bound on `D` gives
`gamma <= d e^(2a^2) < 4d <= 32`.
Thus the source may safely intersect the final enclosure with `[1,4d]`,
and this analytic target is within the accepted `[1,128]` truth support.

If the raw `alpha`, `beta` and `eta` intervals have widths at most
`delta/2`, `delta/4` and `delta/4`, then `T` has width at most `delta/2`.
Because `alpha` is in `[0,1/2]`, the `alpha^2` interval has width at most
`delta/2`. Consequently the `D` interval has width at most `5 delta/4`.
Intersecting with the independent positive lower bounds cannot increase
these widths. The final PR interval `[L,U]` therefore satisfies

`U/L <= (1+2400 delta)^2 (1+40,000,000 delta)`.

With `delta<5e-16`, the right-hand side minus one is less than `1e-7`,
comfortably below the specified `1e-5` logtruth error ceiling. This proves
that degree 24/25 is sufficient for the entire finite grid. There is no
unbounded convergence loop, adaptive tolerance tuning, or future recipe to
choose. Inconsistent intervals are typed source/certificate failures, not
usable partial truth values.

## Interval propagation and emitted float

For nonnegative `alpha in [a0,a1]`, `beta in [b0,b1]`, and
`eta in [h0,h1]`, the source uses

`T in [1/2-a1, 1/2-a0]`,
`D in [b0-2h1+a0^2, b1-2h0+a1^2]`.

The exact rational positive bounds above intersect the lower endpoints.
For positive `T,D`, monotonicity gives
`gamma in [T_lower^2/D_upper, T_upper^2/D_lower]`.
Dependence between `alpha`, `beta` and `eta` only makes this enclosure
conservative; independent interval arithmetic does not assume independent
statistical errors.

The midpoint is converted to a Python float `g`. The source immediately
recovers its *actual* exact rational value with `g.as_integer_ratio()`, so
rounding of this final conversion is included rather than ignored. For every
true target `t in [L,U]`,

`|log(g/t)| <= max(0, g/L-1, U/g-1)`.

This follows separately for `g>=t` and `g<=t` from `log(v)<=v-1` for `v>0`.
The returned certificate contains this exact rational bound and admits the
scalar only if it is at most `1/100000`. There is no computation of a rounded
logarithm in the proof or certificate. All intermediate and final intervals,
the exact emitted float fraction, and the selected method identity are retained.

## Finite resource bounds and failure policy

Only degrees 0 through 25 are evaluated. A deliberately loose enumeration
bound is `26*13*26` pair terms plus `26*13*13*26*26` shared-center terms,
which totals 2,979,132, below the hard source ceiling of 3,000,000. The source
increments its counter before every term; this is a polynomial-term bound,
not a claim to have measured CPU, memory, file I/O, or elapsed time. The future
issuer must reserve and measure those resources under the original controller.

There are 26 factorials, 26 radial moments, 13 sphere moments and two lists of
26 distance moments. Loops retain only one term accumulator per moment. A
common denominator for all integrated Taylor terms divides a product of
`20^50`, `2^25`, `25!`, the factors `(d+2s)^3` for `s=0,...,25`, and the
squared product of `(d+2j)` for `j=0,...,12`. This deliberately redundant
common denominator is below `2^1100`; the bounded degree and input domain
therefore also bound rational integer sizes. The source is not a general
arbitrary-radius or arbitrary-dimension integration service.

Invalid dimensions/radii, exceeding the fixed term ceiling, inconsistent
intervals, a nonpositive denominator, nonfinite conversion, or a failed exact
log-error check raise `TruthCertificateError`. No failed seed is dropped,
no precision is silently weakened, and no expensive procedure is retried with
a fresh budget or clock. There is no RNG and no Monte Carlo uncertainty.

## Qualification limits

The source and these derivations require independent review. The authored
AST controls check the closed interface, polynomial structure, bounded loops,
protected-call contract and exact-certificate construction. They deliberately
do not call any integration or truth function, even on a small invented case.
Future authorized numerical qualification should separately compare this
implementation against an independent certified method, exercise all 30
dimension/radius combinations, verify resource closure, and validate the full
protected generator and preparation artifact path. Those are future gates;
they were not run here and are not replaced by the source proof.
