"""Concrete fresh analysis sandbox; feedback is candidate-influenced, not independent evidence."""
import contextlib
import io
from core import need, capture, publish, encoded, parse
from worker_common import start, seed_numpy, view, finish, failure


class BoundedText(io.TextIOBase):
    def __init__(self, cap): self.cap = cap; self.count = 0; self.parts = []
    def write(self, text):
        raw = text.encode('utf-8'); need(self.count + len(raw) <= self.cap, 'bounded analysis feedback')
        self.count += len(raw); self.parts.append(text); return len(text)
    def getvalue(self): return ''.join(self.parts)


def run(config):
    request, budget, limits, output = start(config)
    try:
        seed_numpy(request['seed'])
        batch = None if request['source_only'] else view(request, limits)
        need(not request['source_only'] or request.get('view') is None, 'source-only global author receives no study packet')
        raw, _ = capture(request['code']['path'], request['code']['pin'], request['code_cap'], budget, readonly=True)
        text = BoundedText(request['feedback_bytes']); namespace = {'__name__': 'analysis', 'batch': batch,
                  'rng_seed': request['seed'], 'source_only': request['source_only']}
        with contextlib.redirect_stdout(text), contextlib.redirect_stderr(text):
            exec(compile(raw, '<captured analysis>', 'exec', dont_inherit=True), namespace)
        budget.tick()
        report = {'schema': 'neural049_analysis_feedback_v1', 'text': text.getvalue(),
                  'candidate_influenced': True, 'independent_usage_proof': False}
        desc = publish(output/'FEEDBACK.json', encoded(report), budget, readonly=True)
        return finish(output, request, budget, limits, {'FEEDBACK.json': desc})
    except BaseException as error:
        failure(output, error, budget, limits); raise
