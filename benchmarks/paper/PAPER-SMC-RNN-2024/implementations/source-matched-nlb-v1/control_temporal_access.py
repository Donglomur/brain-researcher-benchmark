"""Generated-only dependency control for the pinned SMC proposal encoders.

No authentic arrays, checkpoint parameters, targets, model fitting, or scorer runs.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import resource
import time
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def propagate(inputs, kernel, location, mode):
    pad = kernel - 1
    if location == "causal":
        assert mode == "reflect" and pad < len(inputs)
        padded = [inputs[i] for i in range(pad, 0, -1)] + inputs
    else:
        assert location == "acausal" and mode == "constant"
        padded = inputs + [frozenset() for _ in range(pad)]
    return [frozenset().union(*padded[t:t + kernel]) for t in range(len(inputs))]


def cumulative(supports):
    result, previous = [], frozenset()
    for support in supports:
        previous = previous | support
        result.append(previous)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    cpu_start, wall_start = time.process_time(), time.monotonic()
    import torch
    import numpy as np
    import yaml

    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.manual_seed(20261116)
    names = ["vi_rnn/encoders.py", "vi_rnn/vae.py", "evaluation/eval_nlb.py",
             "models/reach_nlb_filtering_proposal_36d/config.yaml",
             "models/reach_nlb_smoothing_proposal_36d/config.yaml"]
    manifest = json.loads(args.manifest.read_text())
    pinned = {row["path"]: row["sha256"] for row in manifest["files"]}
    hashes = {name: digest(args.source / name) for name in names}
    assert all(hashes[name] == pinned[name] for name in names)
    spec = importlib.util.spec_from_file_location("_pinned_smc_encoder", args.source / names[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    arms = {}
    for arm, directory in (("causal", "filtering"), ("noncausal", "smoothing")):
        config = yaml.safe_load((args.source / f"models/reach_nlb_{directory}_proposal_36d/config.yaml").read_text())
        params = config["vae_params"]["enc_params"]
        assert params["init_kernel_sizes"] == [14, 4, 2]
        assert params["n_channels"] == [128, 64]
        assert params["nonlinearity"] == "gelu" and params["constant_var"] is False
        with contextlib.redirect_stdout(io.StringIO()):
            encoder = module.CNN_encoder(137, 36, params).double().eval()
        # Positive generated parameters/inputs make every structural path visible
        # to exact-source mean/logvariance gradients; this is not model fitting.
        with torch.no_grad():
            for layer in encoder.modules():
                if isinstance(layer, torch.nn.Conv1d):
                    layer.weight.fill_(1.0 / (layer.in_channels * layer.kernel_size[0]))
                    layer.bias.zero_()
                    assert layer.stride == (1,) and layer.dilation == (1,)
            generated = torch.full((1, 137, 35), 0.5, dtype=torch.float64)
        generated.requires_grad_(True)
        _, means, logvars, _ = encoder(generated, k=1)
        layers, support = [], [frozenset([t]) for t in range(35)]
        for kernel in params["init_kernel_sizes"]:
            support = propagate(support, kernel, params["padding_location"], params["padding_mode"])
            layers.append([sorted(item) for item in support])
        measured = {}
        for name, outputs in (("mean", means), ("logvar", logvars)):
            measured[name] = []
            for t in range(35):
                gradient = torch.autograd.grad(outputs[0, :, t, 0].sum(), generated, retain_graph=True)[0]
                indices = set(torch.nonzero(gradient.abs().sum(dim=(0, 1)) > 0).flatten().tolist())
                assert indices == set(support[t]), (arm, name, t, indices, support[t])
                measured[name].append(sorted(indices))
        filtered = cumulative(support)
        expected = [frozenset(range((max(t, 13) if arm == "causal" else min(t + 17, 34)) + 1))
                    for t in range(35)]
        assert filtered == expected
        # A separate closed-form path expansion checks the structural iterator.
        if arm == "causal":
            direct = [frozenset(abs(abs(abs(t - a) - b) - c)
                                for a in range(2) for b in range(4) for c in range(14))
                      for t in range(35)]
        else:
            direct = [frozenset(range(t, min(t + 17, 34) + 1)) for t in range(35)]
        assert direct == support
        arms[arm] = {
            "kernels": params["init_kernel_sizes"], "channels": params["n_channels"],
            "padding_location": params["padding_location"], "padding_mode": params["padding_mode"],
            "nonlinearity": params["nonlinearity"], "indexing": "zero-based, 35 observed bins",
            "layer_supports": layers, "encoder_mean_support": measured["mean"],
            "encoder_logvar_support": measured["logvar"],
            "filtered_prefix_union": [sorted(item) for item in filtered],
            "filtered_latest_observed_bin": [max(item) for item in filtered],
            "expected_envelope": "0..max(t,13) inclusive" if arm == "causal" else "0..min(t+17,34) inclusive",
            "gradient_structural_match": True, "independent_closed_form_match": True,
            "forward_bins_35_to_44_permitted_observation_support": list(range(35)),
        }
    report = {
        "schema": "smc_generated_temporal_dependency_control_v1", "passed": True,
        "source_commit": manifest["source_commit"], "source_sha256": hashes,
        "control_script_sha256": digest(__file__), "arms": arms,
        "method": "Exact pinned CNN_encoder mean/logvariance gradients with generated positive float64 parameters and inputs; independently propagated set-valued pad/conv supports and closed-form supports; prefix unions model source filtering recurrence.",
        "scope": "Structural dependency proof, not checkpoint sensitivity, numerical reproduction, or enforcement of an arbitrary candidate. No model training or authentic array/checkpoint/target access.",
        "filtering_source_basis": {
            "vae.py": "855-857 encoder; 898-901 initial proposal; 918 and 976 current likelihood; 929-939 saved filtered state before next update; 1026-1029 final state; 1031-1084 separate smoothing tensor; 1087-1102 forward transition and separate filtered readout",
            "eval_nlb.py": "59 selects filtered return for smooth=False; 115-121 particle/repeat means preserve support",
            "resampling": "vae.py1150 gather returns a new tensor; 1171-1173 fixed-shape random draw. Backward smoothing does not overwrite filtered states."
        },
        "training_distinction": "Source train input has45bins and182likelihood neurons; noncausal proposal training support reachesmin(t+17,44). These test35bin contracts do not restrict permitted training/validation fitting.",
        "candidate_enforcement": "Unqualified: a full-input HDF5 submission interface does not enforce temporal invariance; prospective reviewed execution boundary required for causal/joint admission.",
        "versions": {"torch": torch.__version__, "numpy": np.__version__},
        "cpu_seconds": time.process_time() - cpu_start,
        "wall_seconds": time.monotonic() - wall_start,
        "maxrss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({key: report[key] for key in ("passed", "cpu_seconds", "wall_seconds", "maxrss_native_units")}), flush=True)


if __name__ == "__main__":
    main()
