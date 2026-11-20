"""Independent scalar oracle for the generated streamed full-fit source control.

This file is source-authored only. It imports no production implementation and
does not establish numerical equivalence to the neuronal model or source Optax.
The generated control uses 21 scalar parameter coordinates, 147 output sites,
positive-residual masked L1, and momentum 0.6 at learning rate 0.02. Its optimizer
is an analytical test operand, not a claim about the frozen source optimizer.

Normalization is the frozen five-group algebra: divide by the group's L2 norm
raised to 0.99, THEN MULTIPLY by the group's coordinate count (2,3,4,6,6).
All fixture labels/masks are generated; no original data or reference arrays are
read. The reference batch loss is a masked SITE SUM divided by ACTUAL batch size.
"""

from math import fsum, isfinite, sqrt

NUM_SITES = 147
NUM_COORDINATES = 21
PARAMETER_LENGTHS = (2, 3, 4)
MOMENTUM = 0.6
LEARNING_RATE = 0.02
NORMALIZATION_EXPONENT = 0.99
PRODUCTION_EPOCHS = 21
PRODUCTION_BATCH_SIZES = (256,) * 47 + (153,)
PRODUCTION_UPDATES = 1008
VALIDATION_CHUNK_SIZES = (1024, 1024, 999)
FINAL_FEATURE_ROWS = 128


def _finite(value, name):
    result = float(value)
    if not isfinite(result):
        raise ValueError(name + " must be finite")
    return result


def _index(value, limit, name):
    if type(value) is not int or not 0 <= value < limit:
        raise ValueError(name + " is outside the generated coordinate range")
    return value


def coefficient(site, coordinate):
    """Distinct positive coefficient for each coordinate at any fixed site.

    149 is prime; sites use factors 1..147 and coordinates 1..21. Therefore
    multiplication modulo 149 cannot identify two coordinates at a fixed site.
    """
    _index(site, NUM_SITES, "site")
    _index(coordinate, NUM_COORDINATES, "coordinate")
    return (1 + ((site + 1) * (coordinate + 1) % 149)) / 149.0


_COEFFICIENTS = tuple(
    tuple(coefficient(site, coordinate) for coordinate in range(NUM_COORDINATES))
    for site in range(NUM_SITES)
)


def coordinates_to_tree(coordinates):
    """Return (three parameter entries, six basal entries, six somatic entries)."""
    coordinates = tuple(_finite(value, "coordinate") for value in coordinates)
    if len(coordinates) != NUM_COORDINATES:
        raise ValueError("exactly 21 scalar coordinates are required")
    parameters = []
    position = 0
    for width in PARAMETER_LENGTHS:
        parameters.append({"w": list(coordinates[position:position + width])})
        position += width
    basal = [{"w": coordinates[position + index]} for index in range(6)]
    position += 6
    somatic = [{"w": coordinates[position + index]} for index in range(6)]
    return parameters, basal, somatic


def tree_to_coordinates(tree):
    """Canonical order: parameter lengths 2,3,4, then basal 6, then somatic 6."""
    if len(tree) != 3:
        raise ValueError("three optimizer groups are required")
    parameters, basal, somatic = tree
    if len(parameters) != 3 or len(basal) != 6 or len(somatic) != 6:
        raise ValueError("generated tree group lengths must be 3,6,6")
    coordinates = []
    for entry, width in zip(parameters, PARAMETER_LENGTHS):
        if set(entry) != {"w"} or len(entry["w"]) != width:
            raise ValueError("parameter w arrays must have lengths 2,3,4")
        coordinates.extend(_finite(value, "parameter") for value in entry["w"])
    for group in (basal, somatic):
        for entry in group:
            if set(entry) != {"w"}:
                raise ValueError("scalar compartment entry must contain only w")
            coordinates.append(_finite(entry["w"], "compartment parameter"))
    return tuple(coordinates)


def initial_parameters():
    """Fresh positive parameter tree; no arrays or mutable state are shared."""
    return coordinates_to_tree(5.0 + (index + 1) / 32.0
                               for index in range(NUM_COORDINATES))


def zero_state():
    """Fresh state tree for the three generated momentum optimizer groups."""
    return coordinates_to_tree(0.0 for _ in range(NUM_COORDINATES))


def batch_operands(rows, *, start=0):
    """Generate features, negative labels, and heterogeneous binary site masks.

    Feature is the scalar carried by the agreed input current column. The parent
    backend owns expansion into the 287-column source current-array interface.
    start indexes the global generated row; singleton and batch operands can
    therefore use identical rows without any original training data.
    """
    if type(rows) is not int or rows < 1 or type(start) is not int or start < 0:
        raise ValueError("rows must be positive and start must be nonnegative")
    features, labels, masks = [], [], []
    for row in range(start, start + rows):
        features.append((1 + row % 17) / 8.0)
        labels.append([
            -1000.0 - (row % 13) / 16.0 - (site % 7) / 32.0
            for site in range(NUM_SITES)
        ])
        masks.append([
            int((3 * row + 5 * site) % 11 not in (0, 1, 2))
            for site in range(NUM_SITES)
        ])
    return features, labels, masks


