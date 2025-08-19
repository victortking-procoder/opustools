# pdf_tool/urls.py

from django.urls import path
from .views import (
    PdfToolJobView,
    PdfToolJobStatusView,
    PdfToolJobDownloadView
)

urlpatterns = [
    # A single endpoint for creating either a new PDF conversion or file compression job.
    # The 'tool_type' in the request body determines the action.
    # POST to /api/pdf/process/
    path('process/', PdfToolJobView.as_view(), name='pdf_tool_process'),

    # Endpoint for checking the status of a job.
    # GET to /api/pdf/jobs/<uuid:id>/status/
    path('jobs/<uuid:id>/status/', PdfToolJobStatusView.as_view(), name='pdf_job_status'),

    # Endpoint for downloading the processed file.
    # GET to /api/pdf/jobs/<uuid:job_id>/download/
    path('jobs/<uuid:job_id>/download/', PdfToolJobDownloadView.as_view(), name='pdf_job_download'),
]