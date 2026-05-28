select *
from read_parquet('{{ var("silver_dir", "data/silver") }}/silver_expression_gtex.parquet')
