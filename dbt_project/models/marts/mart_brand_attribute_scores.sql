{{ config(materialized='incremental', unique_key=['brand_id', 'platform', 'attribute_name', 'attribute_value'], incremental_strategy='delete+insert') }}

with source_rows as (
    select * from {{ ref('int_attribute_performance') }}
    {% if is_incremental() %}
      where concat(brand_id, '|', platform) in (
        select distinct concat(brand_id, '|', platform)
        from {{ ref('int_ads_with_fingerprints') }}
        where updated_at > (select coalesce(max(computed_at), '1970-01-01'::timestamp_tz) from {{ this }})
      )
    {% endif %}
),
brand_baselines as (
    select
        brand_id,
        platform,
        avg(ctr) as brand_avg_ctr,
        avg(cpa) as brand_avg_cpa,
        avg(roas) as brand_avg_roas,
        avg(completion_rate) as brand_avg_completion_rate
    from source_rows
    group by 1, 2
)
select
    s.brand_id,
    s.platform,
    s.attribute_name,
    s.attribute_value,
    avg(s.ctr) as avg_ctr,
    avg(s.cpa) as avg_cpa,
    avg(s.roas) as avg_roas,
    avg(s.completion_rate) as avg_completion_rate,
    count(distinct s.ad_id) as sample_size,
    stddev(s.ctr) as std_ctr,
    stddev(s.cpa) as std_cpa,
    min(s.published_at) as min_date,
    max(s.published_at) as max_date,
    b.brand_avg_ctr,
    b.brand_avg_cpa,
    b.brand_avg_roas,
    b.brand_avg_completion_rate,
    iff(b.brand_avg_ctr > 0, avg(s.ctr) / b.brand_avg_ctr, null) as performance_index_ctr,
    iff(avg(s.cpa) > 0, b.brand_avg_cpa / avg(s.cpa), null) as performance_index_cpa,
    iff(b.brand_avg_roas > 0, avg(s.roas) / b.brand_avg_roas, null) as performance_index_roas,
    iff(
        b.brand_avg_completion_rate > 0,
        avg(s.completion_rate) / b.brand_avg_completion_rate,
        null
    ) as performance_index_completion_rate,
    current_timestamp() as computed_at
from source_rows s
left join brand_baselines b
  on b.brand_id = s.brand_id and b.platform = s.platform
group by
    s.brand_id,
    s.platform,
    s.attribute_name,
    s.attribute_value,
    b.brand_avg_ctr,
    b.brand_avg_cpa,
    b.brand_avg_roas,
    b.brand_avg_completion_rate

