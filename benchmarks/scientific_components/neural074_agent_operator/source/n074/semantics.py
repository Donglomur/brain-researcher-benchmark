"""One training-only feature transform shared by all prospective reference arms."""
from dataclasses import dataclass
import re
from .contracts import require


def tokens(text):
    return tuple(re.findall(r'[a-z][a-z0-9_]*', text.lower()))


@dataclass(frozen=True)
class Features:
    vocabulary: tuple
    inverse_document_frequency: tuple
    design_terms: tuple
    training_endpoints: tuple

    def transform(self, designs):
        import numpy as np
        word_index = {v: i for i, v in enumerate(self.vocabulary)}
        design_index = {v: i + len(self.vocabulary) for i, v in enumerate(self.design_terms)}
        out = np.zeros((len(designs), len(self.vocabulary) + len(self.design_terms)), dtype=float)
        require(len({d.endpoint for d in designs}) == len(designs), 'Duplicate design row')
        for row, design in enumerate(designs):
            design.validate()
            for word in tokens(design.text):
                if word in word_index:
                    out[row, word_index[word]] += 1.0
            out[row, :len(self.vocabulary)] *= np.asarray(self.inverse_document_frequency)
            norm = np.linalg.norm(out[row, :len(self.vocabulary)])
            if norm > 0:
                out[row, :len(self.vocabulary)] /= norm
            for term, value in design.coefficients:
                if term in design_index:
                    out[row, design_index[term]] = value
        require(np.isfinite(out).all(), 'Nonfinite semantic/design feature')
        return out


def fit_features(designs):
    import math
    require(bool(designs), 'No training designs')
    require(len({d.endpoint for d in designs}) == len(designs), 'Duplicate training design')
    for d in designs:
        d.validate()
    vocabulary = tuple(sorted({w for d in designs for w in tokens(d.text)}))
    terms = tuple(sorted({term for d in designs for term, _ in d.coefficients}))
    require(bool(vocabulary or terms), 'No training semantic/design features')
    counts = {w: sum(w in set(tokens(d.text)) for d in designs) for w in vocabulary}
    idf = tuple(math.log((1 + len(designs)) / (1 + counts[w])) + 1 for w in vocabulary)
    return Features(vocabulary, idf, terms, tuple(d.endpoint for d in designs))
