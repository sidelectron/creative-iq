"""Audio feature extraction (librosa)."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np


def analyze_audio(wav_path: Path | None, has_audio: bool) -> dict:
    if not has_audio or wav_path is None or not wav_path.exists():
        return {
            "has_music": False,
            "has_voiceover": False,
            "audio_energy_mean": 0.0,
            "silence_ratio": 0.0,
            "tempo_bpm": None,
        }

    y, sr = librosa.load(str(wav_path), sr=None, mono=True)
    if y.size == 0:
        return {
            "has_music": False,
            "has_voiceover": False,
            "audio_energy_mean": 0.0,
            "silence_ratio": 1.0,
            "tempo_bpm": None,
        }

    rms = librosa.feature.rms(y=y)[0]
    energy_mean = float(np.clip(np.mean(rms) * 5.0, 0.0, 1.0))

    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y=y)))
    contrast = float(np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)))

    has_music = contrast > 15 and energy_mean > 0.05
    has_voiceover = zcr > 0.08 and energy_mean > 0.02

    frame_length = 2048
    hop = 512
    rms_frames = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop)[0]
    db = librosa.amplitude_to_db(rms_frames + 1e-9, ref=np.max)
    silence_ratio = float(np.mean(db < -40))

    tempo_val = None
    if has_music:
        onset = librosa.onset.onset_strength(y=y, sr=sr)
        try:
            tempo_fn = librosa.feature.rhythm.tempo
        except AttributeError:  # pragma: no cover
            tempo_fn = librosa.feature.tempo  # type: ignore[attr-defined]
        tempo_arr = tempo_fn(onset_envelope=onset, sr=sr)
        if tempo_arr is not None and len(tempo_arr):
            tempo_val = int(round(float(tempo_arr[0])))

    if not has_music and has_voiceover:
        tempo_val = None

    return {
        "has_music": bool(has_music),
        "has_voiceover": bool(has_voiceover),
        "audio_energy_mean": energy_mean,
        "silence_ratio": float(np.clip(silence_ratio, 0.0, 1.0)),
        "tempo_bpm": tempo_val,
    }
