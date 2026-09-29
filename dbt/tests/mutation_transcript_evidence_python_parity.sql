-- The Python and dbt implementations must produce the same multiset of rows.
with python_rows as (
  select *
  from read_parquet('{{ var("gold_dir", "data/gold") }}/gold_mutation_transcript_evidence.parquet')
),
dbt_rows as (
  select * from {{ ref('gold_mutation_transcript_evidence') }}
),
python_only as (
  select * from python_rows
  except all
  select * from dbt_rows
),
dbt_only as (
  select * from dbt_rows
  except all
  select * from python_rows
)
select * from python_only
union all
select * from dbt_only
