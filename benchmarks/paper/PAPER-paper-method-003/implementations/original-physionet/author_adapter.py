"""Offline REVE-Base classifier prediction with the pinned author architecture.

The public REVE-Base release is an encoder, not the four-class downstream model.
This adapter requires a complete native downstream state_dict; an encoder alone
or a missing classifier head is rejected. No authenticated historical Table 12
checkpoint has been recovered. Successful prediction is not paper reproduction.

Set REVE_AUTHOR_SOURCE to the external source archive/checkout at SOURCE_COMMIT.
Only load_predictor initializes a model, and only predict performs inference.
Those operations belong under the operator's frozen protocol and native lease.
No source, model, or position-bank downloads are performed by this module.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace

SOURCE_COMMIT = "06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7"
SOURCE_HASHES = {
    "src/models/backbone.py": "632ecd10ddb5efcc6f50a7207b0aa3934e7304438eb3f1db1edfefc3fab3371f",
    "src/models/encoder.py": "933684a3306e16c16926cead0fc8c8c0a9ae99ad9dfaf54dee860c5b335d1b6c",
    "src/models/classifier.py": "cf71d0f455df0e9a263363213d75fbf493ffc5d587cd3c1f80cdc90ab961f90f",
    "src/utils/initialization.py": "f57a373a1a6a8b956bbfe7f5eae2d9d48405f71c37462af91fe55ee1f4101eb8",
    "src/configs/task/physio.yaml": "eec8e80137e125c8bea6a28fd4b26bdd690464ac1d192c20c5aeb94d47a48c14",
    "src/configs/encoder/base.yaml": "ad162dd129c93a466b7e8ada2be1e00e0c1272e95789a9bcb943786680dedb31",
    "hf/reve-positions/positions.json": "f62ca8d7dd4b88e1422ea17348440a41ed0b73b9ff7d12c3b1229492c9b448a5",
}
CHANNELS = tuple((
    "Fc5. Fc3. Fc1. Fcz. Fc2. Fc4. Fc6. C5.. C3.. C1.. Cz.. C2.. C4.. C6.. "
    "Cp5. Cp3. Cp1. Cpz. Cp2. Cp4. Cp6. Fp1. Fpz. Fp2. Af7. Af3. Afz. Af4. Af8. "
    "F7.. F5.. F3.. F1.. Fz.. F2.. F4.. F6.. F8.. Ft7. Ft8. T7.. T8.. T9.. T10. "
    "Tp7. Tp8. P7.. P5.. P3.. P1.. Pz.. P2.. P4.. P6.. P8.. Po7. Po3. Poz. Po4. "
    "Po8. O1.. Oz.. O2.. Iz.."
).split())
ELECTRODES = tuple((
    "FC5 FC3 FC1 FCz FC2 FC4 FC6 C5 C3 C1 CZ C2 C4 C6 CP5 CP3 CP1 CPz CP2 CP4 CP6 "
    "FP1 Fpz FP2 AF7 AF3 AFz AF4 AF8 F7 F5 F3 F1 FZ F2 F4 F6 F8 FT7 FT8 T3 T4 T9 T10 "
    "TP7 TP8 T5 P5 P3 P1 PZ P2 P4 P6 T6 PO7 PO3 POz PO4 PO8 O1 OZ O2 Iz"
).split())
FLAT_DIM = (64 * 4 + 1) * 512
_IMPORT_LOCK = threading.Lock()
_NATIVE_CACHE = {}


def _digest(handle):
    value = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        value.update(chunk)
    return value.hexdigest()


def verify_author_source(source=None):
    """Verify source/geometry without importing NumPy, Torch, or native modules."""
    source = source or os.environ.get("REVE_AUTHOR_SOURCE")
    if not source:
        raise ValueError("REVE_AUTHOR_SOURCE must identify the external pinned author source")
    root = Path(source).expanduser().resolve()
    for relative, expected in SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"author source mismatch at {relative}; require {SOURCE_COMMIT}")
    positions = json.loads((root / "hf/reve-positions/positions.json").read_text())
    if any(name not in positions or len(positions[name]) != 3 or
           not all(math.isfinite(x) for x in positions[name]) for name in ELECTRODES):
        raise ValueError("complete finite author geometry is required")
    return root, positions


def _native_modules(root):
    # Native modules use absolute models.* / utils.* imports. Compile the
    # verified source bytes directly (no stale pyc), resolve those four imports
    # temporarily, and retain unique module identities without changing sys.path.
    with _IMPORT_LOCK:
        key = str(root)
        if key in _NATIVE_CACHE:
            return _NATIVE_CACHE[key]
        aliases = ("models", "utils", "utils.initialization", "models.backbone",
                   "models.encoder", "models.classifier")
        if any(name in sys.modules for name in aliases):
            raise RuntimeError("native REVE import namespace occupied; use an isolated operator process")
        prefix = "_reve_author_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        loaded, unique_names = {}, []
        try:
            for name in ("models", "utils"):
                package = ModuleType(name)
                package.__path__ = []
                sys.modules[name] = package
            for name in aliases[2:]:
                path = root / "src" / (name.replace(".", "/") + ".py")
                unique = prefix + "." + name
                module = ModuleType(unique)
                module.__file__ = str(path)
                module.__package__ = unique.rsplit(".", 1)[0]
                sys.modules[unique] = sys.modules[name] = module
                unique_names.append(unique)
                content = path.read_bytes()
                if hashlib.sha256(content).hexdigest() != SOURCE_HASHES[str(path.relative_to(root))]:
                    raise ValueError("author source changed during import")
                exec(compile(content, str(path), "exec"), module.__dict__)
                loaded[name] = module
            _NATIVE_CACHE[key] = loaded
            return loaded
        except BaseException:
            for name in unique_names:
                sys.modules.pop(name, None)
            raise
        finally:
            for name in aliases:
                sys.modules.pop(name, None)


def load_predictor(checkpoint):
    """Load one explicit bare native classifier state_dict, offline and strictly."""
    root, positions = verify_author_source()
    checkpoint = Path(checkpoint).expanduser().resolve()
    if not checkpoint.is_file():
        raise ValueError("explicit complete downstream checkpoint file is required")
    try:
        import numpy as np
        import torch
        from torch.nn.attention import SDPBackend, sdpa_kernel
        native = _native_modules(root)
    except ImportError as exc:
        raise RuntimeError("native adapter requires the pinned author's Python dependencies, "
                           "including torch>=2.6, numpy, einops, transformers, and packaging") from exc

    with checkpoint.open("rb") as handle:
        checkpoint_sha256 = _digest(handle)
        handle.seek(0)
        state = torch.load(handle, map_location="cpu", weights_only=True)
        handle.seek(0)
        if _digest(handle) != checkpoint_sha256:
            raise ValueError("checkpoint changed while loading")
    if (not isinstance(state, Mapping) or not state or
            any(not isinstance(k, str) or not torch.is_tensor(v) for k, v in state.items())):
        raise ValueError("bare native classifier tensor state_dict required; no wrappers or fallback")
    if "linear_head.3.weight" not in state or tuple(state["linear_head.3.weight"].shape) != (4, FLAT_DIM):
        raise ValueError("complete four-class no-pooling downstream head required; encoder alone rejected")
    args = SimpleNamespace(embed_dim=512, depth=22, heads=8, head_dim=64,
                           mlp_dim_ratio=2.66, use_geglu=True)
    # Meta construction allocates no random fallback weights. Strict assignment
    # must populate every native model parameter before CPU execution is possible.
    with torch.device("meta"):
        encoder = native["models.encoder"].REVE(args, 4, 200, 20, 0.0025)
        model = native["models.classifier"].ReveClassifier(
            encoder, n_classes=4, dropout=0.0, pooling="no", out_shape=FLAT_DIM)
    model.load_state_dict(state, strict=True, assign=True)
    model = model.to(device="cpu", dtype=torch.float32).eval()

    class MathAttention(torch.nn.Module):
        def forward(self, qkv):
            q, k, v = (x.reshape(x.shape[0], x.shape[1], 8, 64).transpose(1, 2)
                       for x in qkv.chunk(3, dim=-1))
            with sdpa_kernel(SDPBackend.MATH):
                result = torch.nn.functional.scaled_dot_product_attention(q, k, v)
            return result.transpose(1, 2).reshape(qkv.shape[0], qkv.shape[1], 512)

    # CPU math backend replaces only the parameter-free attention implementation;
    # the author's qkv/output projections and complete model weights are retained.
    for attention, _feedforward in model.encoder.transformer.layers:
        attention.attend = MathAttention()
        attention.use_flash = False
    geometry = torch.tensor([positions[name] for name in ELECTRODES], dtype=torch.float32)

    class Predictor:
        identity = {
            "model": "REVE-Base native four-class PhysioNet-MI classifier",
            "author_source_commit": SOURCE_COMMIT,
            "author_source_sha256": dict(SOURCE_HASHES),
            "checkpoint_sha256": checkpoint_sha256,
            "geometry_sha256": SOURCE_HASHES["hf/reve-positions/positions.json"],
            "geometry_bank_revision": "befa5b57a455b77cf302daf610c2e9ed8140bace",
            "geometry_bank_sha256": "4b793820b9df0998667deb6c8ce2dbb86b38221d5165c1844bc4971941b13f13",
            "input_scale": "microvolts / 100, then float32; no additional normalization",
            "electrode_names": list(ELECTRODES),
            "device": "cpu", "dtype": "float32", "attention_backend": "pytorch_sdpa_math",
            "backend_deviation": "CPU fp32 math replaces author automatic CUDA/flash backend",
            "pooling": "no: query context prepended before flatten", "flat_dim": FLAT_DIM,
            "torch_version": torch.__version__, "numpy_version": np.__version__,
            "historical_Table12_checkpoint_authenticated": False,
        }

        def predict(self, signals_uV, channel_names):
            if tuple(channel_names) != CHANNELS:
                raise ValueError("exact source channel order/names required; no implicit remapping")
            data = np.asarray(signals_uV)
            if data.ndim != 3 or data.shape[1:] != (64, 800) or data.shape[0] < 1:
                raise ValueError("nonempty batch of N x 64 x 800 source epochs required")
            if data.dtype != np.dtype("float64") or not np.isfinite(data).all():
                raise ValueError("finite float64 microvolt inputs from the source preparer required")
            # Match native LMDBDataset: divide in the source dtype before casting.
            tensor = torch.from_numpy(np.ascontiguousarray(data / 100.0)).float()
            pos = geometry.unsqueeze(0).repeat(data.shape[0], 1, 1)
            with torch.inference_mode():
                logits = model(tensor, pos).cpu().numpy()
            if logits.shape != (data.shape[0], 4) or not np.isfinite(logits).all():
                raise ValueError("native classifier returned invalid logits")
            return logits

    return Predictor()
