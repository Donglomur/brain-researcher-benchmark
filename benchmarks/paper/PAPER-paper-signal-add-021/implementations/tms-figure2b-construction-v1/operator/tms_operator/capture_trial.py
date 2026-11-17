"""Fixed capture-only Harbor 0.21.0 child lifecycle for paired TMS Figure 2B.

Import this module only inside the trusted host child after parent source-lock,
runtime/transport/storage and configuration admission. Imports do not run a trial.
No grader, candidate artifact reader, transport callback or provider is installed.
The parent owns private metadata bounds and actual host/container closure.
"""
import json
import os
import re
import time
from pathlib import Path

from harbor.models.task.task import Task
from harbor.models.agent.context import AgentContext
from harbor.models.trial.config import TrialConfig
from harbor.models.trial.result import TrialResult
from harbor.tasks.client import TaskDownloadResult
from harbor.trial.single_step import SingleStepTrial

AGENT_IMPORT = "tms_operator.agent:FigureAgent"
ENVIRONMENT_IMPORT = "tms_operator.terminal:FigureDockerEnvironment"


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _ordinary_path(value):
    path = Path(os.path.abspath(value))
    _need(all(not p.is_symlink() for p in (path, *path.parents)),
          "no symbolic path ancestors")
    return path


def config_bytes(config):
    """Canonical mutation guard; this is not independent execution authority."""
    _need(type(config) is TrialConfig, "exact selected Harbor TrialConfig type")
    return json.dumps(
        config.model_dump(mode="json", context={"redact_sensitive_env": False}),
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _admit_local_configuration(config, task_root, admitted_config):
    _need(type(admitted_config) is bytes and config_bytes(config) == admitted_config,
          "unchanged independently admitted configuration")
    root = _ordinary_path(task_root)
    _need(root.is_dir() and config.task.path is not None
          and _ordinary_path(config.task.path) == root, "exact existing local task")
    _need(all(getattr(config.task, key) is None for key in
              ("git_url", "git_commit_id", "name", "ref", "download_dir", "source"))
          and config.task.overwrite is False, "no remote/package/download task")
    _need(config.source_trial is None and config.install_only is False
          and not config.extra_instruction_paths, "fresh candidate task only")
    _need(config.agent.name is None and config.agent.import_path == AGENT_IMPORT,
          "only fixed FigureAgent implementation")
    _need(type(config.agent.model_name) is str and bool(config.agent.model_name.strip()),
          "explicit model identity")
    _need(not config.agent.skills and not config.agent.mcp_servers
          and not config.agent.env and not config.agent.extra_allowed_hosts
          and config.agent.load_trajectory is None
          and config.agent.resume_trajectory is False,
          "no injected agent environment/skills/tools/trajectory")
    # FigureAgent's fixed source validates its admitted data-only kwargs schema.
    # Canonical serialization above refuses non-JSON callable/config objects.
    _need(config.verifier.disable is True and config.verifier.import_path is None
          and not config.verifier.kwargs and not config.verifier.env
          and not config.verifier.include_logs and not config.verifier.exclude_logs,
          "verifier disabled without imported implementation or relay")
    _need(not config.artifacts, "no automatic artifact specifications")
    _need(config.environment.type is None
          and config.environment.import_path == ENVIRONMENT_IMPORT
          and not config.environment.env
          and not config.environment.extra_docker_compose
          and not config.environment.extra_allowed_hosts
          and config.environment.force_build is False
          and config.environment.delete is True,
          "only fixed bounded Docker successor, fresh deleted lifecycle")
    # The fixed environment source validates its admitted runtime-binding kwargs;
    # no class/module selector is accepted through those data-only operands.
    trials = _ordinary_path(config.trials_dir)
    _need(trials.is_dir(), "existing trusted trial parent")
    name = config.trial_name
    _need(type(name) is str and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name) is not None,
          "explicit ordinary trial-name component")
    trial_path = _ordinary_path(trials / name)
    _need(not trial_path.exists(), "fresh trial namespace")
    _need(not trial_path.is_relative_to(root) and not root.is_relative_to(trial_path),
          "task source and mutable trial namespace are disjoint")
    return root, trial_path


