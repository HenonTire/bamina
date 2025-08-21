# storage/storage_backends.py
from storages.backends.s3boto3 import S3Boto3Storage

class SupabaseMediaStorage(S3Boto3Storage):
    bucket_name = "your-supabase-bucket"
    custom_domain = f"{bucket_name}.supabase.co/storage/v1/object/public"
