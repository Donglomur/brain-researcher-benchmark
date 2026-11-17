"""Exact used lifecycle primitives; unrelated donor task constants omitted."""
from __future__ import annotations

from dataclasses import asdict

import hashlib

import json

import math

import os

from pathlib import Path

import re

import resource

import selectors

import shutil

import signal

import stat

import sys

import threading

import time

import types

class OwnerError(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise OwnerError(reason)

def sha(body):
    return hashlib.sha256(body).hexdigest()

def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)

class WallFuse:
    """Fatal outer watchdog. A fuse exit leaves the directory unqualified.

    No successful receipt exists before all groups close. A fatal watchdog cannot
    itself certify reaping; its abandoned output must remain quarantined.
    """
    def __init__(self, until, owner_rss_limit=64 * 1048576):
        self.until, self.owner_rss_limit = until, owner_rss_limit
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.owned = {}
        self.thread = threading.Thread(target=self._watch, daemon=True)

    def add(self, child):
        need(child.pid > 1 and child.pid != os.getpgrp(), "separate owned process group")
        with self.lock:
            self.owned[child.pid] = child

    def closed(self, child):
        with self.lock:
            self.owned.pop(child.pid, None)

    def close_remaining(self, until):
        """Independent last cleanup attempt; original failure is never erased."""
        with self.lock:
            children = tuple(self.owned.values())
        rows = []
        for child in children:
            row = {"pid": child.pid, "reaped": False, "process_group_absent": False, "errors": [], "signals_sent": []}
            try:
                os.killpg(child.pid, 0)
                os.killpg(child.pid, signal.SIGKILL)
                row["signals_sent"].append("SIGKILL")
            except ProcessLookupError:
                pass
            except BaseException as exc:
                row["errors"].append({"kill": type(exc).__name__})
            try:
                child.wait(timeout=max(0, min(.5, until - time.monotonic())))
                row["reaped"] = True
            except BaseException as exc:
                row["errors"].append({"reap": type(exc).__name__})
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                row["process_group_absent"] = True
            except BaseException as exc:
                row["errors"].append({"absence": type(exc).__name__})
            if row["reaped"] and row["process_group_absent"]:
                self.closed(child)
            rows.append(row)
        return rows

    def _watch(self):
        try:
            while not self.stop.wait(.02):
                if time.monotonic() >= self.until or rss_bytes() > self.owner_rss_limit:
                    self._fatal()
        except BaseException:
            self._fatal()

    def _fatal(self):
        try:
            with self.lock:
                for pid in self.owned:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except BaseException:
                        pass
        finally:
            os._exit(124)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *unused):
        # Unresolved descendants are never abandoned by disarming the fatal fuse.
        with self.lock:
            unresolved = bool(self.owned)
        if unresolved:
            self.thread.join(timeout=max(0, self.until - time.monotonic()) + .1)
            os._exit(124)
        self.stop.set()
        self.thread.join(timeout=.5)

def accept_gate(expected_sha, original_parent, until, *, fd=0):
    """A bounded EOF-terminated gate; no work is allowed until it is accepted."""
    need(type(expected_sha) is str and re.fullmatch("[0-9a-f]{64}", expected_sha), "gate SHA256")
    need(type(original_parent) is int and original_parent > 1 and os.getppid() == original_parent, "live gate owner")
    need(type(until) in (int, float) and math.isfinite(until), "finite gate horizon")
    body = bytearray()
    with selectors.DefaultSelector() as selector:
        os.set_blocking(fd, False)
        selector.register(fd, selectors.EVENT_READ)
        while True:
            need(time.monotonic() < until and os.getppid() == original_parent, "gate expired or owner lost")
            if not selector.select(min(.02, max(0, until - time.monotonic()))):
                continue
            try:
                part = os.read(fd, 4097 - len(body))
            except BlockingIOError:
                continue
            if not part:
                break
            body.extend(part)
            need(len(body) <= 4096, "gate exceeds limit")
    need(1 <= len(body) <= 4096 and sha(body) == expected_sha, "complete matching gate and EOF required")
    return {"accepted": True, "bytes": len(body), "sha256": sha(body),
            "accepted_monotonic": time.monotonic(), "parent_pid": original_parent,
            "controller_pid": os.getpid(), "controller_group": os.getpgrp()}
