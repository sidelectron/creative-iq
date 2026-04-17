{{ config(materialized='incremental', unique_key='ad_id', incremental_strategy='delete+insert') }}

select
    u.*,
    f.hook_type,
    f.narrative_arc,
    f.emotional_tone,
    f.cta_type,
    f.cta_placement,
    f.cta_text,
    f.product_first_appearance_seconds,
    f.product_prominence,
    f.human_presence,
    f.logo_visible,
    f.logo_first_appearance_seconds,
    f.logo_position,
    f.text_overlay_style,
    f.background_setting,
    f.music_style,
    f.color_palette,
    f.color_warmth,
    f.color_saturation,
    f.scene_count,
    f.avg_scene_duration,
    f.motion_intensity,
    f.text_density,
    f.face_present_ratio,
    f.has_music,
    f.has_voiceover,
    f.audio_energy_mean,
    f.silence_ratio,
    f.tempo_bpm,
    f.duration_seconds,
    f.word_count,
    f.transcript,
    f.processing_duration_seconds
from {{ ref('int_ads_unified') }} u
inner join {{ ref('stg_fingerprints') }} f
  on f.ad_id = u.ad_id
where u.total_impressions is not null
{% if is_incremental() %}
  and u.updated_at > (select coalesce(max(updated_at), '1970-01-01'::timestamp_tz) from {{ this }})
{% endif %}

