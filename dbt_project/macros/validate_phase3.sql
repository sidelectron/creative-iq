{% macro validate_phase3() %}

-- 1) raw.ads coverage in stg_ads (excluding soft deleted)
select
  'raw_ads_covered_by_stg_ads' as check_name,
  count(*) as failures
from {{ source('raw', 'ads') }} r
left join {{ ref('stg_ads') }} s
  on cast(r.id as varchar) = s.ad_id
where r.deleted_at is null
  and s.ad_id is null

union all

-- 2) fingerprints have core flattened fields
select
  'fingerprints_have_core_attributes' as check_name,
  count(*) as failures
from {{ ref('stg_fingerprints') }}
where hook_type is null
   or narrative_arc is null
   or emotional_tone is null

union all

-- 3) int_ads_with_fingerprints has both perf and fingerprint indicators
select
  'int_ads_with_fingerprints_has_perf_and_fp' as check_name,
  count(*) as failures
from {{ ref('int_ads_with_fingerprints') }}
where total_impressions is null
   or hook_type is null

union all

-- 4) mart has rows for present categorical attributes
select
  'mart_attribute_presence' as check_name,
  count(*) as failures
from (
  select distinct attribute_name
  from {{ ref('int_attribute_performance') }}
) p
left join (
  select distinct attribute_name
  from {{ ref('mart_brand_attribute_scores') }}
) m
  on p.attribute_name = m.attribute_name
where m.attribute_name is null

{% endmacro %}