class CaptureOnlySingleStepTrial(SingleStepTrial):
    """Fixed normal/recovery paths with no Harbor output copier or verifier."""

    def __init__(self, config, *, _task, _task_download_result):
        self._capture_journal = []
        self._capture_normal_return = False
        self._capture_run_entered = False
        self._capture_recovery_entered = False
        self._capture_factory_identity = None
        super().__init__(
            config, _task=_task, _task_download_result=_task_download_result,
        )
        self._journal("constructed")

    async def run(self):
        _need(self._capture_factory_identity is not None
              and not self._capture_run_entered, "one factory-bound native run")
        self._capture_run_entered = True
        return await super().run()

    def _journal(self, event):
        # One immutable source-defined phase schedule; never candidate text.
        permitted = {
            "constructed", "agent-phase-enter", "agent-phase-normal-return",
            "normal-stop-attempt", "normal-path-return",
            "recovery-enter", "recovery-stop-return", "generic-scrub-suppressed",
        }
        _need(event in permitted and len(self._capture_journal) < 8,
              "finite capture lifecycle journal")
        self._capture_journal.append({
            "index": len(self._capture_journal),
            "event": event,
            "monotonic_ns": time.monotonic_ns(),
        })

    async def _run(self):
        _need(self.config.verifier.disable is True,
              "capture-only invariant: verifier disabled")
        _need(not self._capture_normal_return and not self._capture_recovery_entered,
              "one candidate phase")
        self._journal("agent-phase-enter")
        # Unlike SingleStepTrial._run_agent, this direct call does not finally
        # synchronize logs and does not swallow known agent failures.
        await self._run_agent_phase(
            target=self.result,
            instruction=self.task.instruction,
            timeout_sec=self._agent_timeout_sec,
            user=self.task.config.agent.user,
            resume=False,
            load=False,
        )
        self._capture_normal_return = True
        self._journal("agent-phase-normal-return")
        self._journal("normal-stop-attempt")
        await self._stop_agent_environment()
        self._journal("normal-path-return")

    async def _recover_outputs(self):
        self._capture_recovery_entered = True
        self._journal("recovery-enter")
        # Failure outputs stay in independently bounded private storage.
        # They are not copied, parsed, backfilled or graded here.
        await self._stop_agent_environment()
        self._journal("recovery-stop-return")

    async def _sync_agent_output(self, target):
        raise RuntimeError("automatic agent-output synchronization is forbidden")

    async def _download_agent_logs(self):
        raise RuntimeError("automatic log download is forbidden")

    async def _upload_agent_logs(self):
        raise RuntimeError("automatic log upload is forbidden")

    async def _collect_artifacts(self, *, stop_main_before_sidecars=False):
        raise RuntimeError("automatic artifact collection is forbidden")

    async def _collect_artifacts_phased(
        self, *, artifacts_dir, step_cfg=None, step_artifacts=None,
        stop_main_before_sidecars=False,
    ):
        raise RuntimeError("automatic phased artifact collection is forbidden")

    async def _run_verifier(self):
        raise RuntimeError("capture-only trial never invokes a verifier")

    def _scrub_jobs_dir(self):
        # Preserve scientific bytes: do not recursively read/rewrite candidate
        # outputs via Harbor's generic secret scrubber. All logs/result metadata
        # remain private and unredacted; publication is not authorized by this.
        self._journal("generic-scrub-suppressed")


