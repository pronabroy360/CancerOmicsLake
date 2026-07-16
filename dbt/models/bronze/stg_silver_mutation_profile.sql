select *
from read_parquet('{{ var("silver_dir", "data/silver") }}/silver_mutation_profile.parquet')
