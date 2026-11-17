# NIDER numerical reporting controls

This package checks a numerical reporting criterion with invented inputs. It
contains the unchanged authored criterion and the complete 77-control suite:
268 assertions in five groups, including ten scale-projection controls.

The criterion accepts numerical submissions for three contrasts, each with a
Pearson correlation, two-sided probability, study count and sample count.
Reporting comparisons use the displayed decimal precision and exact rational
intervals. Exact ties and intervals crossing a rounding boundary are indeterminate.
Counts must agree exactly. A separate Fisher-z-to-Pearson projection preserves
the original serialized values. R-formatted table strings never determine scores.

The controls cover incomplete support, duplicate/nonfinite JSON, domain errors,
reporting boundaries, display-string independence and an independently derived
higher-order certificate for the rational scale enclosure. A first failure is
retained with actual attempted/completed counts; later controls are not reported
as executed.

On Linux with CPython 3.11.18, run:

```sh
python -I -S -B run_synthetic.py --out /tmp/nider-reporting-example
```

The output directory must be new. The runner records every control result,
source hashes and the observed Python runtime. It uses a 29-second alarm,
30-second CPU limit and 2 GiB address-space limit. CI additionally bounds the
outer command and retains its original streams and exit status.

No authentic data, published answer values, original-author code, native fits or
model calls are included. Passing these controls does not establish paper
reproduction, scientific improvement, a qualified benchmark or secure execution
of arbitrary candidate programs. Agreement with values printed in a paper also
cannot establish that a submission computed those values; protected procedure
checks remain separate.
