"""Fixed investigator procedure, executed ONLY inside the selected isolated worker.

There is no model/network call at import. The trusted host owns the bounded
broker, credentials and all mounted input/output/model limits. Python actions
below are candidate actions inside that worker, never a host execution route.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def parse(text):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def instructions(value):
    fields = {"schema", "system_prompt", "max_actions", "max_output_tokens",
              "max_code_bytes", "max_tool_output_bytes"}
    need(type(value) is dict and set(value) == fields and
         value["schema"] == "neural083_agent_instructions_v1", "Exact investigator instructions")
    need(type(value["system_prompt"]) is str and value["system_prompt"], "Nonempty captured prompt")
    for name in fields - {"schema", "system_prompt"}:
        need(type(value[name]) is int and value[name] > 0, "Explicit positive investigator limit")
    return value


class BoundedText(io.TextIOBase):
    def __init__(self, limit):
        self.limit = limit
        self.parts = []
        self.used = 0

    def write(self, text):
        need(type(text) is str, "Text tool output")
        size = len(text.encode("utf8"))
        need(self.used + size <= self.limit, "Tool output ceiling")
        self.parts.append(text)
        self.used += size
        return len(text)

    def value(self):
        return "".join(self.parts)


def python_action(code, state, output_limit):
    """Actual worker-local numerical action; isolation is outside this function."""
    capture = BoundedText(output_limit)
    try:
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            exec(compile(code, "<isolated-agent-action>", "exec"), state)
        error = None
    except Exception as exc:
        # Exception strings may be arbitrarily large; retain only their type.
        error = type(exc).__name__
    return {"stdout": capture.value(), "error_type": error}


def investigate(phase, client, config, output_path, *, action=python_action):
    """Concrete bounded loop; injected action is an explicitly inert test leaf."""
    config = instructions(config)
    need(phase in ("fit", "infer"), "Fixed training or query stage")
    role = ("Fit using only /input training data; write /output/model.bin. "
            "Use only permitted labels and training-only inner validation. No query is mounted."
            if phase == "fit" else
            "Infer all100 opaque-ordered queries in /input; use immutable /model/model.bin. "
            "Write the original complete prediction schema to /output/predictions.json. "
            "Do not refit/tune/normalize/calibrate using query inputs. No training mount is present.")
    messages = [{"role": "system", "content": config["system_prompt"]},
                {"role": "user", "content": role + " Return exactly JSON {action:python,code:string} "
                 "or {action:finish}, with quoted JSON keys/values. Python actions execute only in this worker. "
                 "All probabilities and condition identity must follow /input/case.json. "
                 "The entire query batch is visible; this does not authorize batch fitting. "
                 "Captured fit/source alone does not establish stochastic-state equivalence."}]
    state = {"__name__": "__isolated_agent__"}
    for ordinal in range(config["max_actions"]):
        reply = client.generate(messages=messages, max_output_tokens=config["max_output_tokens"])
        need(type(reply) is dict and set(reply) == {"text", "usage"} and type(reply["text"]) is str,
             "Bounded broker reply")
        value = parse(reply["text"])
        need(type(value) is dict and value.get("action") in ("python", "finish"), "Declared investigator action")
        messages.append({"role": "assistant", "content": reply["text"]})
        if value["action"] == "finish":
            need(set(value) == {"action"}, "Exact finish action")
            path = Path(output_path)
            need(path.is_file() and not path.is_symlink() and path.stat().st_size > 0,
                 "Required stage artifact before finish")
            return {"status": "finished", "actions": ordinal + 1,
                    "semantic_no_query_fitting_established": False}
        need(set(value) == {"action", "code"} and type(value["code"]) is str and
             0 < len(value["code"].encode("utf8")) <= config["max_code_bytes"], "Bounded Python action")
        observation = action(value["code"], state, config["max_tool_output_bytes"])
        need(type(observation) is dict and set(observation) == {"stdout", "error_type"}, "Tool observation schema")
        need(type(observation["stdout"]) is str and
             len(observation["stdout"].encode("utf8")) <= config["max_tool_output_bytes"] and
             (observation["error_type"] is None or type(observation["error_type"]) is str), "Bounded tool observation")
        messages.append({"role": "user", "content": json.dumps(observation, allow_nan=False)})
    raise ValueError("Investigator action allocation exhausted before a complete artifact")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("fit", "infer"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--model")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    need(args.input == "/input" and args.out == ("/output/model.bin" if args.phase == "fit" else "/output/predictions.json") and
         args.model == (None if args.phase == "fit" else "/model/model.bin"), "Fixed isolated worker paths")
    # This path is a separately captured, readonly trusted mount, not a host route.
    helper = Path("/trusted/openbmi_agent_tools.py")
    spec = importlib.util.spec_from_file_location("openbmi_agent_tools", helper)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    raw = Path("/trusted/AGENT_INSTRUCTIONS.json").read_bytes()
    need(0 < len(raw) <= 1048576, "Bounded captured instruction member")
    investigate(args.phase, client, parse(raw.decode("utf8")), args.out)


if __name__ == "__main__":
    main()
