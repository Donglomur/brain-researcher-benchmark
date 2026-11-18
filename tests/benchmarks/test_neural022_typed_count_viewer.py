"""Enroll the task-local stdlib viewer controls in public-catalog CI discovery."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'benchmarks/neural/NEURAL-022/implementations/typed-count-viewer-v1/test_viewer.py'
SPEC = importlib.util.spec_from_file_location('neural022_typed_count_viewer_controls', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ViewerControls = MODULE.ViewerControls
