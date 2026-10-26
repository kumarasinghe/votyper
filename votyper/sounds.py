"""Start/stop dings, synthesized so no sound files are needed."""


def play_tones(*freqs: float) -> None:
    """Play short bell notes one after another; blocks until done."""
    try:
        import numpy as np
        import sounddevice as sd  # installed with moonshine-voice
        rate, secs = 44100, 0.12
        t = np.arange(int(rate * secs)) / rate
        notes = [(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t))
                 * np.exp(-t * 22) * 0.3 for f in freqs]
        sd.play(np.concatenate(notes).astype(np.float32), rate)
        sd.wait()
    except Exception:
        pass  # a missing speaker must never stop dictation


def play_start() -> None:
    play_tones(988)              # one high note


def play_stop() -> None:
    play_tones(784, 523)         # two falling notes
