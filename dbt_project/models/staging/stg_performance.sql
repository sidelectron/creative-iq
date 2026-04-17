{{ config(materialized='incremental', unique_key=['ad_id', 'date'], incremental_strategy='delete+insert') }}

with ranked as (
    select
        cast(ad_id as varchar) as ad_id,
        cast(date as date) as date,
        cast(impressions as integer) as impressions,
        cast(clicks as integer) as clicks,
        cast(conversions as integer) as conversions,
        cast(spend as float) as spend,
        cast(revenue as float) as revenue,
        cast(video_views as integer) as video_views,
        cast(video_completions as integer) as video_completions,
        cast(engagement_count as integer) as engagement_count,
        metadata as metadata,
        cast(loaded_at as timestamp_tz) as loaded_at,
        row_number() over (
            partition by ad_id, date
            order by loaded_at desc
        ) as rn
    from {{ source('raw', 'ad_performance') }}
    {% if is_incremental() %}
      where loaded_at > (select coalesce(max(loaded_at), '1970-01-01'::timestamp_tz) from {{ this }})
    {% endif %}
)
select
    ad_id,
    date,
    impressions,
    clicks,
    conversions,
    spend,
    revenue,
    video_views,
    video_completions,
    engagement_count,
    metadata,
    loaded_at,
    iff(impressions > 0, clicks / impressions::float, null) as ctr,
    iff(conversions > 0, spend / conversions, null) as cpa,
    iff(spend > 0, revenue / spend, null) as roas,
    iff(video_views > 0, video_completions / video_views::float, null) as completion_rate
from ranked
where rn = 1