async def create_capture_trial(config, *, task_root, admitted_config):
    """Construct exact local subclass after caller-owned source/runtime admission.

    No generic Trial.create or TaskClient download dispatch is used. The local
    TaskDownloadResult fields match TaskClient._download_local_tasks exactly.
    This function can create private trial metadata when called; do not call it
    during source inspection or before genuine runtime admission.
    """
    root, trial_path = _admit_local_configuration(
        config, task_root, admitted_config,
    )
    task = Task(
        task_dir=root, extra_instruction_paths=[], disable_verification=True,
    )
    _need(not task.has_steps and not task.config.steps, "single-step local task")
    _need(not task.config.artifacts and not task.config.verifier.collect,
          "no task artifact transfer or collect hooks")
    _need(not task.config.environment.mcp_servers
          and not task.config.environment.skills_dir,
          "no task-supplied tools or skills")
    download = TaskDownloadResult(
        path=root, download_time_sec=0.0, cached=True,
    )
    # Recheck mutation/freshness immediately before Trial's filesystem and
    # custom-agent constructor side effects.
    _, current_path = _admit_local_configuration(config, root, admitted_config)
    _need(current_path == trial_path, "unchanged selected trial destination")
    trial = CaptureOnlySingleStepTrial(
        config, _task=task, _task_download_result=download,
    )
    _need(type(trial) is CaptureOnlySingleStepTrial
          and _ordinary_path(trial.paths.trial_dir) == trial_path,
          "exact capture subclass and path")
    trial._capture_factory_identity = (id(trial), bytes(admitted_config))
    return trial


def terminal_summary(trial, result):
    """Return trusted lifecycle observations and raw fields, never grading authority.

    The parent must capture/serialize the returned raw fields under its explicit
    private-result budget, and verify the fixed FigureAgent terminal receipt.
    No recursive model_dump of arbitrary AgentContext metadata is performed here.
    """
    _need(type(trial) is CaptureOnlySingleStepTrial, "exact capture trial")
    _need(type(result) is TrialResult and result is trial.result,
          "same actual Harbor result object")
    identity = trial._capture_factory_identity
    _need(type(identity) is tuple and len(identity) == 2 and identity[0] == id(trial)
          and config_bytes(trial.config) == identity[1],
          "factory and unchanged configuration identity")
    _need(trial._capture_normal_return is True
          and trial._capture_recovery_entered is False,
          "actual awaited phase return without recovery")
    _need(result.exception_info is None, "no recorded setup/agent/cleanup exception")
    _need(result.started_at is not None and result.finished_at is not None
          and result.finished_at >= result.started_at, "complete trial timing")
    timing = result.agent_execution
    _need(timing is not None and timing.started_at is not None
          and timing.finished_at is not None
          and timing.finished_at >= timing.started_at, "complete candidate timing")
    _need(result.verifier is None and result.verifier_result is None,
          "no verification was performed")
    context = result.agent_result
    _need(type(context) is AgentContext, "exact actual AgentContext present")
    expected = ["constructed", "agent-phase-enter", "agent-phase-normal-return",
                "normal-stop-attempt", "normal-path-return", "generic-scrub-suppressed"]
    _need([r["event"] for r in trial._capture_journal] == expected,
          "complete exact normal-path journal")
    return {
        "schema": "tms_capture_trial_terminal_summary_v1",
        "trial_id": str(result.id),
        "trial_name": result.trial_name,
        "journal": [dict(r) for r in trial._capture_journal],
        "trial_timing": {"started_at": result.started_at.isoformat(),
                         "finished_at": result.finished_at.isoformat()},
        "agent_timing": {"started_at": timing.started_at.isoformat(),
                         "finished_at": timing.finished_at.isoformat()},
        "agent_info": {
            "name": result.agent_info.name,
            "version": result.agent_info.version,
            "model_info": None if result.agent_info.model_info is None else {
                "name": result.agent_info.model_info.name,
                "provider": result.agent_info.model_info.provider,
            },
        },
        "agent_result_raw": {
            "n_input_tokens": context.n_input_tokens,
            "n_cache_tokens": context.n_cache_tokens,
            "n_output_tokens": context.n_output_tokens,
            "cost_usd": context.cost_usd,
            "rollout_details": context.rollout_details,
            "metadata": context.metadata,
        },
        "exception_info": None,
        "private_logs_redacted": False,
        "generic_agent_result_is_completion_proof": False,
        "agent_specific_completion_admission": "requires_fixed_FigureAgent_receipt",
        "external_host_and_container_absence_observed_by_this_module": False,
        "private_grading_performed": False,
    }
