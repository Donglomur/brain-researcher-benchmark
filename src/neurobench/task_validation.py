#!/usr/bin/env python3
"""Read-only, offline checks for single-step neuroscience Harbor task drafts.

This is not Harbor, a sandbox audit, a scientific review, or a certification.
No task code, Docker build, download, or model is executed. See TERMINAL_BENCH_STANDARD.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shlex
import sys
import tomllib
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

TBS_REVISION = "05694954781735e8c36f656fae7f90b9392e700a"
HARBOR_REVISION = "1f49616c8bba4e91264df2d7882c4f2c0d43d99a"
SUFFIX = ("\n\nYou have 28800 seconds to complete this task. "
          "Do not cheat by using online solutions or hints specific to this task.\n")
ROOT_FIELDS = {"schema_version", "task", "metadata", "verifier", "agent", "environment",
               "solution", "source", "multi_step_reward_strategy", "steps", "artifacts"}
NETWORK_FIELDS = {"network_mode", "allowed_hosts"}
ENV_FIELDS = NETWORK_FIELDS | {"build_timeout_sec", "docker_image", "os", "cpus", "memory_mb",
    "storage_mb", "gpus", "gpu_types", "tpu", "mcp_servers", "env", "skills_dir", "healthcheck",
    "workdir", "allow_internet", "backend", "validate_env"}
META_REQUIRED = {"author_name", "author_email", "author_organization", "author_profile", "domain",
    "field", "subfield", "tags", "expert_time_estimate_hours", "relevant_experience", "conflicts_of_interest"}
HUMAN_METADATA = {"author_name", "author_email", "author_organization", "author_profile", "relevant_experience", "conflicts_of_interest"}
ROLES = {"public_input", "verifier_reference", "source_code", "model_checkpoint"}
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_TEXT = 4 * 1024 * 1024
MAX_INLINE_HASH = 64 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric(value: Any, *, positive: bool = True) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def nonempty(value: Any) -> bool:
    return (isinstance(value, str) and bool(value.strip())) or (
        isinstance(value, list) and bool(value) and all(nonempty(v) for v in value))


def string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: Any, *, required: bool = False) -> bool:
    return isinstance(value, list) and (bool(value) or not required) and all(string(v) for v in value)


def string_map(value: Any) -> bool:
    return isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())


def timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def inside(root: Path, relative: Any) -> Path | None:
    """Reject traversal and symlink components, including symlinks staying inside root."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        return None
    p = PurePosixPath(relative)
    if p.is_absolute() or any(v in ("..", ".") for v in relative.split("/")):
        return None
    current = root
    for part in p.parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        current.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return current


def artifact_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("/") or "\\" in value:
        return False
    p = PurePosixPath(value)
    if str(p) != value or any(x in ("..", ".") for x in value.split("/")[1:]):
        return False
    # Protect the verifier and avoid whole-filesystem transfer. This is our stricter local rule.
    if len(p.parts) < 3 or p.parts[1] in {"tests", "solution", "logs", "proc", "sys", "dev", "etc", "usr", "bin", "sbin", "lib", "lib64"}:
        return False
    return not any(c in value for c in "*?[]$`\n\r\x00")


def docker_lines(text: str) -> list[tuple[str, str]]:
    text = re.sub(r"\\\s*\n", " ", text)
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"([A-Za-z]+)\s+(.*)", line)
        if match:
            result.append((match[1].upper(), match[2]))
    return result


def copy_tokens(value: str) -> list[str]:
    value = re.sub(r"^(?:--\S+\s+)+", "", value).strip()
    try:
        if value.startswith("["):
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed) else []
        return shlex.split(value)
    except (ValueError, json.JSONDecodeError):
        return []


