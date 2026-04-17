"""Decomposition orchestrator: stages 4–9, persistence, Redis event."""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.config.settings import settings
from shared.utils.gemini import GeminiPermanentError, GeminiTransientError
from shared.models.db import Ad, CreativeFingerprint
from shared.models.enums import AdStatus
from shared.utils import redis_sync
from services.decomposition import metrics as prom
from services.chat.auto_events_service import detect_single_ad_outlier, detect_style_novelty_for_ad
from services.decomposition.pipeline import audio, gemini_creative, media_extract, transcribe, visual
from services.decomposition.pipeline.fingerprint_merge import merge_attributes

log = structlog.get_logger()


class PermanentPipelineError(Exception):
    """Unrecoverable pipeline failure (no Celery retry)."""


def run_decomposition(session: Session, ad_id: uuid.UUID, celery_task_id: str) -> None:
    t0 = time.perf_counter()
    timings: dict[str, float] = {}

    ad = session.get(Ad, ad_id)
    if ad is None or ad.deleted_at is not None:
        return

    work_root = Path("/tmp") / f"creativeiq_decompose_{ad_id}"
    if work_root.exists():
        shutil.rmtree(work_root, ignore_errors=True)
    work_root.mkdir(parents=True, exist_ok=True)
    video_path = work_root / "source_video"

    try:
        if not ad.gcs_video_path:
            raise PermanentPipelineError("Ad has no video path")

        t_dl = time.perf_counter()
        media_extract.download_raw_video(ad.gcs_video_path, video_path)
        timings["download"] = time.perf_counter() - t_dl

        t_me = time.perf_counter()
        try:
            media = media_extract.extract_media(str(ad_id), video_path, work_root)
        except Exception as e:  # noqa: BLE001
            raise PermanentPipelineError(
                "Video file is corrupted or in an unsupported format"
            ) from e
        timings["media_extraction"] = time.perf_counter() - t_me
        prom.DECOMPOSITION_STAGE_DURATION_SECONDS.labels(stage_name="media_extraction").observe(
            timings["media_extraction"]
        )

        duration = float(media.video_metadata.get("duration_seconds") or 0.0)

        t_vis = time.perf_counter()
        vis = visual.analyze_visuals(media.keyframe_local_paths, duration)
        timings["visual_analysis"] = time.perf_counter() - t_vis
        prom.DECOMPOSITION_STAGE_DURATION_SECONDS.labels(stage_name="visual_analysis").observe(
            timings["visual_analysis"]
        )

        if media.has_audio and media.audio_local_path:
            t_au = time.perf_counter()
            aud = audio.analyze_audio(media.audio_local_path, True)
            timings["audio_analysis"] = time.perf_counter() - t_au
        else:
            aud = audio.analyze_audio(None, False)
            timings["audio_analysis"] = 0.0
        prom.DECOMPOSITION_STAGE_DURATION_SECONDS.labels(stage_name="audio_analysis").observe(
            timings["audio_analysis"]
        )

        if media.has_audio and media.audio_local_path:
            t_tr = time.perf_counter()
            tr = transcribe.transcribe(media.audio_local_path, True)
            timings["transcription"] = time.perf_counter() - t_tr
        else:
            tr = transcribe.transcribe(None, False)
            timings["transcription"] = 0.0
        prom.DECOMPOSITION_STAGE_DURATION_SECONDS.labels(stage_name="transcription").observe(
            timings["transcription"]
        )

        low_level_summary = {
            "visual": vis,
            "audio": aud,
            "transcript_excerpt": (tr.get("transcript") or "")[:500],
            "has_audio": media.has_audio,
        }

        t_g = time.perf_counter()
        try:
            gemini_dict, tin, tout, g_warnings = gemini_creative.run_creative_analysis(
                keyframe_paths=media.keyframe_local_paths,
                transcript=str(tr.get("transcript") or ""),
                low_level_summary=low_level_summary,
                duration_seconds=duration,
                platform=str(ad.platform),
            )
        except (GeminiTransientError, GeminiPermanentError) as e:
            raise PermanentPipelineError(str(e)) from e
        timings["gemini_analysis"] = time.perf_counter() - t_g
        prom.DECOMPOSITION_STAGE_DURATION_SECONDS.labels(stage_name="gemini_analysis").observe(
            timings["gemini_analysis"]
        )

        attrs = merge_attributes(
            video_meta=media.video_metadata,
            visual=vis,
            audio_feats=aud,
            transcript=tr,
            gemini=gemini_dict,
        )
        low_level_features = {**vis, **aud}

        meta = dict(ad.ad_metadata or {})
        for w in g_warnings:
            meta.setdefault("warnings", [])
            if isinstance(meta["warnings"], list):
                meta["warnings"].append(w)
        if g_warnings:
            meta["decomposition_warning"] = ";".join(g_warnings)

        fp = session.scalar(
            select(CreativeFingerprint).where(CreativeFingerprint.ad_id == ad_id)
        )
        total_time = time.perf_counter() - t0
        if fp is None:
            fp = CreativeFingerprint(
                ad_id=ad_id,
                attributes=attrs,
                low_level_features=low_level_features,
                gemini_analysis=gemini_dict,
                transcript=str(tr.get("transcript") or ""),
                gemini_model_used=settings.gemini_model_pro,
                gemini_tokens_input=tin,
                gemini_tokens_output=tout,
                processing_duration_seconds=float(total_time),
            )
            session.add(fp)
        else:
            fp.attributes = attrs
            fp.low_level_features = low_level_features
            fp.gemini_analysis = gemini_dict
            fp.transcript = str(tr.get("transcript") or "")
            fp.gemini_model_used = settings.gemini_model_pro
            fp.gemini_tokens_input = tin
            fp.gemini_tokens_output = tout
            fp.processing_duration_seconds = float(total_time)

        ad.status = AdStatus.DECOMPOSED.value
        ad.ad_metadata = meta
        session.add(ad)
        session.commit()
        detect_style_novelty_for_ad(session, ad_id=ad_id)
        detect_single_ad_outlier(session, ad_id=ad_id)

        redis_sync.publish_event_sync({"event": "ad.decomposed", "ad_id": str(ad_id)})

        prom.ADS_DECOMPOSED_TOTAL.labels(platform=str(ad.platform)).inc()
        prom.DECOMPOSITION_DURATION_SECONDS.observe(total_time)

        log.info(
            "decomposition_complete",
            ad_id=str(ad_id),
            media_extraction=round(timings.get("media_extraction", 0), 2),
            visual_analysis=round(timings.get("visual_analysis", 0), 2),
            audio_analysis=round(timings.get("audio_analysis", 0), 2),
            transcription=round(timings.get("transcription", 0), 2),
            gemini_analysis=round(timings.get("gemini_analysis", 0), 2),
            total=round(total_time, 2),
            celery_task_id=celery_task_id,
        )
    except PermanentPipelineError as e:
        session.rollback()
        ad = session.get(Ad, ad_id)
        if ad:
            ad.status = AdStatus.FAILED.value
            meta = dict(ad.ad_metadata or {})
            meta["error"] = str(e)
            ad.ad_metadata = meta
            session.add(ad)
            session.commit()
        prom.ADS_DECOMPOSITION_FAILED_TOTAL.labels(
            failure_stage="pipeline", error_type="permanent"
        ).inc()
        log.warning("decomposition_failed", ad_id=str(ad_id), error=str(e))
        raise
    except Exception:
        session.rollback()
        log.exception("decomposition_error", ad_id=str(ad_id))
        raise
    finally:
        if work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)
