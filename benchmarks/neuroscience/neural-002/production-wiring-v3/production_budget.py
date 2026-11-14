"""Prospective logical reservations; not a kernel or scientific admission."""
import math
import time


class Budget:
    def __init__(self, read_bytes, write_bytes, seconds):
        if any(type(x) is not int or x <= 0 for x in (read_bytes, write_bytes)):
            raise ValueError("positive explicit byte reservations required")
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("positive explicit original deadline required")
        self.read_limit, self.write_limit = read_bytes, write_bytes
        self.read_reserved = self.write_reserved = 0
        self.end = time.monotonic() + seconds

    def check(self):
        if time.monotonic() >= self.end:
            raise TimeoutError("original production metadata deadline expired")

    def read(self, amount):
        self.check()
        if type(amount) is not int or amount < 0 or self.read_reserved + amount > self.read_limit:
            raise ValueError("prospective read reservation exhausted")
        self.read_reserved += amount

    def write(self, amount):
        self.check()
        if type(amount) is not int or amount < 0 or self.write_reserved + amount > self.write_limit:
            raise ValueError("prospective write reservation exhausted")
        self.write_reserved += amount

    def snapshot(self):
        return {"read_reserved": self.read_reserved, "write_reserved": self.write_reserved,
                "read_limit": self.read_limit, "write_limit": self.write_limit,
                "physical_or_kernel_io_measured": False,
                "hard_whole_process_deadline_enforced_here": False}
