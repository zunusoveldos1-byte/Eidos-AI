import logging
from dataclasses import replace
from types import SimpleNamespace

import pytest

from eidos.core.metrics import LATENCY_TRACE, VoiceLatency, report_llm_latency
from eidos.core.config import AppConfig
from eidos.modules.voice.worker import VoiceWorker


def test_latency_logs_compact_pair_and_warns_only_above_threshold(caplog):
    trace = VoiceLatency()
    with caplog.at_level(logging.INFO, logger='eidos.voice.latency'):
        trace.observe('stt', 38)
        trace.observe('llm', 140)
        trace.observe('llm', 500)
        trace.observe('llm', 501)
    assert caplog.records[1].message == 'STT: 38ms | LLM: 140ms'
    assert caplog.records[2].levelno == logging.INFO
    assert caplog.records[3].levelno == logging.WARNING
    assert 'slow LLM' in caplog.records[3].message


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf')])
def test_invalid_timings_are_ignored(value, caplog):
    trace = VoiceLatency()
    trace.observe('stt', value)
    assert trace.stt_ms is None and not caplog.records


def test_worker_measures_from_speech_end_and_shares_turn_with_llm(monkeypatch, caplog, tmp_path):
    import eidos.modules.voice.worker as module
    recorder = SimpleNamespace(speech_ended_at=10,
        record=lambda *args: object())
    stt = SimpleNamespace(transcribe=lambda *args: 'private spoken text')
    worker = VoiceWorker(recorder=recorder, stt=stt)
    def handle(text):
        report_llm_latency(140)
        return 'private model answer'
    worker.commands = SimpleNamespace(handle=handle)
    monkeypatch.setattr(module, 'perf_counter', lambda: 10.038)
    previous = LATENCY_TRACE.get()
    with caplog.at_level(logging.INFO, logger='eidos.voice.latency'):
        worker._run(replace(AppConfig(), speak=False), tmp_path)
    assert 'STT: 38ms | LLM: 140ms' in caplog.text
    assert 'private' not in caplog.text
    assert LATENCY_TRACE.get() is previous


def test_new_turn_does_not_reuse_previous_stt(caplog):
    first = LATENCY_TRACE.set(VoiceLatency())
    try:
        LATENCY_TRACE.get().observe('stt', 38)
        second = LATENCY_TRACE.set(VoiceLatency())
        try:
            with caplog.at_level(logging.INFO, logger='eidos.voice.latency'):
                report_llm_latency(120)
            assert caplog.records[-1].message == 'STT: — | LLM: 120ms'
        finally:
            LATENCY_TRACE.reset(second)
    finally:
        LATENCY_TRACE.reset(first)
