"""Visual feature extraction from keyframe images (OpenCV)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _dominant_colors_kmeans(bgr: np.ndarray, k: int = 5) -> list[str]:
    pixels = bgr.reshape(-1, 3).astype(np.float32)
    if len(pixels) < k:
        k = max(1, len(pixels))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.2)
    _, labels, centers = cv2.kmeans(
        pixels,
        k,
        None,
        criteria,
        3,
        cv2.KMEANS_PP_CENTERS,
    )
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)
    hexes: list[str] = []
    for idx in order[:5]:
        b, g, r = centers[idx]
        hexes.append(f"#{int(r):02x}{int(g):02x}{int(b):02x}")
    while len(hexes) < 5:
        hexes.append(hexes[-1] if hexes else "#000000")
    return hexes[:5]


def _warmth_saturation(hsv: np.ndarray) -> tuple[float, float]:
    h = hsv[:, :, 0].astype(np.float32) * 2.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    warm = ((h <= 60) | (h >= 300)).astype(np.float32)
    cool = ((h >= 120) & (h <= 260)).astype(np.float32)
    warm_ratio = float(np.mean(warm))
    cool_ratio = float(np.mean(cool) + 1e-6)
    warmth = float(max(0.0, min(1.0, warm_ratio / (warm_ratio + cool_ratio))))
    saturation = float(np.clip(np.mean(s), 0.0, 1.0))
    return warmth, saturation


def _text_density_simple(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 60, 180)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return 0.0
    areas = sorted([cv2.contourArea(c) for c in cnts], reverse=True)[:5]
    h, w = gray.shape
    cover = sum(a for a in areas if a > (h * w) * 0.002)
    return float(np.clip(cover / (h * w + 1e-6), 0.0, 1.0))


def analyze_visuals(
    keyframe_paths: list[Path],
    duration_seconds: float,
) -> dict:
    if not keyframe_paths:
        return {
            "color_palette": ["#000000"] * 5,
            "color_warmth": 0.5,
            "color_saturation": 0.0,
            "scene_count": 0,
            "avg_scene_duration": 0.0,
            "motion_intensity": 0.0,
            "text_density": 0.0,
            "face_present_ratio": 0.0,
            "face_first_appearance_keyframe_index": None,
            "face_first_appearance_seconds": None,
        }

    cascade_path = str(
        Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    )
    face_cascade = cv2.CascadeClassifier(cascade_path)

    palettes: list[list[str]] = []
    warmths: list[float] = []
    sats: list[float] = []
    text_scores: list[float] = []
    face_per_frame: list[bool] = []
    prev_gray: np.ndarray | None = None
    flow_mags: list[float] = []

    for p in keyframe_paths:
        bgr = cv2.imread(str(p))
        if bgr is None:
            continue
        small = cv2.resize(bgr, (320, int(bgr.shape[0] * 320 / max(bgr.shape[1], 1))))
        palettes.append(_dominant_colors_kmeans(small))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        w, s = _warmth_saturation(hsv)
        warmths.append(w)
        sats.append(s)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        text_scores.append(_text_density_simple(gray))
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
        face_per_frame.append(len(faces) > 0)
        if prev_gray is not None and prev_gray.shape == gray.shape:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            flow_mags.append(float(np.mean(mag)))
        prev_gray = gray

    if not palettes:
        return analyze_visuals([], duration_seconds)

    pal_arr = np.array(
        [np.array([int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)]) for h in palettes[0]],
        dtype=np.float32,
    )
    for rest in palettes[1:]:
        pal_arr += np.array(
            [np.array([int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)]) for h in rest],
            dtype=np.float32,
        )
    pal_arr /= len(palettes)
    color_palette = [f"#{int(r):02x}{int(g):02x}{int(b):02x}" for b, g, r in pal_arr]

    scene_count = len(keyframe_paths)
    avg_scene_duration = (
        float(duration_seconds / max(scene_count, 1)) if duration_seconds else 0.0
    )
    motion_intensity = float(np.clip((np.mean(flow_mags) if flow_mags else 0.0) / 10.0, 0.0, 1.0))
    text_density = float(np.mean(text_scores)) if text_scores else 0.0
    face_present_ratio = (
        sum(1 for x in face_per_frame if x) / max(len(face_per_frame), 1)
    )
    face_idx = next((i for i, v in enumerate(face_per_frame) if v), None)
    face_ts = None
    if face_idx is not None and duration_seconds and scene_count:
        face_ts = float(duration_seconds * (face_idx / max(scene_count - 1, 1)))

    return {
        "color_palette": color_palette,
        "color_warmth": float(np.mean(warmths)) if warmths else 0.5,
        "color_saturation": float(np.mean(sats)) if sats else 0.0,
        "scene_count": int(scene_count),
        "avg_scene_duration": float(avg_scene_duration),
        "motion_intensity": float(motion_intensity),
        "text_density": float(text_density),
        "face_present_ratio": float(face_present_ratio),
        "face_first_appearance_keyframe_index": int(face_idx) if face_idx is not None else None,
        "face_first_appearance_seconds": face_ts,
    }
