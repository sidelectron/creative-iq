with perf as (
    select
        ad_id,
        sum(impressions) as total_impressions,
        sum(clicks) as total_clicks,
        sum(conversions) as total_conversions,
        sum(spend) as total_spend,
        sum(revenue) as total_revenue,
        avg(ctr) as avg_ctr,
        avg(cpa) as avg_cpa,
        avg(roas) as avg_roas,
        avg(completion_rate) as avg_completion_rate,
        sum(video_views) as total_video_views,
        min(date) as min_date,
        max(date) as max_date
    from {{ ref('stg_performance') }}
    group by ad_id
)
select
    a.*,
    p.total_impressions,
    p.total_clicks,
    p.total_conversions,
    p.total_spend,
    p.total_revenue,
    p.avg_ctr,
    p.avg_cpa,
    p.avg_roas,
    p.avg_completion_rate,
    p.total_video_views,
    p.max_date,
    coalesce(a.run_duration_days, datediff('day', p.min_date, p.max_date)) as run_duration_days_derived
from {{ ref('stg_ads') }} a
left join perf p
  on p.ad_id = a.ad_id

