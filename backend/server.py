from flask import Flask
app = Flask(__name__)


from sqlalchemy import create_engine, text
host, un, pw, port = 'conservation-intl.clqfooklvyn0.us-east-1.rds.amazonaws.com','postgres','postgres',5432 
dbname = 'vitalsigns_staging'
engine = create_engine('postgresql://{un}:{pw}@{host}:{port}/{dbname}'.format(
        un=un,
        pw=pw,
        host=host,
        port=port,
        dbname=dbname))


@app.route('/')
def hello_world():
    return 'Hello, World!'


sql_text = "SELECT country.name,country.country,agric.landscape_no,landscape.description, landscape.shape FROM public.agric agric, public.country country, public.agric_field_details agric_field_details, public.landscape landscape where agric.country=country.country and agric.country='TZA' and agric_field_details.parent_uuid=agric.uuid and landscape.landscape_no = agric.landscape_no ORDER BY agric_field_details.ag3a_40 desc"

@app.route('/fertilizer_use')
def fertilizer_use():
	sql = text(sql_text)
	result = engine.execute(sql)
	header = ",".join(result.keys())
	rows = "\n".join(",".join(row) for row in result.fetchall())
	return header+"\n"+rows

