from datetime import datetime, timedelta, date
from airflow.decorators import dag, task
from airflow import DAG
from airflow.models import TaskInstance, XCom
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup
import requests
import json
from googleapiclient.discovery import build
from airflow.utils.dates import days_ago
import pandas as pd
import csv
import boto3
import os


# Replace with your API key and AWS access keys
api_key = "YOUR_YOUTUBE_API_KEY"
aws_access_key_id = "YOUR_AWS_ACCESS_KEY_ID"
aws_secret_access_key = "YOUR_AWS_SECRET_ACCESS_KEY"

#DAG Arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

#DAG Definition
dag = DAG(
    'youtube_data_pipeline',
    default_args=default_args,
    description='A simple data pipeline for fetching popular YouTube videos and uploading to S3',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2022, 1, 1),
    catchup=False
)

#Task-1
def fetch_youtube_videos(**kwargs):
    youtube = build('youtube', 'v3', developerKey=api_key)
    request = youtube.videos().list(
        part='snippet,contentDetails,statistics',
        chart='mostPopular',
        regionCode='IN',
        maxResults=10
    )
    response = request.execute()
    videos = response['items']
    video_list = []
    for video in videos:
        video_dict = {}
        video_dict['title'] = video['snippet']['channelTitle']
        video_dict['tit'] = video['snippet']['title']
        video_dict['duration'] = video['contentDetails']['duration']
        video_dict['categoryId'] = video['snippet']['categoryId']
        video_dict['viewcount'] = video['statistics']['viewCount']
        video_dict['likecount'] = video['statistics']['likeCount']
        video_list.append(video_dict)

    print(f"Video list in fetch_youtube_videos: {video_list}")  # Debugging: print the video_list

    # Save the video_list to a temporary JSON file
    with open("temp_video_list.json", "w") as f:
        json.dump(video_list, f)

#Task-2
def upload_to_s3(**kwargs):
    # Load the video_list from the temporary JSON file
    with open("temp_video_list.json", "r") as f:
        video_list = json.load(f)

    print(f"Video list in upload_to_s3: {video_list}")  # Debugging: print the video_list

    # ... Rest of the code for upload_to_s3

    s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
    bucket_name = 'airflow-csv-files'
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f'youtube_videos_{dt_string}.csv'
    object_key = filename
    csv_str = 'channel,video_title,video_duration,video_category,video_viewcount,video_likecount\n'
    print(f'video_list: {video_list}')
    title_len = max([len(video['title']) for video in video_list])
    title_len = max(title_len, 20)
    tit_len = max([len(video['tit']) for video in video_list])
    tit_len = max(title_len, 40)
    duration_len = max([len(video['duration']) for video in video_list])
    for video in video_list:
        csv_str += f"{video['title'][:title_len]},{video['tit'][:tit_len]},{video['duration'][:duration_len]},"
        csv_str += f"{video['categoryId']},{video['viewcount']},{video['likecount']}\n"
    s3.put_object(Bucket=bucket_name, Key=object_key, Body=csv_str)
    return f"s3://{bucket_name}/{object_key}"


with dag:
    fetch_videos_task = PythonOperator(
        task_id='fetch_youtube_videos',
        python_callable=fetch_youtube_videos,
        provide_context=True,
    )
    
    upload_to_s3_task = PythonOperator(
        task_id='upload_to_s3',
        python_callable=upload_to_s3,
        provide_context=True,
    )
    
    print_completion = BashOperator(
        task_id='print_completion',
        bash_command='echo "Data pipeline complete!"'
    )
    
    #Task Pipeline
    fetch_videos_task >> upload_to_s3_task >> print_completion