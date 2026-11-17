"""Exact current-task coordinate interpretation selected by root source review."""
import json
from pathlib import Path

from source_loader import CURRENT_PROTOCOL_PIN, PINS, SourceError, read_pinned

BINDING_SHA256 = "5a1f4e3ed6c0d04c405f86de8fb3093e57e203f3c2136a6b26892770a9ce520a"


def load_coordinate_binding():
    here = Path(__file__).resolve().parent
    binding = json.loads(read_pinned(here / "coordinate-binding.json", BINDING_SHA256))
    task = here.parent.parent
    read_pinned(task / "task.json", binding["task_sha256"])
    read_pinned(task / "understanding.v1.json", binding["understanding_sha256"])
    if binding["active_protocol_source_sha256"] != CURRENT_PROTOCOL_PIN or binding["source_profile_sha256"] != {
            name: value for name, value in PINS.items() if name.endswith(".json")}:
        raise SourceError("coordinate interpretation differs from selected source profiles")
    return binding
