from pathlib import Path
import wave


def test_original_stadium_loop_is_a_playable_wav_asset() -> None:
    path = Path(__file__).resolve().parents[1] / "assets" / "epl_stadium_loop.wav"
    assert path.exists()
    with wave.open(str(path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 22_050
        assert audio.getnframes() / audio.getframerate() == 16
