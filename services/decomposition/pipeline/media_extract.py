"""Media extraction: keyframes, audio WAV, ffprobe metadata."""

from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import structlog

from shared.config.settings import settings
from shared.utils import storage_sync

log = structlog.get_logger()


@dataclass
class MediaExtractionResult:
    keyframe_local_paths: list[Path]
    audio_local_path: Path | None
    has_audio: bool
    video_metadata: dict
    frame_object_keys: list[str]
    audio_object_key: str | None


def _run(cmd: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return p.returncode, p.stdout or "", p.stderr or ""


def ffprobe_dict(video_path: Path) -> dict:
    code, out, err = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
    )
    if code != 0:
        raise RuntimeError(err or out or "ffprobe failed")
    return json.loads(out)


def _duration_seconds(meta: dict) -> float:
    fmt = meta.get("format") or {}
    try:
        return float(fmt.get("duration") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _has_audio_stream(meta: dict) -> bool:
    for s in meta.get("streams") or []:
        if s.get("codec_type") == "audio":
            return True
    return False


def _pick_scene_timestamps(video_path: Path, duration: float, max_frames: int) -> list[float]:
    """Use ffmpeg showinfo on scene filter to collect timestamps (best-effort)."""
    vf = "select='gt(scene,0.32)',showinfo"
    _, _, err = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(video_path),
            "-vf",
            vf,
            "-f",
            "null",
            "-",
        ]
    )
    times: list[float] = []
    for line in err.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            try:
                t = float(m.group(1))
                if 0 <= t <= duration + 0.01:
                    times.append(t)
            except ValueError:
                continue
    seen: set[float] = set()
    uniq: list[float] = []
    for t in times:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:max_frames]


def _evenly_spaced(n: int, duration: float) -> list[float]:
    if n <= 0 or duration <= 0:
        return [0.0]
    if n == 1:
        return [min(0.5 * duration, max(duration - 0.05, 0.0))]
    return [duration * (i / (n - 1)) for i in range(n)]


def select_keyframe_timestamps(video_path: Path, duration: float) -> list[float]:
    max_kf = 20
    eff_dur = max(duration, 0.05)

    if duration > 300:
        times = _evenly_spaced(max_kf, eff_dur)[:max_kf]
    elif duration < 2:
        n = 2 if duration > 0.5 else 1
        times = _evenly_spaced(n, eff_dur)
    elif duration < 3:
        n = min(max_kf, max(1, int(math.ceil(duration))))
        times = [min(i * eff_dur / max(n - 1, 1), eff_dur - 1e-3) for i in range(n)]
    else:
        scene_times = _pick_scene_timestamps(video_path, eff_dur, max_kf)
        if len(scene_times) < 5:
            n = min(max_kf, max(5, int(math.ceil(eff_dur))))
            times = _evenly_spaced(n, eff_dur)[:max_kf]
        else:
            times = scene_times[:max_kf]

    out: list[float] = []
    for t in times:
        t = max(0.0, min(float(t), max(eff_dur - 1e-3, 0.0)))
        if not out or abs(t - out[-1]) > 1e-3:
            out.append(t)
    if not out:
        out = [0.0]
    return out[:max_kf]


def _extract_frame_at(video_path: Path, t: float, out_path: Path) -> None:
    code, _, err = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(t),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_path),
        ]
    )
    if code != 0 or not out_path.exists():
        raise RuntimeError(err or "frame extract failed")


def extract_media(
    ad_id: str,
    video_local_path: Path,
    work_dir: Path,
) -> MediaExtractionResult:
    meta = ffprobe_dict(video_local_path)
    duration = _duration_seconds(meta)
    has_audio = _has_audio_stream(meta)

    width = height = fps = bitrate = codec = None
    for s in meta.get("streams") or []:
        if s.get("codec_type") == "video":
            width = s.get("width")
            height = s.get("height")
            codec = s.get("codec_name")
            afr = s.get("avg_frame_rate")
            if afr and isinstance(afr, str) and "/" in afr:
                num, den = afr.split("/", 1)
                try:
                    if float(den) != 0:
                        fps = float(num) / float(den)
                except ValueError:
                    fps = None
            break
    try:
        br = int(meta.get("format", {}).get("bit_rate") or 0)
        bitrate = br if br > 0 else None
    except (TypeError, ValueError):
        bitrate = None

    timestamps = select_keyframe_timestamps(video_local_path, duration)
    frames_dir = work_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    key_paths: list[Path] = []
    frame_keys: list[str] = []
    bucket = settings.storage_bucket_extracted
    for i, ts in enumerate(timestamps, start=1):
        fname = f"frame_{i:03d}.jpg"
        local = frames_dir / fname
        _extract_frame_at(video_local_path, ts, local)
        key_paths.append(local)
        obj_key = f"{ad_id}/frames/{fname}"
        frame_keys.append(obj_key)
        data = local.read_bytes()
        storage_sync.upload_bytes(bucket, obj_key, data, "image/jpeg")

    audio_local: Path | None = None
    audio_key: str | None = None
    if has_audio:
        wav_path = work_dir / "audio" / "audio.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        code, _, err = _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(video_local_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(wav_path),
            ]
        )
        if code == 0 and wav_path.exists() and wav_path.stat().st_size > 44:
            audio_local = wav_path
            audio_key = f"{ad_id}/audio/audio.wav"
            storage_sync.upload_bytes(
                bucket, audio_key, wav_path.read_bytes(), "audio/wav"
            )
        else:
            has_audio = False
            log.warning("audio_extract_failed", stderr=err[:500])

    video_metadata = {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "codec": codec,
        "bitrate": bitrate,
        "resolution": f"{int(width)}x{int(height)}" if width and height else None,
    }

    return MediaExtractionResult(
        keyframe_local_paths=key_paths,
        audio_local_path=audio_local,
        has_audio=has_audio,
        video_metadata=video_metadata,
        frame_object_keys=frame_keys,
        audio_object_key=audio_key,
    )


def download_raw_video(gcs_video_path: str, dest: Path) -> None:
    bucket, key = storage_sync.parse_bucket_key(gcs_video_path)
    data = storage_sync.download_bytes(bucket, key)
    dest.write_bytes(data)
