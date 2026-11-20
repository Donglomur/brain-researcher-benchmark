"""Exact observed image-to-container label omission policy.

The caller must authenticate and retain the full selected image label map and
explicitly select its effective base map. This helper only validates their
relationship. It does not authorize an image, infer a new profile, or handle
per-container ownership labels. Derived images require their own selected maps.
"""

POLICY_ID = "smc-image-effective-labels-v1"
OMITTED_DESKTOP_KEYS = frozenset((
    "desktop.docker.io/mounts/0/Source",
    "desktop.docker.io/mounts/0/SourceKind",
    "desktop.docker.io/mounts/0/Target",
    "desktop.docker.io/mounts/1/Source",
    "desktop.docker.io/mounts/1/SourceKind",
    "desktop.docker.io/mounts/1/Target",
    "desktop.docker.io/ports.scheme",
))


def validate_label_maps(image_labels, effective_base_labels):
    """Return a fresh effective map; reject every unselected omission or change.

    Both inputs must be exact dicts whose keys and values are exact strings.
    Neither map is mutated. Full image labels remain the caller's distinct
    authenticated input; arbitrary retained keys are accepted only when they
    are explicitly present with the same value in both selected maps.
    """
    for name, labels in (("image_labels", image_labels),
                         ("effective_base_labels", effective_base_labels)):
        if type(labels) is not dict:
            raise ValueError(name + " must be an exact dict")
        if any(type(key) is not str or type(value) is not str
               for key, value in labels.items()):
            raise ValueError(name + " requires exact string keys and values")
    image_keys = set(image_labels)
    base_keys = set(effective_base_labels)
    if base_keys - image_keys:
        raise ValueError("effective base contains labels absent from image")
    if image_keys - base_keys != OMITTED_DESKTOP_KEYS:
        raise ValueError("image must omit exactly the seven selected Desktop keys")
    if any(image_labels[key] != value
           for key, value in effective_base_labels.items()):
        raise ValueError("retained label values differ from the selected image")
    return dict(effective_base_labels)
