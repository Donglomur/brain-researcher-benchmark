"""Operator-side numeric dialogue for the existing Hybrid causal consumer.

No provider, API, model, data file, or process is started by this module. The
provider receives only next_request()'s copied value, never this trusted object.
This is protocol construction, not isolation or complete-cohort qualification.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import types

CONSUMER_BYTES = 13637
CONSUMER_SHA256 = "c5876452457f05c3f9fe69015f7e6cff565dcfa43b6a7b9e8921b096cdd1d00b"
TOKEN = re.compile(r"[0-9a-f]{64}\Z")
CONDITION = "unassisted_numeric_dialogue"
SYSTEM_PROMPT = """Predict the next recorded human action from the currently revealed processed behavioral state.
Return one JSON object with exactly token and probabilities. Copy the current opaque token exactly. probabilities contains four strictly positive finite numbers in recorded class order [1,2,3,4], each below 1 and summing to 1 within 1e-9. Classes 3 and 4 are terminal actions. No explanation, Markdown, additional keys, tool call, or multiple answer is accepted.
The observation contains the complete permitted current state: nL,nR,nB,rL,rR,muL,muR,gL,gR,first_visit,after_first_visit,t. The L/R counts can encode observed colored evidence or an initial visible cue; mu=(r+1)/(n+2) is not a universal initial-cue identity. gL/gR are exclusive cursor flags. first_visit/after_first_visit are exclusive history flags. t is the source cursor-local decision clock, not elapsed seconds.
Use only this state and the observations and your committed responses earlier in this same trial. No model artifact, tools, external data, target feedback, or future trial length is supplied. A new trial starts a fresh dialogue. These are processed behavioral states, not neural recordings."""


class DialogueError(ValueError):
    """The complete dialogue is unusable after a protocol failure."""


def load_consumer(source_path=None):
    """Authenticate the exact existing consumer before executing captured bytes.

    An explicit path permits private generated controls without copying source.
    It cannot select a different consumer implementation or relaxed contract.
    """
    path = Path(source_path) if source_path is not None else (
        Path(__file__).resolve().parents[1]
        / "hybrid-frozen-model-candidate" / "runner" / "consumer.py"
    )
    with path.open("rb") as handle:
        body = handle.read(CONSUMER_BYTES + 1)
    if len(body) != CONSUMER_BYTES or hashlib.sha256(body).hexdigest() != CONSUMER_SHA256:
        raise DialogueError("unaccepted causal consumer source")
    name = "_hybrid_direct_consumer_" + CONSUMER_SHA256
    module = types.ModuleType(name)
    module.__file__ = str(path)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        exec(compile(body, str(path), "exec"), module.__dict__)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    return module


class DirectDialogue:
    """Trusted adapter around an authenticated consumer.OnlineSession.

    The operator retains all private cases and this object. A transport starts a
    fresh provider conversation whenever new_trial is true and sends exactly
    messages. It must independently prohibit tools and persistent cross-trial
    state; the Python interface itself cannot prove either restriction.
    """

    def __init__(self, consumer, session):
        if type(session) is not consumer.OnlineSession:
            raise DialogueError("use the authenticated consumer's OnlineSession")
        self._consumer = consumer
        self._session = session
        self._messages = []
        self._pending = False
        self._failed = False
        self._complete = False

    def _require_live(self):
        if self._failed:
            raise DialogueError("dialogue aborted")
        if self._complete:
            raise DialogueError("dialogue already complete")

    def next_request(self):
        """Return only permitted messages, or None after the final commitment."""
        try:
            self._require_live()
            if self._pending:
                raise DialogueError("commit before requesting another state")
            query = self._session.next_query()
            if query is None:
                self._complete = True
                return None
            if type(query) is not dict or set(query) != {"schema", "token", "new_trial", "observation"}:
                raise DialogueError("exact current-query fields required")
            if query["schema"] != "hybrid-current-query-v1" or type(query["new_trial"]) is not bool:
                raise DialogueError("current-query schema or trial marker")
            if type(query["token"]) is not str or TOKEN.fullmatch(query["token"]) is None:
                raise DialogueError("opaque current token")
            self._consumer.validate_observation(query["observation"])
            if query["new_trial"]:
                self._messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            elif not self._messages:
                raise DialogueError("first state must start a new trial")
            content = json.dumps(query, sort_keys=True, separators=(",", ":"), allow_nan=False)
            if len(content.encode("utf-8")) > 4096:
                raise DialogueError("current query byte bound")
            self._messages.append({"role": "user", "content": content})
            self._pending = True
            return {"condition": CONDITION, "new_trial": query["new_trial"],
                    "messages": copy.deepcopy(self._messages)}
        except Exception:
            self._failed = True
            raise

    def submit(self, response_body):
        """Commit a single raw JSON response; return no target feedback.

        The provider adapter must supply response bytes only, rejecting tool-call
        or multiple-candidate envelopes before this entry point. Extra keys,
        duplicate JSON keys, prose, invalid numbers, or a replayed token abort.
        """
        try:
            self._require_live()
            if not self._pending:
                raise DialogueError("no unanswered state")
            reply = self._consumer.decode_reply(response_body)
            # The consumer checks exact fields, current token and the original
            # strict four-class probability rule. No repair or answer retry.
            self._session.commit(reply)
            content = json.dumps(reply, sort_keys=True, separators=(",", ":"), allow_nan=False)
            self._messages.append({"role": "assistant", "content": content})
            self._pending = False
        except Exception:
            self._failed = True
            raise

    def finished_predictions(self):
        """Operator-only result; not a complete-population or isolation receipt.

        Full authentic evaluation must still use the existing complete-cohort
        source admission, scorer, failure accounting and participant bootstrap.
        """
        if self._failed or not self._complete or self._pending:
            raise DialogueError("dialogue unfinished or aborted")
        return self._session.finished_predictions()
