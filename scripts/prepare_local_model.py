"""Explicit setup, separate from normal app startup. No microphone access."""
import argparse
from pathlib import Path
import time
from eidos.agent.providers import start_ollama, pull_model
from eidos.agent.settings import AgentSettings
from eidos.agent.harness import TaskContext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='qwen3:4b-instruct-2507-q4_K_M')
    args = parser.parse_args()
    print(start_ollama(Path(__file__).resolve().parents[1]), flush=True)
    last = [0.0]
    def progress(state, text):
        if time.monotonic()-last[0] > 5 or 'success' in text:
            print(text, flush=True)
            last[0] = time.monotonic()
    settings = AgentSettings(model=args.model)
    context = TaskContext(timeout=5400, progress=progress)
    print(pull_model(settings, context), flush=True)


if __name__ == '__main__':
    main()
