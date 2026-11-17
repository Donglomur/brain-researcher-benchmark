"""Additive explicit candidate-failure closure, preserving the original state API."""
from .plan import ContextState
from .custody import CustodyError,digest,require_digest

class ContextStateV2(ContextState):
    def candidate_failure(self, prediction_digest, reason, original_outcome_digest):
        """Preserve required cases even if the candidate fails before query opens.

        Infrastructure/admission/reference/provider-metering failures do not use
        this method: those invalidate qualification and cannot become low scores.
        """
        if self.state not in ('prepared','authoring','sealed','query_open'):
            raise CustodyError('candidate failure cannot replace unknown/closed execution')
        if not isinstance(reason,str) or not reason:
            raise CustodyError('explicit candidate failure required')
        require_digest(prediction_digest);require_digest(original_outcome_digest)
        previous=self.state
        self.prediction_digest=prediction_digest;self.failure=reason;self.state='submitted'
        self._event('candidate_failure',digest({'previous':previous,'prediction':prediction_digest,
                    'reason':reason,'original_outcome':original_outcome_digest}))
