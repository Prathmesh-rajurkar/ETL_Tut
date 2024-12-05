from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.dates import days_ago
import json
from airflow.models import Connection

## Define DAG

with DAG(
    dag_id='nasa_apod_postgres',
    start_date=days_ago(1),
    schedule_interval='@daily',
    catchup=False
) as dag:

    ## Step 1: Create a table if it doesn't exist
    @task
    def create_table():
        postgres_hook = PostgresHook(postgres_conn_id='my_postgres_connection')

        ## Sql query to create table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS apod_data(
            id SERIAL PRIMARY KEY,
            title VARCHAR(255),
            explanation TEXT,
            url TEXT,
            date DATE,
            media_type VARCHAR(50)
        );
        """
        postgres_hook.run(create_table_query)


    ## Step 2: Extract the NASA API Data(APOD Data)

    extract_apod = SimpleHttpOperator(
        task_id='extract_apod',
        http_conn_id = 'nasa_api',
        endpoint='planetary/apod',
        method='GET',
        data={"api_key":"{{conn.nasa_api.extra_dejson.api_key}}"},
        response_filter = lambda response:response.json(),
    )


    ## Step 3: Transform the Data(Pick the information i need to save)

    @task
    def transform_apod_data(response):
        apod_data={
            'title':response.get('title',''),
            'explanation':response.get('explanation',''),
            'url':response.get('url',''),
            'date':response.get('date',''),
            'media_type':response.get('media_type','')
        }
        return apod_data


    ## Step 4: Load the information into postgres

    @task
    def load_data_to_postgres(apod_data):
        postgres_hook = PostgresHook(postgres_conn_id='my_postgres_connection')

        ## define the SQl insert query
        insert_query = '''
        INSERT INTO apod_data (title,explanation,url,date,media_type)
        VALUES (%s,%s,%s,%s,%s);
        '''

        postgres_hook.run(insert_query,parameters=(
            apod_data['title'],
            apod_data['explanation'],
            apod_data['url'],
            apod_data['date'],
            apod_data['media_type']
        ))



    ## Step 5: Verify the data DBViewer

    ## Step 6: Define task dependencies
    # extract E
    create_table() >> extract_apod
    api_response = extract_apod.output
    # transform T
    transformed_data=transform_apod_data(api_response)
    # load L
    load_data_to_postgres(transformed_data)


# netstat -ano | findstr :5432
# taskkill /PID <PID> /F