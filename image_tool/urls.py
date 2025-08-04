# image_tool/urls.py

from django.urls import path
from .views import (
    ImageConversionView,
    ImageConversionJobStatusView,
    ImageConversionJobDownloadView
)

urlpatterns = [
    # Endpoint for creating a new image conversion job
    # POST to /api/image/convert/
    path('convert/', ImageConversionView.as_view(), name='image_convert_create'),

    # Endpoint for checking the status of an image conversion job
    # GET to /api/image/jobs/<uuid:id>/status/
    path('jobs/<uuid:id>/status/', ImageConversionJobStatusView.as_view(), name='image_job_status'),

    # Endpoint for downloading the processed image file
    # GET to /api/image/jobs/<uuid:job_id>/download/
    path('jobs/<uuid:job_id>/download/', ImageConversionJobDownloadView.as_view(), name='image_job_download'),
]