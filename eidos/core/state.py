"""Voice lifecycle transitions."""

from enum import Enum


class State(str, Enum):
    IDLE = 'idle'
    STARTING = 'starting'
    RECORDING = 'recording'
    LOADING = 'loading'
    TRANSCRIBING = 'transcribing'
    SYNTHESIZING = 'synthesizing'
    PLAYING = 'playing'
    ERROR = 'error'
    CLOSING = 'closing'


class StateMachine:
    NEXT = {
        State.IDLE: {State.STARTING},
        State.STARTING: {State.RECORDING},
        State.RECORDING: {State.LOADING, State.TRANSCRIBING},
        State.LOADING: {State.TRANSCRIBING},
        State.TRANSCRIBING: {State.SYNTHESIZING},
        State.SYNTHESIZING: {State.PLAYING},
        State.PLAYING: set(),
        State.ERROR: set(),
        State.CLOSING: set(),
    }

    def __init__(self) -> None:
        self.state = State.IDLE

    def transition(self, target: State) -> None:
        allowed = self.NEXT[self.state] | {State.ERROR, State.IDLE, State.CLOSING}
        if self.state == State.CLOSING or target == self.state or target not in allowed:
            raise ValueError(f'Недопустимый переход {self.state.value} → {target.value}')
        self.state = target
