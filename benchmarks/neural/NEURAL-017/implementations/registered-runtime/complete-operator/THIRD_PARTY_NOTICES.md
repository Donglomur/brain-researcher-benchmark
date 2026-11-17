# Third-party notices and source attribution

The project-level license remains the repository's LICENSE. It does not replace applicable third-party notices or grant rights to external papers, datasets, numerical libraries or model outputs.

## Neural Latents Benchmark source

The source-bound organizer is [neurallatents/nlb_tools](https://github.com/neurallatents/nlb_tools), revision `42f8410b88e12db136910fa2f888b025ea0aa2ae`. The included source adapts its task alignment/conversion conventions (`nlb/raw_primitives.py`, `raw_counts.py`, `raw_prepare.py`), smoothing/Poisson recipes (`nlb/scientific/glm.py`) and GPFA search/observed-query readout recipes (`nlb/scientific/gpfa.py`). `nlb/metric_core.py` independently implements the co-smoothing equation with the explicitly documented strict-domain/error distinctions. These are attributed adapted or independent implementations, not a byte-identical upstream checkout. Exact algorithms and deviations are documented in design/REFERENCE_METHODS.md and design/METRICS_AND_UNCERTAINTY.md.

The full notice below is reproduced verbatim from the retained `../public/NLB_LICENSE` (1,071 bytes; SHA-256 `6b79a9e581f330f2ec31a227b162f5b7950021fd9152203729ec7ad5bc2d9f7f`). This records the retained notice and selected source attribution, without claiming a new upstream license retrieval at that revision.

```text
MIT License

Copyright (c) 2022 Neural Latents

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## External materials

No Elephant, Neo, quantities, NumPy, SciPy, scikit-learn, pandas, h5py or other external library implementation is bundled. Dependency/source pins are declarations, not installations or a replacement for those distributions' applicable licenses and nested notices. A later independently selected environment must retain its actual notices.

The task's existing data attribution identifies DANDI 000128/version 0.220113.0400 and its stated CC BY 4.0 terms, with Churchland et al. and the Neural Latents Benchmark as scientific sources. No dataset or primary paper body is included here. Licensed participant contexts and any later model/service outputs require their own applicable rights; no blanket redistribution permission is created by this source release.
