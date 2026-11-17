#!/usr/bin/env python3
"""Idempotently patch Harbor's claude-code agent to read the host's logged-in
Claude session OAuth token as a fallback.

Why: `harbor run -a claude-code` only reads CLAUDE_CODE_OAUTH_TOKEN from the
process env. Without `export CLAUDE_CODE_OAUTH_TOKEN=...` the in-container agent
comes up "Not logged in" -> authentication_failed -> NonZeroAgentExitCodeError
(a 0.0 that is NOT a real task failure). This patch makes it fall back to
~/.claude/.credentials.json -> claudeAiOauth.accessToken, so the current
interactive login authenticates the agent. An exported env var still wins.

Usage:
    python patch_harbor_oauth.py                # auto-detect the active harbor
    python patch_harbor_oauth.py /path/to/harbor [/another/harbor ...]
        (each path may be a harbor package dir, a src/ tree, or the
         claude_code.py file itself)

Safe to re-run (detects an existing patch and skips). Re-run after any
`uv tool upgrade harbor` / reinstall.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from pathlib import Path

MARKER = "session_oauth_token"  # present if already patched (this file or a hand-edit)

HELPER = '''

def _br_session_oauth_token() -> str:
    """Fallback: read the host's logged-in Claude session OAuth token.

    Added by patch_harbor_oauth.py. Lets `-a claude-code` authenticate from
    ~/.claude/.credentials.json (claudeAiOauth.accessToken) without exporting
    CLAUDE_CODE_OAUTH_TOKEN. Env var still wins. Read fresh each run so the
    current (possibly refreshed) session token is used. Never logs the value.
    """
    import json as _json
    import os as _os
    import time as _time
    from pathlib import Path as _Path

    for _p in (
        _os.environ.get("CLAUDE_CREDENTIALS_PATH"),
        _os.path.expanduser("~/.claude/.credentials.json"),
    ):
        if not _p:
            continue
        try:
            _data = _json.loads(_Path(_p).read_text())
        except Exception:
            continue
        _oauth = _data.get("claudeAiOauth") or {}
        _tok = _oauth.get("accessToken")
        if not _tok:
            continue
        _exp = _oauth.get("expiresAt")
        if isinstance(_exp, (int, float)) and _exp > 0 and _exp / 1000.0 < _time.time():
            print(
                f"[harbor patch] session OAuth token in {_p} is expired; refresh "
                "your Claude login or set CLAUDE_CODE_OAUTH_TOKEN.",
                file=sys.stderr,
            )
        return _tok
    return ""
'''

# The exact env-dict line Harbor uses (upstream + stebo85 forks share it).
# Anchor on the env-DICT assignment ("KEY": os.environ.get(KEY, "")) so we patch the
# line that actually injects the token into the container — not an unrelated
# bool(os.environ.get(KEY, "")) "is-configured" check that some branches also have.
OAUTH_RE = re.compile(
    r'("CLAUDE_CODE_OAUTH_TOKEN"\s*:\s*)os\.environ\.get\(\s*"CLAUDE_CODE_OAUTH_TOKEN"\s*,\s*""\s*\)'
)
OAUTH_NEW = r'\1os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or _br_session_oauth_token()'


def find_claude_code_files(target: str) -> list[Path]:
    p = Path(target)
    if p.is_file():
        return [p]
    if p.is_dir():
        return [
            Path(x)
            for x in glob.glob(
                str(p / "**" / "agents" / "installed" / "claude_code.py"),
                recursive=True,
            )
        ]
    return []


def auto_targets() -> list[Path]:
    hits: list[Path] = []
    # uv-tool install(s)
    for g in glob.glob(
        os.path.expanduser(
            "~/.local/share/uv/tools/harbor/lib/python*/site-packages/harbor/"
            "agents/installed/claude_code.py"
        )
    ):
        hits.append(Path(g))
    # whatever `import harbor` resolves to in this interpreter
    try:
        import harbor  # type: ignore

        cc = Path(harbor.__file__).parent / "agents" / "installed" / "claude_code.py"
        if cc.is_file():
            hits.append(cc)
    except Exception:
        pass
    # de-dupe
    seen, out = set(), []
    for h in hits:
        r = h.resolve()
        if r not in seen:
            seen.add(r)
            out.append(h)
    return out


def patch_file(f: Path) -> str:
    text = f.read_text()
    if MARKER in text:
        return "already patched (skip)"
    if not OAUTH_RE.search(text):
        return "OAuth line not found — unrecognized shape, patch manually"
    new = OAUTH_RE.sub(OAUTH_NEW, text, count=1)
    new = new.rstrip("\n") + "\n" + HELPER
    f.write_text(new)
    # sanity: compile
    import py_compile

    try:
        py_compile.compile(str(f), doraise=True)
    except Exception as e:  # pragma: no cover
        f.write_text(text)  # revert
        return f"reverted — compile failed: {e}"
    return "PATCHED"


def main() -> int:
    args = sys.argv[1:]
    targets: list[Path] = []
    if args:
        for a in args:
            fs = find_claude_code_files(a)
            if not fs:
                print(f"  (no claude_code.py under {a})")
            targets += fs
    else:
        targets = auto_targets()

    if not targets:
        print("No harbor claude_code.py found. Pass a path explicitly.")
        return 1

    seen = set()
    for f in targets:
        r = f.resolve()
        if r in seen:
            continue
        seen.add(r)
        print(f"{patch_file(f):45}  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
