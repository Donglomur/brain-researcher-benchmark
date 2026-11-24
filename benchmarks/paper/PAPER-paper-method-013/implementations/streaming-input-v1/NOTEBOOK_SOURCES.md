# Authenticated author notebook source

The exact three pinned author notebooks were authenticated on 24 November 2026:
725,049 original bytes in total, with matching Git blob SHA1, SHA256 and declared
sizes. Extracting their code cells reproduces all three previously retained source
exports byte-for-byte. This closes the old notebook-body authentication gap; the
November17 TLS failures remain historical evidence, and their descriptions remain
in PROVENANCE.json under previous_body_authentication.

The source revision is
[305a4827929b2c6e82e44c5c69b2ea9d410e20a4](https://github.com/KangningZhang/DeepCaImX/tree/305a4827929b2c6e82e44c5c69b2ea9d410e20a4).
[MANIFEST.json](author-code/MANIFEST.json) binds every original notebook, each
literal code-cell source, and each derived text file. These author-code text files
are covered by the retained [MIT license](LICENSE.author). Markdown, cell outputs,
execution counts, plots and embedded notebook images are excluded. The `.py.txt`
suffix marks source text, not a runnable or repaired training package.

| Original notebook | Code-only export | Original bytes | Export bytes |
| --- | --- | ---: | ---: |
| Full testing demo | [testing.source.py.txt](author-code/testing.source.py.txt) | 603,568 | 9,705 |
| Full training demo | [training.source.py.txt](author-code/training.source.py.txt) | 47,339 | 37,981 |
| Experimental preprocessing | [preprocessing.source.py.txt](author-code/preprocessing.source.py.txt) | 74,142 | 3,507 |

## Reproduce the source extraction

Provision only the three original pinned notebooks in an external input directory
as `testing.ipynb`, `training.ipynb` and `preprocessing.ipynb`. The script performs
no network requests. The output directory must be fresh and its parent must exist.
All three originals must authenticate before any output directory is created.

```sh
python -I -B notebook_sources.py \
  --input-dir /external/author-notebooks \
  --output-dir /external/source-exports
```

The extractor preserves every character in each code cell. It prefixes the code
with its zero-based original cell index, joins cells with two newlines and appends
one final newline. It authenticates the resulting export digest as well. Static
`ast.parse` reports syntax; it does not import author modules, evaluate notebook
cells, load weights or run a model. Parsing successfully does not establish that a
cell's dependencies, runtime behavior or scientific method are correct.

## Literal upstream syntax and scientific scope

The training model-definition cell is ordinary Python, not an IPython/shell magic.
Notebook cell3, cell line120 (export line136) contains `self.128`, which static
Python parsing rejects. Export lines137–139 likewise contain numeric attributes
`self.64`, `self.32` and `self.16`; line140 preserves malformed `s'tanh'` text.
These tokens are deliberately unchanged. The manifest reports the first syntax
error encountered in that cell, not an exhaustive compiler diagnostic. This is a
static source finding and no new full-training execution was attempted.

The source remains a released N=8 demonstration. Byte authentication does not
establish equivalence to the paper's N=15/P9 model or its original trained weights.
The preprocessing notebook starts from an already prepared experimental MAT;
it does not determine the raw Allen frame-index base or512-to488 crop origin.
Testing/demo display code does not supply the original full-panel assembler,
segmentation threshold or missing temporal support. All original mapping,
checkpoint, trace/assembly and scientific qualification holds remain in force.

The maintained streaming producer and decoder are unchanged. Its geometry,
source endpoints, complete ten-recording population, metric and failure behavior
are not altered by this source recovery.

Generated controls exercise source-identity rejection before JSON parsing,
output/markdown removal without code execution, preservation of syntax failures,
complete-input admission and refusal to overwrite an existing output directory:

```sh
python -I -B -m unittest discover -s tests -p 'test_notebook_sources.py' -v
```

## Historical source generations

[The historical source crosswalk](HISTORICAL_SOURCES.md) preserves an earlier
N15/nine-stage prototype and distinguishes its 1,000-frame interfaces from the
paper's 400-frame experimental condition and the later N=8 demo above. It also
records why historical STNeuroNet annotation attribution does not authenticate
the original DeepCaImX crop or frame mapping. The three current notebook exports
and their static syntax findings remain unchanged.
