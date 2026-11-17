class Refusal(ValueError):
    """A requested operation does not meet its declared contract."""

class SourceGap(Refusal):
    """A required original producer or scientific definition is not admitted."""

class DeadlineExceeded(Refusal):
    pass

