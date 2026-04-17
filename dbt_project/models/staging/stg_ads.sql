with ranked as (
    select
        cast(id as varchar) as ad_id,
        cast(brand_id as varchar) as brand_id,
        cast(external_id as varchar) as external_id,
        lower(cast(platform as varchar)) as platform,
        cast(ad_format as varchar) as ad_format,
        cast(title as varchar) as title,
        cast(description as varchar) as description,
        cast(gcs_video_path as varchar) as gcs_video_path,
        cast(thumbnail_gcs_path as varchar) as thumbnail_gcs_path,
        cast(duration_seconds as float) as duration_seconds,
        cast(resolution as varchar) as resolution,
        cast(source as varchar) as source,
        cast(status as varchar) as status,
        cast(published_at as timestamp_tz) as published_at,
        cast(deactivated_at as timestamp_tz) as deactivated_at,
        cast(run_duration_days as integer) as run_duration_days,
        metadata as metadata,
        cast(created_at as timestamp_tz) as created_at,
        cast(updated_at as timestamp_tz) as updated_at,
        cast(deleted_at as timestamp_tz) as deleted_at,
        cast(loaded_at as timestamp_tz) as loaded_at,
        row_number() over (partition by id order by loaded_at desc) as rn
    from {{ source('raw', 'ads') }}
)
select
    ad_id,
    brand_id,
    external_id,
    platform,
    ad_format,
    title,
    description,
    gcs_video_path,
    thumbnail_gcs_path,
    duration_seconds,
    resolution,
    source,
    status,
    published_at,
    deactivated_at,
    run_duration_days,
    metadata,
    created_at,
    updated_at,
    deleted_at,
    loaded_at,
    deactivated_at is null as is_active
from ranked
where rn = 1
  and deleted_at is null

