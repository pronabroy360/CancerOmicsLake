select *
from read_parquet('{{ var("silver_dir", "data/silver") }}/silver_file_manifest.parquet')