class Audit:
    def __init__(self, task: Path, evidence_dir: Path | None = None, profile: str = "science"):
        self.task = task.resolve()
        self.evidence_dir = (evidence_dir or self.task / "authoring").resolve()
        self.profile = profile
        self.publication_metadata_complete = True
        self.issues: list[dict[str, str]] = []
        self.inputs: list[dict[str, Any]] = []

    def issue(self, code: str, message: str, severity: str = "error") -> None:
        self.issues.append({"severity": severity, "code": code, "message": message})

    def publication_missing(self, code: str, message: str) -> None:
        self.publication_metadata_complete = False
        self.issues.append({"severity": "warning" if self.profile == "local-draft" else "error", "code": code,
                            "message": message, "gate": "publication_metadata"})

    def text(self, path: Path, *, required: bool = True) -> str:
        if path.is_symlink():
            self.issue("symlink", f"Refuse symlink: {path}")
            return ""
        try:
            if path.stat().st_size > MAX_TEXT:
                self.issue("text_too_large", f"Text inspection limit exceeded: {path}")
                return ""
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            if required:
                self.issue("unreadable_file", f"Cannot read {path}: {exc}")
            return ""

    def json(self, path: Path) -> dict[str, Any]:
        text = self.text(path)
        if not text:
            return {}
        try:
            data = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
            if not isinstance(data, dict):
                raise ValueError("expected object")
            return data
        except (ValueError, json.JSONDecodeError) as exc:
            self.issue("invalid_json", f"Invalid {path}: {exc}")
            return {}

    def table(self, data: dict, key: str, allowed: set[str] | None = None) -> dict:
        value = data.get(key)
        if not isinstance(value, dict):
            self.issue("table_type", f"{key} must be a TOML table")
            return {}
        if allowed is not None:
            for extra in sorted(set(value) - allowed):
                self.issue("unknown_field", f"Unrecognized {key}.{extra}; Harbor may silently ignore it")
        return value

    def config(self) -> tuple[dict, list[str]]:
        try:
            cfg = tomllib.loads(self.text(self.task / "task.toml"))
        except tomllib.TOMLDecodeError as exc:
            self.issue("invalid_toml", str(exc))
            return {}, []
        for extra in sorted(set(cfg) - ROOT_FIELDS):
            self.issue("unknown_field", f"Unrecognized root field {extra}")
        if not nonempty(cfg.get("schema_version")) or not isinstance(cfg.get("schema_version"), str):
            self.issue("schema_version", "schema_version must be a nonempty string; no fixed Harbor version is assumed")
        if cfg.get("steps"):
            self.issue("unsupported_multistep", "This local validator supports single-step tasks only")
        if "steps" in cfg and not isinstance(cfg["steps"], list):
            self.issue("field_type", "steps must be an array; this profile supports only an empty array")
        if "multi_step_reward_strategy" in cfg:
            self.issue("unsupported_multistep", "multi_step_reward_strategy is outside this single-step profile")
        if "source" in cfg and not string(cfg["source"]):
            self.issue("field_type", "source must be a string")
        task = self.table(cfg, "task", {"name", "version", "description", "authors", "keywords"})
        if task.get("name") != "terminal-bench-science/" + self.task.name:
            self.issue("task_name", "task.name must be terminal-bench-science/<task-folder-name>")
        if not string(task.get("description")):
            self.issue("task_description", "Nonempty task.description required")
        if "version" in task and not string(task["version"]):
            self.issue("field_type", "task.version must be a string")
        authors = task.get("authors")
        if "authors" not in task or authors == []:
            self.publication_missing("authors", "Nonempty task.authors required for publication; do not invent human identity")
        elif not isinstance(authors, list):
            self.publication_metadata_complete = False
            self.issue("authors", "Present task.authors must be a nonempty array of author objects")
        else:
            for author in authors:
                if not isinstance(author, dict) or set(author) - {"name", "email"} or not all(string(author.get(k)) for k in ("name", "email")):
                    self.publication_metadata_complete = False
                    self.issue("authors", "Each author requires name/email only; human authorship is not certified")
        if not string_list(task.get("keywords"), required=True):
            self.issue("keywords", "Nonempty task.keywords string array required")
        meta = self.table(cfg, "metadata")
        for key in META_REQUIRED - {"expert_time_estimate_hours"}:
            if not (string_list(meta.get(key), required=True) if key == "tags" else string(meta.get(key))):
                if key in HUMAN_METADATA:
                    self.publication_metadata_complete = False
                missing = key not in meta or (isinstance(meta[key], str) and not meta[key].strip())
                if key in HUMAN_METADATA and missing:
                    self.publication_missing("metadata", f"Nonempty metadata.{key} required for the Science submission profile")
                else:
                    self.issue("metadata", f"Valid metadata.{key} required; malformed fields are not waived in local-draft mode")
        if "expert_time_estimate_hours" not in meta:
            self.publication_missing("expert_time", "A defensible expert_time_estimate_hours is pending; do not invent human timing")
        elif not numeric(meta.get("expert_time_estimate_hours")):
            self.publication_metadata_complete = False
            self.issue("expert_time", "expert_time_estimate_hours must be finite and positive; it is an estimate, not measured runtime")
        for old in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
            if old in meta:
                self.issue("readme_metadata", f"Move {old} to the corresponding README section")
        agent = self.table(cfg, "agent", NETWORK_FIELDS | {"timeout_sec", "user"})
        self.phase_fields(agent, "agent")
        if not numeric(agent.get("timeout_sec")) or agent.get("timeout_sec") != 28800:
            self.issue("agent_timeout", "TB-Science requires agent.timeout_sec = 28800")
        if "network_mode" in agent and agent["network_mode"] != "public":
            self.issue("agent_network_override", "Agent override must not defeat public-network Science mode")
        env = self.table(cfg, "environment", ENV_FIELDS)
        self.environment(env, "environment", agent=True)
        verifier = self.table(cfg, "verifier", NETWORK_FIELDS | {"timeout_sec", "env", "user", "environment_mode", "environment", "collect"})
        self.phase_fields(verifier, "verifier")
        if "collect" in verifier:
            self.issue("unsupported_collect", "Verifier collect hooks require separate review; this profile uses declared artifacts only")
        if verifier.get("environment_mode") != "separate":
            self.issue("separate_verifier", "verifier.environment_mode must be separate")
        if not numeric(verifier.get("timeout_sec")):
            self.issue("verifier_timeout", "A finite positive verifier.timeout_sec is required")
        ve = self.table(verifier, "environment", ENV_FIELDS)
        self.environment(ve, "verifier.environment", agent=False)
        if "network_mode" in verifier and verifier["network_mode"] != "no-network":
            self.issue("verifier_network_override", "Verifier override must not defeat no-network isolation")
        if "solution" in cfg:
            solution = self.table(cfg, "solution", {"env"})
            if "env" in solution and not string_map(solution["env"]):
                self.issue("field_type", "solution.env must map strings to strings")
        artifacts = cfg.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            self.issue("artifacts", "Nonempty top-level artifacts array required; not under [verifier]")
            artifacts = []
        safe = []
        for artifact in artifacts:
            if not artifact_path(artifact):
                self.issue("artifact_path", f"Unsafe/noncanonical artifact path: {artifact!r}")
            else:
                safe.append(artifact)
        if len(set(safe)) != len(safe):
            self.issue("duplicate_artifact", "Duplicate artifact paths")
        for a in safe:
            if any(a != b and PurePosixPath(b) in PurePosixPath(a).parents for b in safe):
                self.issue("overlapping_artifacts", "Parent/child artifact declarations overlap")
        return cfg, safe

    def phase_fields(self, table: dict, name: str) -> None:
        if "user" in table and not (type(table["user"]) is int or string(table["user"])):
            self.issue("field_type", f"{name}.user must be an integer or nonempty string")
        if "env" in table and not string_map(table["env"]):
            self.issue("field_type", f"{name}.env must map strings to strings")
        if "allowed_hosts" in table and not string_list(table["allowed_hosts"]):
            self.issue("field_type", f"{name}.allowed_hosts must be a string array")

    def environment(self, env: dict, name: str, *, agent: bool) -> None:
        self.phase_fields(env, name)
        expected = "public" if agent else "no-network"
        if env.get("network_mode") != expected:
            self.issue("network_policy", f"{name}.network_mode must explicitly be {expected}; allowlist requires a separately reviewed exception")
        if env.get("allowed_hosts"):
            self.issue("network_hosts", f"{name}.allowed_hosts conflicts with this profile's explicit {expected} policy")
        if "allow_internet" in env:
            self.issue("deprecated_network", f"Remove deprecated {name}.allow_internet")
        for key in ("build_timeout_sec", "cpus", "memory_mb", "storage_mb"):
            if (agent or key in env) and not numeric(env.get(key)):
                self.issue("resource", f"{name}.{key} must be finite and positive")
        for key in ("memory_mb", "storage_mb"):
            if key in env and type(env[key]) is not int:
                self.issue("field_type", f"{name}.{key} must be an integer")
        for key in ("docker_image", "skills_dir", "workdir", "backend", "validate_env"):
            if key in env and not string(env[key]):
                self.issue("field_type", f"{name}.{key} must be a string")
        if "os" in env and env["os"] not in ("linux", "windows"):
            self.issue("field_type", f"{name}.os must be linux or windows")
        for key in ("healthcheck", "mcp_servers", "tpu"):
            if key in env:
                self.issue("unsupported_environment_feature", f"{name}.{key} requires separate schema/exposure review outside this profile")
        if "gpu_types" in env and not string_list(env["gpu_types"], required=True):
            self.issue("field_type", f"{name}.gpu_types must be a nonempty string array")
        if "gpus" in env and (type(env["gpus"]) is not int or not 0 <= env["gpus"] <= 1):
            self.issue("gpu_count", f"{name}.gpus must be integer 0 or 1")
        if numeric(env.get("gpus")):
            if not isinstance(env.get("gpu_types"), list) or not nonempty(env["gpu_types"]):
                self.issue("gpu_type", f"{name}.gpu_types required for a GPU")
            if agent and env.get("backend", env.get("validate_env")) != "hosted":
                self.issue("gpu_backend", "TB-Science GPU execution requires backend=hosted; no rental is authorized by validation")
        if agent and (numeric(env.get("cpus")) and env["cpus"] > 4 or numeric(env.get("memory_mb")) and env["memory_mb"] > 16384):
            if env.get("backend", env.get("validate_env")) != "hosted":
                self.issue("large_backend", "Resources exceed default Science runner; explicitly review hosted backend")

    def files(self, artifacts: list[str]) -> None:
        instruction = self.text(self.task / "instruction.md")
        if not instruction.endswith(SUFFIX):
            self.issue("instruction_suffix", "instruction.md must end with the exact timeout/anti-cheat paragraph and newline")
        for a in artifacts:
            if a not in instruction:
                self.issue("artifact_instruction", f"Declared artifact absent from instruction: {a}")
        readme = self.text(self.task / "README.md")
        readme = re.sub(r"<!--.*?-->", "", readme, flags=re.S)
        for heading in ("Difficulty", "Reference solution", "Verification"):
            found = re.search(r"(?mi)^##\s+" + re.escape(heading) + r"\s*\n(.*?)(?=^##\s|\Z)", readme, re.S)
            if not found or not found.group(1).strip():
                self.issue("readme_section", f"README needs a substantive ## {heading} section")
        self.text(self.task / "solution/solve.sh")
        script = self.text(self.task / "tests/test.sh")
        for runtime in ("environment", "tests"):
            self.docker(runtime, artifacts)
        for pattern in (r"\b(?:pip|pip3)\s+install\b", r"\bapt(?:-get)?\s+install\b", r"\buvx\b", r"\buv\s+(?:pip\s+install|run\b[^\n]*--with)\b", r"\bcurl\b[^\n]*\|\s*(?:sh|bash)"):
            if re.search(pattern, script):
                self.issue("runtime_install", "tests/test.sh installs or obtains dependencies at runtime")
        if not re.search(r"--ctrf(?:\s+|=)/logs/verifier/ctrf\.json", script):
            self.issue("ctrf", "tests/test.sh must produce /logs/verifier/ctrf.json using --ctrf")
        test_sources = [script]
        tests = self.task / "tests"
        if tests.exists():
            for p in sorted(tests.rglob("*")):
                if p.is_file() and p.suffix in {".py", ".sh"} and p.name != "test.sh":
                    test_sources.append(self.text(p))
        combined = "\n".join(test_sources)
        if not re.search(r"reward\.(?:txt|json)", combined):
            self.issue("reward_missing", "No reward.txt/reward.json writer reference found in verifier source")
        if "reward.txt" in combined and "reward.json" in combined:
            self.issue("reward_precedence", "Both reward formats appear: JSON takes precedence. Use one unambiguous reward output in this local profile")
        for match in re.finditer(r"\becho\s+['\"]?([\d.]+)['\"]?\s*>[^\n]*reward\.(?:txt|json)", combined):
            try:
                if float(match.group(1)) not in (0.0, 1.0):
                    self.issue("fractional_reward", "Literal nonbinary shell reward found")
            except ValueError:
                self.issue("invalid_reward", "Malformed literal shell reward")
        self.issue("reward_runtime_required", "Static source inspection cannot prove every reward path is binary or fail-closed; recorded oracle/nop and adversarial runs are still required", "warning")

    def docker(self, folder: str, artifacts: list[str]) -> None:
        text = self.text(self.task / folder / "Dockerfile")
        lines = docker_lines(text)
        stages: set[str] = set()
        for command, value in lines:
            if command == "FROM":
                parts = shlex.split(value)
                parts = [p for p in parts if not p.startswith("--")]
                base = parts[0] if parts else ""
                if base not in stages and base != "scratch":
                    if "$" in base or ":" not in base or base.endswith(":latest"):
                        self.issue("image_pin", f"{folder}/Dockerfile base must use an explicit version or digest: {base}")
                    elif "@sha256:" not in base:
                        self.issue("mutable_image_tag", f"{folder}/Dockerfile tag is not a content digest; resolve the image digest for execution evidence", "warning")
                if len(parts) >= 3 and parts[-2].upper() == "AS":
                    stages.add(parts[-1])
            if command in {"COPY", "ADD"} and folder == "environment":
                tokens = copy_tokens(value)
                for source in tokens[:-1]:
                    if source.startswith("/") or ".." in PurePosixPath(source).parts or any(x in PurePosixPath(source).parts for x in ("tests", "solution", "authoring")):
                        self.issue("agent_copy_boundary", f"Agent Dockerfile references protected/out-of-context source: {source}")
        if not any(c == "FROM" for c, _ in lines):
            self.issue("docker_from", f"{folder}/Dockerfile lacks FROM")
        if folder != "tests":
            return
        copies = [copy_tokens(v) for c, v in lines if c in {"COPY", "ADD"}]
        if not any(t and t[-1].rstrip("/") == "/tests" for t in copies):
            self.issue("verifier_copy", "tests/Dockerfile must bake tests into /tests")
        dirs: set[str] = set()
        for command, value in lines:
            if command == "RUN":
                for m in re.finditer(r"\bmkdir\s+-p\s+([^;&|]+)", value):
                    try:
                        dirs.update(x.rstrip("/") for x in shlex.split(m.group(1)) if x.startswith("/"))
                    except ValueError:
                        self.issue("mkdir_syntax", "Cannot statically resolve verifier mkdir command")
        for artifact in artifacts:
            parent = str(PurePosixPath(artifact).parent)
            if parent not in dirs:
                self.issue("artifact_parent", f"Pre-create exact verifier artifact parent with RUN mkdir -p: {parent}")
        if "/logs/verifier" not in dirs:
            self.issue("verifier_log_dir", "Pre-create /logs/verifier in tests/Dockerfile")
        requirements = text
        for file in (self.task / "tests").rglob("*requirements*.txt"):
            requirements += "\n" + self.text(file)
        for name, version in (("pytest", "8.4.1"), ("pytest-json-ctrf", "0.3.5")):
            if not re.search(r"\b" + re.escape(name + "==" + version) + r"(?=[\s'\"]|$)", requirements):
                self.issue("verifier_dependency_pin", f"Bake {name}=={version} into tests/Dockerfile (or its requirements file)")

    def input_lock(self) -> None:
        lock = self.json(self.evidence_dir / "provenance/inputs.lock.json")
        if type(lock.get("schema_version")) is not int or lock.get("schema_version") != 1:
            self.issue("input_schema", "inputs.lock.json schema_version must be 1")
        inputs = lock.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            self.issue("inputs", "Nonempty inputs.lock.json inputs array required for real-data neuroscience tasks")
            return
        seen: set[str] = set()
        for item in inputs:
            if not isinstance(item, dict):
                self.issue("input_type", "Each input must be an object")
                continue
            self.inputs.append(item)
            if not isinstance(item.get("id"), str) or not item["id"] or item["id"] in seen:
                self.issue("input_id", "Input IDs must be nonempty unique strings")
            else:
                seen.add(item["id"])
            if not isinstance(item.get("role"), str) or item.get("role") not in ROLES:
                self.issue("input_role", f"Invalid role for {item.get('id')}")
            url = item.get("url")
            if not isinstance(url, str) or urlparse(url).scheme != "https" or not urlparse(url).netloc:
                self.issue("input_url", "Input needs a public HTTPS provenance URL; availability is not tested here")
            version = item.get("version")
            if not nonempty(version) or not isinstance(version, str) or version.lower() in {"main", "master", "latest", "draft"}:
                self.issue("input_version", "Input needs a release/version identifier, not a moving branch alias")
            if not isinstance(item.get("sha256"), str) or not SHA.fullmatch(item["sha256"]):
                self.issue("input_sha256", "Each exact input file needs a lowercase SHA-256")
            if type(item.get("bytes")) is not int or item["bytes"] <= 0:
                self.issue("input_bytes", "Input bytes must be a positive integer")
            if not nonempty(item.get("license")):
                self.issue("input_license", "Record data/code license or unresolved terms explicitly")
            if "local_path" in item:
                path = inside(self.task, item["local_path"])
                if path is None or not path.is_file():
                    self.issue("input_local_path", "Local input is missing, symlinked, or outside task root")
                else:
                    if path.stat().st_size != item.get("bytes"):
                        self.issue("input_size_mismatch", f"Size mismatch: {item['local_path']}")
                    if path.stat().st_size <= MAX_INLINE_HASH:
                        if sha256(path) != item.get("sha256"):
                            self.issue("input_hash_mismatch", f"SHA-256 mismatch: {item['local_path']}")
                    else:
                        self.issue("input_hash_not_checked", f"{item['local_path']}: >64 MiB; checksum recorded, payload not read by this static validator", "warning")

    def fingerprint(self) -> str:
        """Local source/declared-input fingerprint, NOT Harbor task_checksum or image digest."""
        entries = []
        for file in sorted(self.task.rglob("*")):
            rel = file.relative_to(self.task)
            if any(p in {"authoring", ".git", "__pycache__", ".pytest_cache"} for p in rel.parts):
                continue
            if file.is_symlink():
                self.issue("task_symlink", f"Task source symlink is not fingerprinted: {rel}")
                continue
            if file.is_file():
                if file.stat().st_size <= MAX_INLINE_HASH:
                    entries.append([rel.as_posix(), sha256(file)])
                elif not any(item.get("local_path") == rel.as_posix() for item in self.inputs):
                    self.issue("unlocked_large_file", f"{rel}: file exceeds 64 MiB and lacks an exact local_path input lock; freshness cannot be checked")
        raw = json.dumps({"files": entries, "inputs": self.inputs}, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def run_evidence(self, kind: str, run: Any, fingerprint: str) -> dict[str, Any]:
        if not isinstance(run, dict):
            self.issue("run_type", f"runs.{kind} must be an object")
            return {"status": "invalid"}
        if isinstance(run.get("status"), str) and run.get("status") in {"not_run", "failed", "infrastructure_error"}:
            return {"status": run["status"], "verified": False}
        if run.get("status") != "recorded":
            self.issue("run_status", f"runs.{kind}: use not_run/failed/infrastructure_error/recorded; a 'passed' claim alone is not evidence")
            return {"status": "invalid"}
        before = len([i for i in self.issues if i["severity"] == "error"])
        if run.get("task_fingerprint") != fingerprint:
            self.issue("stale_evidence", f"{kind}: local task fingerprint does not match current source and declared inputs")
        if not string(run.get("harbor_version")) or not timestamp(run.get("completed_at")):
            self.issue("run_provenance", f"{kind}: harbor_version and timezone-aware ISO completed_at required")
        command = run.get("command")
        if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
            self.issue("run_command", f"{kind}: command must be a nonempty string array")
        path = inside(self.evidence_dir, run.get("result_path"))
        if path is None or not path.is_file():
            self.issue("run_path", f"{kind}: result_path missing, symlinked or escaping evidence directory")
            return {"status": "invalid"}
        if sha256(path) != run.get("result_sha256"):
            self.issue("run_digest", f"{kind}: result SHA-256 mismatch")
        result = self.json(path)
        if result.get("task_name") not in {self.task.name, "terminal-bench-science/" + self.task.name}:
            self.issue("run_task", f"{kind}: trial task_name does not identify this task")
        agent = result.get("agent_info")
        config = result.get("config")
        if not isinstance(agent, dict) or agent.get("name") != kind:
            self.issue("run_agent", f"{kind}: expected single-trial result with matching agent_info.name")
        if not isinstance(config, dict) or not isinstance(config.get("agent"), dict) or config["agent"].get("name") != kind:
            self.issue("run_agent_config", f"{kind}: config.agent.name does not match")
        if not timestamp(result.get("finished_at")) or not isinstance(result.get("task_checksum"), str) or not SHA.fullmatch(result["task_checksum"]):
            self.issue("run_finished", f"{kind}: timezone-aware finished_at and native SHA-256 task_checksum required")
        if isinstance(config, dict) and isinstance(config.get("task"), dict) and "path" in config["task"]:
            recorded_path = config["task"]["path"]
            if not isinstance(recorded_path, str) or Path(recorded_path).name != self.task.name:
                self.issue("run_task_path", f"{kind}: config.task.path does not identify this task folder")
        if result.get("exception_info") is not None:
            self.issue("run_exception", f"{kind}: infrastructure/agent exception present; do not count as a task verdict")
        steps = result.get("step_results")
        if steps is None:
            steps = []
        if not isinstance(steps, list) or any(not isinstance(x, dict) or x.get("exception_info") is not None for x in steps):
            self.issue("run_step_exception", f"{kind}: malformed step results or step exception")
        if result.get("verifier_environment_mode") != "separate":
            self.issue("run_environment", f"{kind}: evidence must record verifier_environment_mode=separate")
        vr = result.get("verifier_result")
        rewards = vr.get("rewards") if isinstance(vr, dict) else None
        expected = 1 if kind == "oracle" else 0
        # The single binary-reward local profile is stricter than generic Harbor dictionaries.
        if not isinstance(rewards, dict) or set(rewards) != {"reward"} or type(rewards["reward"]) not in (int, float) or rewards["reward"] != expected:
            self.issue("run_reward", f"{kind}: require exactly reward={expected}; booleans/fractions/extra reward axes are invalid")
        reward_path = inside(self.evidence_dir, run.get("reward_path"))
        if reward_path is None or not reward_path.is_file():
            self.issue("reward_evidence", f"{kind}: captured reward_path required")
        else:
            if sha256(reward_path) != run.get("reward_sha256"):
                self.issue("reward_digest", f"{kind}: captured reward SHA-256 mismatch")
            try:
                raw = self.text(reward_path).strip()
                emitted = json.loads(raw)
                if isinstance(emitted, dict):
                    emitted = emitted.get("reward") if set(emitted) == {"reward"} else None
                if type(emitted) not in (int, float) or emitted != expected:
                    raise ValueError("reward not expected literal binary value")
            except (ValueError, json.JSONDecodeError):
                self.issue("reward_value", f"{kind}: captured emitted reward is not {expected}")
        self.ctrf_evidence(kind, run)
        after = len([i for i in self.issues if i["severity"] == "error"])
        return {"status": "evidence_consistent" if before == after else "invalid", "verified": False,
                "native_task_checksum": result.get("task_checksum"),
                "note": "Hashes establish consistency, not authenticity; runtime was not rerun by this tool."}

    def ctrf_evidence(self, kind: str, run: dict) -> None:
        path = inside(self.evidence_dir, run.get("ctrf_path"))
        if path is None or not path.is_file():
            self.issue("ctrf_evidence", f"{kind}: captured ctrf_path required in this local pytest profile")
            return
        if sha256(path) != run.get("ctrf_sha256"):
            self.issue("ctrf_digest", f"{kind}: captured CTRF SHA-256 mismatch")
        report = self.json(path)
        results = report.get("results")
        if not isinstance(results, dict):
            self.issue("ctrf_results", f"{kind}: CTRF results must be an object")
            return
        tests, summary = results.get("tests"), results.get("summary")
        if not isinstance(tests, list) or not tests or not isinstance(summary, dict):
            self.issue("ctrf_results", f"{kind}: nonempty CTRF tests and summary required")
            return
        counts = {name: 0 for name in ("passed", "failed", "skipped", "pending", "other")}
        for test in tests:
            if not isinstance(test, dict) or not string(test.get("name")) or not isinstance(test.get("status"), str) or test["status"] not in counts:
                self.issue("ctrf_test", f"{kind}: malformed CTRF test name/status")
                return
            counts[test["status"]] += 1
        expected = {"tests": len(tests), **counts}
        for name, value in expected.items():
            if type(summary.get(name)) is not int or summary[name] != value:
                self.issue("ctrf_summary", f"{kind}: summary.{name} does not match test records")
        if kind == "oracle" and (counts["passed"] != len(tests)):
            self.issue("ctrf_oracle", "Oracle evidence must pass every declared test; skipped/pending tests leave qualification incomplete")
        if kind == "nop" and counts["failed"] == 0:
            self.issue("ctrf_nop", "Nop evidence must fail at least one behavioral test; infrastructure failure does not demonstrate task discrimination")

    def execute(self) -> dict[str, Any]:
        _, artifacts = self.config()
        self.files(artifacts)
        self.input_lock()
        fingerprint = self.fingerprint()
        q = self.json(self.evidence_dir / "evidence/qualification.json")
        if type(q.get("schema_version")) is not int or q.get("schema_version") != 1:
            self.issue("qualification_schema", "qualification.json schema_version must be 1")
        authorship = q.get("instruction_authorship")
        if not isinstance(authorship, dict) or not isinstance(authorship.get("kind"), str) or authorship.get("kind") not in {"ai_draft", "human", "human_reviewed_ai_draft", "unknown"}:
            self.issue("authorship_declaration", "Declare instruction_authorship.kind honestly")
            authorship = {"kind": "unknown"}
        self.issue("human_review_required", "Human authorship/expertise and scientific review cannot be certified by this tool", "warning")
        runs = q.get("runs")
        if not isinstance(runs, dict):
            self.issue("runs_type", "qualification.runs must be an object")
            runs = {}
        evidence = {kind: self.run_evidence(kind, runs.get(kind, {"status": "not_run"}), fingerprint) for kind in ("oracle", "nop")}
        checksums_disagree = all(evidence[k].get("native_task_checksum") for k in ("oracle", "nop")) and evidence["oracle"]["native_task_checksum"] != evidence["nop"]["native_task_checksum"]
        if checksums_disagree:
            self.issue("run_checksum_disagreement", "Oracle/nop native task checksums differ; they are not evidence for the same task contents")
        passed = not any(i["severity"] == "error" for i in self.issues)
        technical_pass = not any(i["severity"] == "error" and i.get("gate") != "publication_metadata" for i in self.issues)
        consistent = not checksums_disagree and all(r["status"] == "evidence_consistent" for r in evidence.values())
        runtime_status = "consistent" if consistent else "invalid" if checksums_disagree or any(r["status"] == "invalid" for r in evidence.values()) else "not_recorded" if all(r["status"] == "not_run" for r in evidence.values()) else "incomplete"
        status = "static_failed" if not passed else "runtime_evidence_consistent_review_pending" if consistent else "static_pass_runtime_unverified"
        return {"task": str(self.task), "evidence_dir": str(self.evidence_dir), "static_pass": passed,
                "technical_pass": technical_pass, "publication_metadata_complete": self.publication_metadata_complete,
                "runtime_evidence_status": runtime_status,
                "qualification_status": status, "accepted": False, "task_fingerprint": fingerprint,
                "instruction_authorship": authorship, "runtime_evidence": evidence, "issues": self.issues,
                "profile": {"name": "neuroscience-single-step-tb-science" if self.profile == "science" else "neuroscience-single-step-local-draft", "mode": self.profile, "tb_science_revision": TBS_REVISION, "harbor_revision": HARBOR_REVISION},
                "limits": "Static checks and supplied evidence consistency only. No task execution, sandbox proof, scientific validation, model calibration, human authorship verification or upstream acceptance."}


def validate_task(task: Path, evidence_dir: Path | None = None, profile: str = "science") -> dict[str, Any]:
    audit = Audit(task, evidence_dir, profile)
    try:
        return audit.execute()
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        # Malformed external metadata should produce a report, never a success or a CLI traceback.
        audit.issue("inspection_error", f"Validation could not finish: {type(exc).__name__}: {exc}")
        return {"task": str(task), "static_pass": False, "qualification_status": "static_failed",
                "accepted": False, "issues": audit.issues, "runtime_evidence": {}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path, nargs="+", help="Task directory or collection root; legacy roots are not implicitly scanned")
    parser.add_argument("--evidence-dir", type=Path, help="External authoring root; supported only for a single task")
    parser.add_argument("--json", action="store_true", help="Print machine-readable report to stdout")
    parser.add_argument("--print-fingerprint", action="store_true", help="Print the local task fingerprint for one task; not Harbor task_checksum")
    parser.add_argument("--require-runtime-evidence", action="store_true", help="Also fail unless matching oracle/nop trial evidence is present; still not acceptance")
    parser.add_argument("--profile", choices=("science", "local-draft"), default="science", help="Default science requires publication metadata; explicit local-draft permits missing human declarations only, not malformed fields or technical violations")
    args = parser.parse_args(argv)
    task_dirs: list[Path] = []
    for p in args.tasks:
        if (p / "task.toml").is_file():
            task_dirs.append(p)
        elif p.is_dir():
            task_dirs.extend(sorted(f.parent for f in p.rglob("task.toml") if not f.is_symlink()))
        else:
            parser.error(f"No task directory: {p}")
    task_dirs = list(dict.fromkeys(p.resolve() for p in task_dirs))
    if not task_dirs:
        parser.error("No task.toml files found; an empty collection is not a pass")
    if (args.evidence_dir or args.print_fingerprint) and len(task_dirs) != 1:
        parser.error("--evidence-dir/--print-fingerprint requires exactly one task")
    reports = [validate_task(p, args.evidence_dir, args.profile) for p in task_dirs]
    if args.print_fingerprint:
        print(reports[0].get("task_fingerprint", "unavailable"))
    elif args.json:
        print(json.dumps({"schema_version": 1, "reports": reports, "accepted_count": 0}, indent=2))
    else:
        for report in reports:
            print(f"{report['task']}: {report['qualification_status']}")
            for issue in report["issues"]:
                print(f"  {issue['severity']}: {issue['code']}: {issue['message']}")
            print("  Upstream acceptance and research-grade qualification: not established.")
    return 0 if all(r["static_pass"] and (not args.require_runtime_evidence or r["qualification_status"] == "runtime_evidence_consistent_review_pending") for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