def _site_amplitudes(parameters):
    coordinates = tree_to_coordinates(parameters)
    return tuple(
        fsum(value * weight for value, weight in zip(coordinates, site_weights))
        for site_weights in _COEFFICIENTS
    )


def predict_features(parameters, features):
    """Feature-only prediction oracle; accepts and accesses no labels or masks."""
    amplitudes = _site_amplitudes(parameters)
    features = tuple(_finite(value, "feature") for value in features)
    return [[feature * amplitude for amplitude in amplitudes]
            for feature in features]


def batch_reference(parameters, features, labels, masks):
    """Analytical masked L1 mean and gradient, independent of source reductions.

    Define A_s = sum_j theta_j*a_sj, X_s = sum_i m_is*x_i,
    Y_s = sum_i m_is*y_is. When every supported residual is positive:

        loss = sum_s (A_s*X_s - Y_s) / B
        gradient_j = sum_s a_sj*X_s / B

    These are site sufficient statistics, not a source singleton-call replay.
    B is len(features), including 153 for the production tail. There is no
    division by 147, the mask count, or a nominal full-batch size.
    """
    features = tuple(_finite(value, "feature") for value in features)
    labels = tuple(tuple(_finite(value, "label") for value in row)
                   for row in labels)
    masks = tuple(tuple(_finite(value, "mask") for value in row)
                  for row in masks)
    rows = len(features)
    if rows < 1 or len(labels) != rows or len(masks) != rows:
        raise ValueError("feature, label, and mask row counts must agree")
    if any(len(row) != NUM_SITES for row in labels + masks):
        raise ValueError("all rows must contain exactly 147 sites")
    if any(value not in (0.0, 1.0) for row in masks for value in row):
        raise ValueError("this generated oracle requires binary site masks")

    amplitudes = _site_amplitudes(parameters)
    for row in range(rows):
        for site in range(NUM_SITES):
            if masks[row][site]:
                residual = features[row] * amplitudes[site] - labels[row][site]
                if not isfinite(residual) or residual <= 0.0:
                    raise ValueError("positive-residual analytical branch violated")

    feature_sums = tuple(
        fsum(masks[row][site] * features[row] for row in range(rows))
        for site in range(NUM_SITES)
    )
    label_sums = tuple(
        fsum(masks[row][site] * labels[row][site] for row in range(rows))
        for site in range(NUM_SITES)
    )
    loss = fsum(amplitudes[site] * feature_sums[site] - label_sums[site]
                for site in range(NUM_SITES)) / rows
    gradient_coordinates = tuple(
        fsum(_COEFFICIENTS[site][coordinate] * feature_sums[site]
             for site in range(NUM_SITES)) / rows
        for coordinate in range(NUM_COORDINATES)
    )
    return loss, coordinates_to_tree(gradient_coordinates)


def normalize_gradients(gradients):
    """Apply the independently specified five-group normalization algebra."""
    coordinates = tree_to_coordinates(gradients)
    normalized = []
    # Three separate parameter groups, one whole basal, one whole somatic.
    for begin, end, multiplier in ((0, 2, 2), (2, 5, 3), (5, 9, 4),
                                   (9, 15, 6), (15, 21, 6)):
        group = coordinates[begin:end]
        norm = sqrt(fsum(value * value for value in group))
        if not isfinite(norm) or norm <= 0.0:
            raise ValueError("generated normalization requires nonzero finite norm")
        denominator = norm ** NORMALIZATION_EXPONENT
        normalized.extend(value / denominator * multiplier for value in group)
    return coordinates_to_tree(normalized)


def momentum_transition(parameters, optimizer_states, gradients):
    """One GENERATED momentum control step, never source Optax equivalence.

    n = five_group_normalization(g)
    v_next = 0.6*v + n
    update = -0.02*v_next
    theta_next = theta + update

    The state carries across updates. Every result is a fresh independent tree.
    This helper neither calls source_transition nor supplies replacement source
    reduction, normalization, scheduling, or optimizer implementations.
    """
    old_parameters = tree_to_coordinates(parameters)
    old_states = tree_to_coordinates(optimizer_states)
    normalized_tree = normalize_gradients(gradients)
    normalized = tree_to_coordinates(normalized_tree)
    next_states = tuple(MOMENTUM * old + grad
                        for old, grad in zip(old_states, normalized))
    updates = tuple(-LEARNING_RATE * state for state in next_states)
    next_parameters = tuple(old + update
                            for old, update in zip(old_parameters, updates))
    return {
        "normalized": normalized_tree,
        "proposed_updates": coordinates_to_tree(updates),
        "parameters": coordinates_to_tree(next_parameters),
        "optimizer_states": coordinates_to_tree(next_states),
        "updates": 1,
    }
