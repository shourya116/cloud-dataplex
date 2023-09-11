"""Airflow dag to async run and evaluate data quality scan"""
import pendulum
from airflow import DAG
from airflow.operators.python import BranchPythonOperator
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.dataplex import DataplexGetDataQualityScanResultOperator
from airflow.providers.google.cloud.operators.dataplex import DataplexRunDataQualityScanOperator
from airflow.providers.google.cloud.sensors.dataplex import DataplexDataQualityJobStatusSensor
from datetime import timedelta, datetime

"""replace project id and region with user project and the region respectively.
   replace data scan id with the scan user wants to run.
"""
PROJECT_ID = "test-project"
REGION = "us-central1"
DATA_SCAN_ID = "airflow-data-quality-scan"

default_args = {
    'start_date': pendulum.today('UTC').add(days=0),
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'runAsync_evaluate',
    default_args=default_args,
    description='Test custom dataplex datascan run_async->evaluate flow',
    schedule_interval='0 0 * * *',
    start_date=datetime.now(),
    max_active_runs=2,
    catchup=False,
    dagrun_timeout=timedelta(minutes=20))

run_data_scan_async = DataplexRunDataQualityScanOperator(
    task_id="run_data_scan_async",
    project_id=PROJECT_ID,
    region=REGION,
    dag=dag,
    data_scan_id=DATA_SCAN_ID,
    asynchronous=True,
)

get_data_scan_job_status = DataplexDataQualityJobStatusSensor(
        task_id="get_data_scan_job_status",
        project_id=PROJECT_ID,
        region=REGION,
        data_scan_id=DATA_SCAN_ID,
        job_id="{{ task_instance.xcom_pull('run_data_scan_async') }}",
    )

get_job_result = DataplexGetDataQualityScanResultOperator(
            task_id="get_data_scan_job_result",
            project_id=PROJECT_ID,
            region=REGION,
            dag=dag,
            data_scan_id=DATA_SCAN_ID)

def process_data_from_data_scan_job(**kwargs):
    ti = kwargs['ti']
    job_data = ti.xcom_pull(task_ids='get_data_scan_job_result')
    if "dataQualityResult" not in job_data:
        return "failed_job"
    print(f"data quality job result: {job_data.get('dataQualityResult')}")
    if "passed" in job_data["dataQualityResult"]:
        return "passed_job"
    return "failed_job"

def pass_job(**kwargs):
    print("data quality job passed")

def fail_job(**kwargs):
    print("data quality job failed")

passed_job = PythonOperator(
    task_id = "passed_job",
    python_callable=pass_job,
    dag=dag
    )

failed_job = PythonOperator(
    task_id = "failed_job",
    python_callable=fail_job,
    dag=dag
    )

process_data = BranchPythonOperator(
      task_id='process_data_from_data_scan_job',
      python_callable=process_data_from_data_scan_job,
      dag=dag
      )

run_data_scan_async >> get_job_result >> process_data >> passed_job
run_data_scan_async >> get_job_result >> process_data >> failed_job