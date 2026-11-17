"""Owned semantic failures and first/secondary-error custody."""
class Refusal(Exception):
    def __init__(self, code):
        if type(code) is not str:
            raise TypeError("owned reason must be text")
        self.code = code
        super().__init__(code)

def need(condition, code):
    if not condition:
        raise Refusal(code)

class Custody:
    def __init__(self):
        self.first = None
        self.secondary = []

    def retain(self, exc, phase):
        # Do not invoke arbitrary exception __str__, attributes or iteration.
        record = (phase, exc)
        if self.first is None:
            self.first = record
        else:
            self.secondary.append(record)

    def close(self, resource, close, phase):
        try:
            close(resource)
        except BaseException as exc:
            self.retain(exc, phase)

    def raise_first(self):
        if self.first is not None:
            raise self.first[1]

    def diagnostic(self):
        # Diagnostics are independent of the original retained exception objects.
        return {"first_phase": None if self.first is None else self.first[0],
                "secondary_phases": [r[0] for r in self.secondary]}
