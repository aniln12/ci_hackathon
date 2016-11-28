import pandas
host,un,pw,port = pandas.read_csv('rds_settings.csv').values.tolist()[0]


dbname = 'r_output'
from sqlalchemy import create_engine, text
engine = create_engine('postgresql://{un}:{pw}@{host}:{port}/{dbname}'.format(
	un=un,
	pw=pw,
	host=host,
	port=port,
	dbname=dbname))

sql = text('DROP TABLE IF EXISTS nutrition_individual;')
result = engine.execute(sql)
df = pandas.read_csv('Nutrition.Individual.csv')
df.to_sql('nutrition_individual', engine)

sql = text('DROP TABLE IF EXISTS nutrition_landscape;')
result = engine.execute(sql)
df = pandas.read_csv('Nutrition.Landscape.csv')
df.to_sql('nutrition_landscape', engine)
