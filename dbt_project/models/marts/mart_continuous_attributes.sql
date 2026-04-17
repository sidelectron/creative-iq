with base as (
    select * from {{ ref('int_ads_with_fingerprints') }}
),
continuous_attributes as (
    select ad_id, brand_id, platform, 'color_warmth' as attribute_name, color_warmth as attribute_value, avg_ctr as ctr, avg_cpa as cpa, avg_roas as roas, avg_completion_rate as completion_rate from base
    union all
    select ad_id, brand_id, platform, 'motion_intensity', motion_intensity, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
    union all
    select ad_id, brand_id, platform, 'text_density', text_density, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
    union all
    select ad_id, brand_id, platform, 'face_present_ratio', face_present_ratio, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
    union all
    select ad_id, brand_id, platform, 'duration_seconds', duration_seconds, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
    union all
    select ad_id, brand_id, platform, 'scene_count', scene_count::float, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
    union all
    select ad_id, brand_id, platform, 'product_first_appearance_seconds', product_first_appearance_seconds, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
    union all
    select ad_id, brand_id, platform, 'audio_energy_mean', audio_energy_mean, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
    union all
    select ad_id, brand_id, platform, 'silence_ratio', silence_ratio, avg_ctr, avg_cpa, avg_roas, avg_completion_rate from base
),
scored as (
    select
        *,
        ntile(5) over (partition by brand_id, platform, attribute_name order by attribute_value) as quantile_bin
    from continuous_attributes
    where attribute_value is not null
),
agg as (
    select
        brand_id,
        platform,
        attribute_name,
        'ctr' as metric_name,
        corr(attribute_value, ctr) as pearson_correlation,
        avg(attribute_value) as attribute_mean,
        stddev(attribute_value) as attribute_stddev,
        object_agg(quantile_bin::varchar, avg(ctr)) as quantile_performance
    from scored
    group by 1, 2, 3
    union all
    select
        brand_id,
        platform,
        attribute_name,
        'cpa' as metric_name,
        corr(attribute_value, cpa) as pearson_correlation,
        avg(attribute_value) as attribute_mean,
        stddev(attribute_value) as attribute_stddev,
        object_agg(quantile_bin::varchar, avg(cpa)) as quantile_performance
    from scored
    group by 1, 2, 3
    union all
    select
        brand_id,
        platform,
        attribute_name,
        'roas' as metric_name,
        corr(attribute_value, roas) as pearson_correlation,
        avg(attribute_value) as attribute_mean,
        stddev(attribute_value) as attribute_stddev,
        object_agg(quantile_bin::varchar, avg(roas)) as quantile_performance
    from scored
    group by 1, 2, 3
    union all
    select
        brand_id,
        platform,
        attribute_name,
        'completion_rate' as metric_name,
        corr(attribute_value, completion_rate) as pearson_correlation,
        avg(attribute_value) as attribute_mean,
        stddev(attribute_value) as attribute_stddev,
        object_agg(quantile_bin::varchar, avg(completion_rate)) as quantile_performance
    from scored
    group by 1, 2, 3
)
select
    *,
    current_timestamp() as computed_at
from agg

