"""Bounded, content-free timing samples. No transcripts or credentials."""
from collections import defaultdict, deque
from contextlib import contextmanager
from threading import Lock
from time import perf_counter
import math
import logging
from contextvars import ContextVar


STAGES = ('wake_detection', 'audio_buffering', 'model_load', 'stt', 'stt_response',
          'command_routing', 'llm_first_token', 'tts')


class StageMetrics:
    def __init__(self, capacity=256):
        self._samples = defaultdict(lambda: deque(maxlen=capacity))
        self._lock = Lock()

    def observe(self, stage, milliseconds, *, cold=False):
        if not math.isfinite(milliseconds) or milliseconds < 0:
            return
        with self._lock:
            self._samples[stage, 'cold' if cold else 'warm'].append(float(milliseconds))

    @contextmanager
    def measure(self, stage, *, cold=False):
        started = perf_counter()
        try:
            yield
        finally:
            self.observe(stage, (perf_counter() - started) * 1000, cold=cold)

    def snapshot(self):
        def percentile(values, fraction):
            position = (len(values) - 1) * fraction
            low = int(position)
            return round(values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low), 3)
        result = {stage: {} for stage in STAGES}
        with self._lock:
            samples = {key: sorted(values) for key, values in self._samples.items()}
        for (stage, mode), values in samples.items():
            result.setdefault(stage, {})[mode] = dict(count=len(values), p50_ms=percentile(values, .5),
                p95_ms=percentile(values, .95), min_ms=round(values[0], 3), max_ms=round(values[-1], 3))
        return result


METRICS = StageMetrics()


LATENCY_TRACE = ContextVar('voice_latency_trace', default=None)
_latency_logger = logging.getLogger('eidos.voice.latency')


class VoiceLatency:
    """One turn's live timings; isolated across worker/async contexts."""
    SLOW_MS = 500

    def __init__(self):
        self.stt_ms = self.llm_ms = None

    def observe(self, stage, milliseconds):
        if not math.isfinite(milliseconds) or milliseconds < 0:
            return
        setattr(self, stage + '_ms', milliseconds)
        def display(value):
            return '—' if value is None else f'{value:.0f}ms'
        message = f'STT: {display(self.stt_ms)} | LLM: {display(self.llm_ms)}'
        if milliseconds > self.SLOW_MS:
            _latency_logger.warning('%s | slow %s (>500ms)', message, stage.upper())
        else:
            _latency_logger.info('%s', message)


def report_llm_latency(milliseconds):
    trace = LATENCY_TRACE.get()
    (trace if trace is not None else VoiceLatency()).observe('llm', milliseconds)
