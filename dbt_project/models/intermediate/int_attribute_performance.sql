with base as (
    select * from {{ ref('int_ads_with_fingerprints') }}
),
unioned as (
    select ad_id, brand_id, platform, 'hook_type' as attribute_name, cast(hook_type as varchar) as attribute_value, avg_ctr as ctr, avg_cpa as cpa, avg_roas as roas, avg_completion_rate as completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'narrative_arc', cast(narrative_arc as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'emotional_tone', cast(emotional_tone as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'cta_type', cast(cta_type as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'cta_placement', cast(cta_placement as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'product_prominence', cast(product_prominence as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'human_presence', cast(human_presence as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'logo_position', cast(logo_position as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'text_overlay_style', cast(text_overlay_style as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'background_setting', cast(background_setting as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'music_style', cast(music_style as varchar), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'logo_visible', iff(logo_visible, 'true', 'false'), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'has_music', iff(has_music, 'true', 'false'), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
    union all
    select ad_id, brand_id, platform, 'has_voiceover', iff(has_voiceover, 'true', 'false'), avg_ctr, avg_cpa, avg_roas, avg_completion_rate, published_at from base
)
select *
from unioned
where attribute_value is not null

