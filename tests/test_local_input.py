import numpy as np
import pytest

from eidos.modules.voice.local_input import (
    CaptureGate, InputOptions, LinearResampler, LocalAudioInput, SileroProbability)


def frame(value=0):
    return np.full(512, value, dtype=np.float32)


def test_wake_preserves_preroll_and_ends_on_silero_pause():
    gate = CaptureGate(InputOptions(pre_roll_seconds=.512, silence_seconds=.096))
    for i in range(25):
        gate.feed(frame(i), 0, None, False)
    gate.feed(frame(25), .9, 'Эйла', False)
    gate.feed(frame(26), .9, None, False)
    assert gate.feed(frame(), 0, None, False) is None
    assert gate.feed(frame(), 0, None, False) is None
    audio, source = gate.feed(frame(), 0, None, False)
    assert source == 'Эйла'
    assert audio[0] == 9  # sixteen frames before the trigger, not including it
    assert 25 in audio and 26 in audio


def test_ptt_waits_for_release_despite_silence():
    gate = CaptureGate(InputOptions(silence_seconds=.064))
    gate.feed(frame(1), .9, None, True)
    for _ in range(10):
        assert gate.feed(frame(), 0, None, True) is None
    audio, source = gate.release()
    assert source == 'ptt' and len(audio) == 11 * 512
    assert gate.release() is None


def test_silent_ptt_is_not_submitted():
    gate = CaptureGate(InputOptions())
    gate.feed(frame(), 0, None, True)
    assert gate.release() is None


def test_ptt_at_maximum_requires_release_before_next_recording():
    gate = CaptureGate(InputOptions(max_seconds=.064))
    gate.feed(frame(1), .9, None, True)
    assert gate.feed(frame(2), .9, None, True) is not None
    assert gate.feed(frame(3), .9, None, True) is None
    gate.feed(frame(), 0, None, False)
    gate.feed(frame(4), .9, None, True)
    audio, _ = gate.release()
    assert 4 in audio


def test_reset_discards_partial_command_and_preroll():
    gate = CaptureGate(InputOptions())
    gate.feed(frame(1), .9, 'Эйдос', False)
    gate.reset()
    assert gate.release() is None
    gate.feed(frame(2), .9, None, True)
    audio, _ = gate.release()
    assert 1 not in audio


def test_wake_without_command_times_out():
    gate = CaptureGate(InputOptions(onset_seconds=.064))
    gate.feed(frame(), 0, 'Эйдос', False)
    assert gate.feed(frame(), 0, None, False) is None
    assert gate.feed(frame(), 0, None, False) is None
    assert gate.source is None


def test_resampling_is_independent_of_input_chunk_boundaries():
    audio = np.sin(np.arange(44100) / 10).astype(np.float32)
    whole = LinearResampler(44100).feed(audio)
    streaming = LinearResampler(44100)
    pieces = [streaming.feed(a) for a in np.array_split(audio, 137)]
    np.testing.assert_allclose(np.concatenate(pieces), whole, atol=1e-6)
    assert abs(len(whole) - 16000) <= 1


def test_options_reject_invalid_limits():
    with pytest.raises(ValueError):
        InputOptions(pre_roll_seconds=-1)


def test_silero_real_cpu_model_preserves_and_resets_state():
    vad = SileroProbability()
    first = vad(frame())
    assert 0 <= first <= 1
    vad(frame())
    vad.reset()
    assert vad(frame()) == pytest.approx(first)


def test_submit_blocks_duplicates_and_mute_invalidates_queued_result():
    audio_input = LocalAudioInput()
    received = []
    audio_input.audio_ready.connect(lambda audio, ident, source: received.append(ident))
    audio_input._submit((frame(), 'ptt'))
    audio_input._submit((frame(), 'ptt'))
    assert len(received) == 1 and audio_input.is_current(received[0])
    audio_input.set_enabled(False)
    assert not audio_input.is_current(received[0])


def test_audio_overflow_closes_device_without_submitting_partial_command():
    from types import SimpleNamespace
    closed = []
    received = []

    class Stream:
        active = True

        def __init__(self, **kwargs):
            self.callback = kwargs['callback']

        def start(self):
            # Overflow at the producer, without opening a real microphone.
            for _ in range(9):
                self.callback(frame(1)[:, None], 512, None, False)

        def abort(self):
            closed.append('abort')

        def close(self):
            closed.append('close')

    sd = SimpleNamespace(query_devices=lambda **kw: {'default_samplerate': 16000},
                         check_input_settings=lambda **kw: None, InputStream=Stream)
    vad = SimpleNamespace(reset=lambda: None)
    audio_input = LocalAudioInput()
    audio_input.audio_ready.connect(lambda *args: received.append(args))
    with pytest.raises(OSError, match='Потеря аудиоданных'):
        audio_input._capture(sd, vad, None, CaptureGate(InputOptions()))
    assert closed == ['abort', 'close']
    assert received == []
