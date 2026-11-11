"""Single owner for each acquired resource; preserve original and cleanup separately."""
class Attempt:
    def __init__(self):
        self.first = None
        self.secondary = []
        self.resources = []
        self.events = []

    def fail(self, error, phase):
        row = (phase, error)
        if self.first is None:
            self.first = row
        else:
            self.secondary.append(row)

    def own(self, resource, close):
        # Acquire ownership before any validation, observation or dependent effect.
        row = [resource, close, False]
        self.resources.append(row)
        return resource

    def retire(self):
        for row in reversed(self.resources):
            if row[2]:
                continue
            row[2] = True
            try:
                row[1]()
            except BaseException as error:
                self.fail(error, 'cleanup')

    def run(self, operation):
        value = None
        try:
            value = operation(self)
        except BaseException as error:
            self.fail(error, 'body')
        finally:
            self.retire()
        if self.first is not None:
            raise self.first[1]
        return value

    def summary(self):
        # No exception formatting hook can displace the retained raw failures.
        return {'completed': self.first is None,
                'first_phase': self.first[0] if self.first else None,
                'secondary_phases': [x[0] for x in self.secondary],
                'resources': len(self.resources),
                'retirements': sum(row[2] for row in self.resources)}
