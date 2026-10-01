"""Fail closed when an explicitly supplied EEGLAB cache is incomplete."""
from pathlib import Path


def require_pairs(directory, subjects):
    directory = Path(directory)
    paths = []
    for subject in subjects:
        for extension in ("set", "fdt"):
            path = directory / f"sub-{subject:03d}_task-N2pc_eeg.{extension}"
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(f"missing or empty paired EEGLAB file: {path}")
            paths.append(path)
    return paths
