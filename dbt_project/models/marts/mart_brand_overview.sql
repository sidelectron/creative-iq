with ad_base as (
    select * from {{ ref('int_ads_with_fingerprints') }}
),
score_ranked as (
    select
        *,
        row_number() over (
            partition by brand_id, platform, attribute_name
            order by performance_index_ctr desc nulls last
        ) as rn
    from {{ ref('mart_brand_attribute_scores') }}
),
best_attrs as (
    select
        brand_id,
        platform,
        object_agg(attribute_name, attribute_value) as top_attribute_values,
        object_agg(attribute_name, performance_index_ctr) as top_attribute_indexes
    from score_ranked
    where rn = 1
    group by 1, 2
)
select
    b.brand_id,
    b.platform,
    count(distinct b.ad_id) as total_ads_analyzed,
    count_if(b.status = 'decomposed') as total_ads_decomposed,
    avg(b.avg_ctr) as avg_ctr_all_ads,
    avg(b.avg_cpa) as avg_cpa_all_ads,
    avg(b.avg_roas) as avg_roas_all_ads,
    avg(b.avg_completion_rate) as avg_completion_rate_all_ads,
    min(b.published_at) as min_published_at,
    max(b.published_at) as max_published_at,
    a.top_attribute_values,
    a.top_attribute_indexes,
    current_timestamp() as computed_at
from ad_base b
left join best_attrs a
  on a.brand_id = b.brand_id and a.platform = b.platform
group by 1, 2, a.top_attribute_values, a.top_attribute_indexes

