"""Create an original, royalty-free football-stadium background loop as WAV."""

from __future__ import annotations

import math
import random
import wave
from array import array
from pathlib import Path


SAMPLE_RATE = 22_050
DURATION_SECONDS = 16
BPM = 120


def _frequency(midi_note: int) -> float:
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def _add_tone(samples: list[float], start: float, duration: float, notes: list[int], gain: float) -> None:
    start_index = int(start * SAMPLE_RATE)
    length = min(int(duration * SAMPLE_RATE), len(samples) - start_index)
    for index in range(length):
        elapsed = index / SAMPLE_RATE
        envelope = min(elapsed / 0.05, 1.0) * min((duration - elapsed) / 0.28, 1.0)
        value = sum(math.sin(2 * math.pi * _frequency(note) * elapsed) for note in notes) / len(notes)
        samples[start_index + index] += value * gain * max(envelope, 0)


def _add_kick(samples: list[float], start: float) -> None:
    start_index = int(start * SAMPLE_RATE)
    length = min(int(0.22 * SAMPLE_RATE), len(samples) - start_index)
    for index in range(length):
        elapsed = index / SAMPLE_RATE
        envelope = math.exp(-17 * elapsed)
        frequency = 105 - 65 * min(elapsed / 0.22, 1.0)
        samples[start_index + index] += math.sin(2 * math.pi * frequency * elapsed) * 0.62 * envelope


def _add_snare(samples: list[float], start: float, rng: random.Random) -> None:
    start_index = int(start * SAMPLE_RATE)
    length = min(int(0.15 * SAMPLE_RATE), len(samples) - start_index)
    for index in range(length):
        elapsed = index / SAMPLE_RATE
        samples[start_index + index] += rng.uniform(-1, 1) * 0.16 * math.exp(-25 * elapsed)


def _add_hat(samples: list[float], start: float, rng: random.Random) -> None:
    start_index = int(start * SAMPLE_RATE)
    length = min(int(0.05 * SAMPLE_RATE), len(samples) - start_index)
    for index in range(length):
        elapsed = index / SAMPLE_RATE
        samples[start_index + index] += rng.uniform(-1, 1) * 0.045 * math.exp(-55 * elapsed)


def build_loop() -> list[float]:
    samples = [0.0] * (SAMPLE_RATE * DURATION_SECONDS)
    rng = random.Random(20261023)
    beat_seconds = 60 / BPM
    # Original minor-chord pulse and percussion; it intentionally contains no
    # melody or motif from any football league broadcast.
    chords = [[45, 52, 57], [41, 48, 52], [43, 50, 55], [40, 47, 52]]
    for beat in range(int(DURATION_SECONDS / beat_seconds)):
        start = beat * beat_seconds
        if beat % 2 == 0:
            _add_tone(samples, start, beat_seconds * 1.8, chords[(beat // 4) % len(chords)], 0.11)
        _add_kick(samples, start)
        _add_hat(samples, start + beat_seconds * 0.5, rng)
        if beat % 4 in {1, 3}:
            _add_snare(samples, start, rng)
    return samples


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "assets" / "epl_stadium_loop.wav"
    output.parent.mkdir(parents=True, exist_ok=True)
    pcm = array("h", (int(max(-1.0, min(1.0, sample)) * 32767) for sample in build_loop()))
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    print(f"Created {output} ({DURATION_SECONDS}s, {SAMPLE_RATE}Hz).")


if __name__ == "__main__":
    main()
