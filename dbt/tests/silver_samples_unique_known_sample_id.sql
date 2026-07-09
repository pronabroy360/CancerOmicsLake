select sample_id
from {{ ref('silver_samples') }}
where sample_id is not null
  and trim(sample_id) != ''
  and lower(sample_id) != 'unknown'
group by sample_id
having count(*) > 1
