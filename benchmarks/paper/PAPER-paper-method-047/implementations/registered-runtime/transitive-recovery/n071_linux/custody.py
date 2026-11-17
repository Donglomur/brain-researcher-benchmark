"""Raw local failure and once-only acquisition custody; no receipt authority."""
from dataclasses import dataclass, field

class Refusal(RuntimeError):
    pass

def require(value, code):
    if not value:
        raise Refusal(code)

@dataclass(eq=False)
class Attempt:
    name: str
    parent: object = None
    first: BaseException | None = None
    occurrences: list = field(default_factory=list)
    unknown: list = field(default_factory=list)
    returned: list = field(default_factory=list)
    complete: bool = False
    retired: bool = False

    def fail(self, error, phase):
        # Do not invoke exception formatting, attributes, equality or add_note.
        if self.first is None:
            self.first = error
        self.occurrences.append((phase, error))
        if self.parent is not None:
            self.parent.fail(error, phase)

    def uncertain(self, phase, detail):
        self.unknown.append((phase, detail))
        if self.parent is not None:
            self.parent.uncertain(phase, detail)

    def raise_first(self):
        if self.first is not None:
            raise self.first

    def retain(self, error):
        self.fail(error, "independent-native-cleanup")

    def finish(self):
        require(not self.retired, "attempt-retired")
        self.raise_first()
        require(not self.unknown, "attempt-unknown")
        self.complete = True

class Owner:
    def __init__(self):
        # This local registry is not evidence of an external native interval.
        self.custody = Attempt("original-owner")
        self.attempts = []
        self.resources = []
        self.closed = False

    def begin(self, name, *, cleanup=False):
        require(type(name) is str and not self.closed, "owner-state")
        if not cleanup:
            self.custody.raise_first()
            require(not self.custody.unknown, "owner-unknown")
        attempt = Attempt(name, self.custody)
        self.attempts.append(attempt)
        return attempt

    def retain(self, resource):
        self.resources.append(resource)
        return resource

    def cleanup(self):
        # Each resource retires before a fallible physical close. Independent
        # remaining resources are still attempted after any earlier failure.
        ordered = sorted(enumerate(self.resources),
                         key=lambda row: (getattr(row[1], "cleanup_priority", 0), row[0]),
                         reverse=True)
        for _, resource in ordered:
            try:
                resource.close()
            except BaseException as error:
                self.custody.fail(error, "independent-cleanup")
        self.closed = True
        self.custody.raise_first()

    def projection(self):
        return {
            "failed": self.custody.first is not None,
            "failure_occurrences": [phase for phase, _ in self.custody.occurrences],
            "unknown": list(self.custody.unknown),
            "resources": len(self.resources),
            "closed": self.closed,
            "native_qualification": False,
        }

