"""Software version/linkage checks only; no model or empirical input."""
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import concurrent.futures

expected = json.loads(Path("/tmp/python_expected_versions.json").read_text())
assert {k: metadata.version(k) for k in expected} == expected
prefix = Path("/opt/thalamus/R-4.3.1")
environment = dict(os.environ); environment["LD_LIBRARY_PATH"] = str(prefix / "lib/R/lib")
def linked(path):
    result = subprocess.run(["ldd", str(path)], capture_output=True, text=True, env=environment, timeout=10)
    if result.returncode or "not found" in result.stdout:
        raise ValueError("Unresolved runtime software linkage: " + str(path))
    return str(path)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    checked = list(pool.map(linked, prefix.rglob("*.so")))
# packageVersion reads installed distribution metadata; no namespace or model
# helper is loaded, and no empirical files are present in this build context.
expression = """stopifnot(as.character(getRversion())=='4.3.1');
expected<-c(caret='6.0.94',xgboost='1.7.5.1',pROC='1.18.0',jsonlite='1.8.4',digest='0.6.31');
actual<-vapply(names(expected),function(x)as.character(utils::packageVersion(x)),character(1));
stopifnot(identical(actual,expected));cat('R4.3.1 package metadata verified\\n')"""
result = subprocess.run([str(prefix / "bin/Rscript"), "--vanilla", "-e", expression], capture_output=True, text=True, timeout=15)
assert result.returncode == 0, result.stderr
print(json.dumps({"status": "dependency_metadata_and_linkage_verified", "shared_objects_checked": len(checked),
                  "python_distributions_checked": len(expected), "R_metadata": result.stdout.strip(),
                  "model_fits": 0, "scoring_calls": 0, "empirical_inputs": 0}))
