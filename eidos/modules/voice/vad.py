"""Silero v6.2 ONNX, CPU only. Model initialization precedes capture."""
from pathlib import Path


class SileroVAD:
    FRAME_SAMPLES = 512

    def __init__(self):
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.inter_op_num_threads = options.intra_op_num_threads = 1
        path = Path(__file__).resolve().parents[2] / 'assets' / 'models' / 'silero_vad.onnx'
        self.session = ort.InferenceSession(str(path), sess_options=options,
                                           providers=['CPUExecutionProvider'])
        self.reset()

    def reset(self):
        import numpy as np
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)

    def __call__(self, pcm: bytes) -> float:
        import numpy as np
        if len(pcm) != 1024:
            raise ValueError('Silero ожидает 512 отсчётов PCM16 / 16 кГц.')
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32).reshape(1, -1) / 32768.
        audio = np.concatenate((self.context, samples), axis=1)
        output, self.state = self.session.run(None, {'input': audio, 'state': self.state,
                                                     'sr': np.array(16000, dtype=np.int64)})
        self.context = samples[:, -64:].copy()
        return float(output[0, 0])
