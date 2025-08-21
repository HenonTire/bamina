import os
from storages.backends.s3boto3 import S3Boto3Storage

class SupabaseMediaStorage(S3Boto3Storage):
    bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")  # reads from .env
    custom_domain = f"{os.getenv('AWS_S3_ENDPOINT_URL')}/{bucket_name}/object/public"
