"""Source-anchored core estimator; runnable source, NOT executed or validated here.

Calls unchanged pinned author helpers. It omits simulations, shuffles and
supplementary sweeps deliberately; it is not a full historical figure driver.
This is a reference solution for supplied-code access, not an independent arm.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "public"))
sys.path.insert(0, str(ROOT / "public/author_code"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import protocol
from panels import load_panels, geometry
from provision import inspect_file, decoded_fields


def analyze(session, f2, f3, x, y, device):
    import numpy as np
    import torch
    import powerlaw
    import lyapun
    # Fig2: population std (ddof=0), no epsilon; deterministic neuron permutation.
    f2 -= f2.mean(axis=1, keepdims=True)
    sd = f2.std(axis=1, keepdims=True)
    protocol.need(np.all(sd > 0), "No source-undefined zero-variance neuron repair")
    f2 /= sd
    np.random.seed(0)
    order = np.random.permutation(len(f2))
    z = torch.from_numpy(f2[order].copy()).to(device)
    spacing = 40 if session["modality"] == "ephys" else 25
    ex, ey = x[order], y[order]
    covariance = torch.linalg.eigh(z @ z.T / z.shape[1])[0].cpu().numpy()[::-1]
    svca2 = powerlaw.SVCA2(z, xpos=ex, ypos=ey, spacing=spacing)
    svca, var = powerlaw.SVCA(z, xpos=ex, ypos=ey, spacing=spacing)
    del z
    # Fig3 independently uses the full uncropped source and its epsilon zscore.
    d = lyapun.zscore(f3, axis=-1)
    eig = lyapun.dmd(d, lam=.1 if session["modality"] == "ephys" else .01,
                      delta=5, device=device)[1]
    acg = lyapun.pc_timescales(d, x, y, sig=2 if session["modality"] == "ephys" else 0, device=device)
    return {"session_id": session["session_id"], "covariance": covariance[:500].tolist(),
            "svca2": svca2[:500].tolist(), "svca": svca[:500].tolist(), "svca_variance": var[:500].tolist(),
            "pc_acg": acg[:session["pc_rows"], :100].tolist(),
            "dmd": [[float(e.real), float(e.imag)] for e in eig]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-root", required=True)
    p.add_argument("--design", required=True)
    p.add_argument("--expanded-ceiling-bytes", type=int, required=True)
    p.add_argument("--array-ceiling-bytes", type=int, required=True)
    p.add_argument("--device", choices=("cpu", "cuda"), required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    from package_io import read
    design_raw = read(a.design, 131072)
    design = protocol.validate_design(protocol.decode(design_raw))
    inventory = json.loads((ROOT / "public/ASSETS.json").read_text())["assets"]
    import torch
    device = torch.device(a.device)
    records = []
    for session, expected, asset in zip(protocol.cohort(), design["records"], inventory):
        c = inspect_file(Path(a.data_root) / asset["filename"], asset, a.expanded_ceiling_bytes, decoded_fields(session["modality"]))
        protocol.need(c["sha256"] == expected["input_sha256"], "Actual design raw identity")
        protocol.need(c["expanded_bytes"] <= a.array_ceiling_bytes, "Selected decode extent")
        f2, f3, x, y = load_panels(a.data_root, session, a.array_ceiling_bytes)
        protocol.need(geometry(session, c["sha256"], f2, f3, x, y) == expected, "Exact prepared geometry")
        records.append(analyze(session, f2, f3, x, y, device))
        del f2, f3, x, y
    value = {"schema": "critical_init_result_v1", "design_sha256": protocol.design_pin(design_raw), "records": records}
    protocol.validate_result(value, design, protocol.design_pin(design_raw))
    raw = (json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n").encode()
    protocol.need(len(raw) <= protocol.MAX_BYTES, "Bounded complete output")
    with open(a.output, "xb") as f:
        f.write(raw)


if __name__ == "__main__":
    main()
