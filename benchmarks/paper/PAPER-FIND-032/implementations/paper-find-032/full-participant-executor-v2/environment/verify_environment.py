"""Future image compatibility checks, without neural data or scientific fits.

This file is supplied as source. It has not been imported or run for authoring.
Passing it would establish these checks only, not numerical or native admission.
"""
import argparse
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    raw = args.lock.read_bytes()
    require(len(raw) <= 1048576, "Bounded environment lock")
    lock = json.loads(raw)
    require(lock["schema"] == "find032_environment_inputs_v1", "Lock schema")
    require(platform.system() == "Linux" and platform.machine() == "x86_64",
            "Selected Linux amd64 environment")
    require(platform.python_implementation() == "CPython" and
            platform.python_version() == lock["python"], "Exact selected interpreter")
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.markers import default_environment
    from packaging.utils import canonicalize_name
    expected = {canonicalize_name(row["name"]): row["version"]
                for row in lock["python_artifacts"]}
    distribution_rows = [(canonicalize_name(dist.metadata["Name"]), dist.version)
                         for dist in importlib.metadata.distributions()]
    require(len(distribution_rows) == len({name for name, _ in distribution_rows}),
            "Unique canonical Python distribution metadata")
    actual = dict(distribution_rows)
    require(actual == expected, "Exact Python distribution closure")
    marker_environment = default_environment()
    marker_environment["extra"] = ""
    checked_edges = []
    for name, version in sorted(expected.items()):
        dist = importlib.metadata.distribution(name)
        python_spec = dist.metadata.get("Requires-Python", "")
        require(not python_spec or platform.python_version() in SpecifierSet(python_spec),
                "Installed interpreter requirement for " + name)
        for text in dist.requires or ():
            requirement = Requirement(text)
            if requirement.marker and not requirement.marker.evaluate(marker_environment):
                continue
            dependency = canonicalize_name(requirement.name)
            require(dependency in expected and
                    expected[dependency] in requirement.specifier,
                    "Installed dependency closure: " + name + " -> " + text)
            require(not requirement.extras, "Unexpected active optional dependency")
            checked_edges.append({"package": name, "requirement": text})
    for module in ("numpy", "scipy", "sklearn", "mne", "matplotlib",
                   "rpy2.robjects"):
        importlib.import_module(module)
    from rpy2 import robjects
    from rpy2.robjects.packages import importr
    r_version = str(robjects.r["as.character"](robjects.r["getRversion"]())[0])
    require(r_version == lock["r"]["version"], "Exact R version")
    bayesfactor = importr("BayesFactor")
    bf_version = str(robjects.r["as.character"](
        robjects.r["packageVersion"]("BayesFactor"))[0])
    require(bf_version.replace("-", ".") ==
            lock["r"]["bayesfactor"]["version"].replace("-", "."),
            "Exact BayesFactor version, using R numeric-version normalization")
    require(callable(bayesfactor.ttestBF) and callable(bayesfactor.extractBF),
            "Required BayesFactor API exports")
    r_packages = {}
    for package, minimum in lock["r"]["required_packages"].items():
        version = robjects.r["packageVersion"](package)
        rendered = str(robjects.r["as.character"](version)[0])
        if minimum is not None:
            require(int(robjects.r["compareVersion"](rendered, minimum)[0]) >= 0,
                    "R dependency minimum: " + package)
        r_packages[package] = rendered
    all_r = list(map(str, robjects.r(
        "local({ p <- installed.packages(); paste(p[, 'Package'], p[, 'Version'], sep='=') })")))
    print(json.dumps({"schema": "find032_environment_import_check_v1",
                      "python": platform.python_version(), "python_packages": actual,
                      "checked_active_edges": checked_edges, "R": r_version,
                      "BayesFactor": bf_version, "required_R_packages": r_packages,
                      "installed_R_manifest": sorted(all_r),
                      "scientific_fits": 0, "neural_data_read": False,
                      "scientific_qualification": False, "native_qualification": False},
                     sort_keys=True))


if __name__ == "__main__":
    main()
