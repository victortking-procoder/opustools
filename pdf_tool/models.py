# --- models.py ---
import uuid
import os
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

def pdf_uploaded_file_path(instance, filename):
    """
    Generates the upload path for original pdf files:
    MEDIA_ROOT/pdf_tool_uploads/<uuid>/<filename>
    """
    return os.path.join('pdf_tool_uploads', str(instance.id), filename)

class PdfUploadedFile(models.Model):
    """
    Represents an original file uploaded by the user specifically for the pdf_tool.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=pdf_uploaded_file_path)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "PDF Tool Uploaded File"
        verbose_name_plural = "PDF Tool Uploaded Files"
        db_table = 'pdf_tool_uploaded_files'

    def __str__(self):
        return f"PDF Upload: {self.original_filename} ({self.id})"

    def delete(self, *args, **kwargs):
        """
        Deletes the associated file from storage when the PdfUploadedFile model instance is deleted.
        """
        if self.file:
            try:
                self.file.delete(save=False)
                file_dir = os.path.dirname(self.file.path)
                if os.path.exists(file_dir) and not os.listdir(file_dir):
                    os.rmdir(file_dir)
            except OSError as e:
                logger.error(f"Error deleting uploaded PDF file {self.file.path}: {e}", exc_info=True)
        super().delete(*args, **kwargs)

class PdfToolJob(models.Model):
    """
    Represents a specific job requested by the user for either PDF conversion, compression, splitting, or merging.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    CONVERSION_FORMAT_CHOICES = [
        ('docx', 'docx'),
        ('xlsx', 'xlsx'),
        ('pptx', 'pptx'),
        ('jpg', 'jpg'),
    ]

    TOOL_TYPE_CHOICES = [
        ('pdf_converter', 'PDF Converter'),
        ('file_compressor', 'File Compressor'),
        ('pdf_merger', 'PDF Merger'), # NEW: Add PDF Merger
        ('pdf_splitter', 'PDF Splitter'), # NEW: Add PDF Splitter
    ]

    COMPRESSION_LEVEL_CHOICES = [
        ('high', 'High Compression'),
        ('medium', 'Medium Compression'),
        ('low', 'Low Compression'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pdf_tool_jobs')
    
    uploaded_files = models.ManyToManyField(
        PdfUploadedFile,
        related_name='pdf_tool_jobs',
        help_text="The file(s) uploaded for this job."
    )

    tool_type = models.CharField(
        max_length=50,
        choices=TOOL_TYPE_CHOICES,
        help_text="The type of operation to perform."
    )

    target_format = models.CharField(
        max_length=10,
        choices=CONVERSION_FORMAT_CHOICES,
        null=True, blank=True,
        help_text="Desired output format for PDF conversion."
    )

    compression_level = models.CharField(
        max_length=10,
        choices=COMPRESSION_LEVEL_CHOICES,
        null=True, blank=True,
        help_text="The desired compression level for PDF files."
    )
    
    # NEW: Fields for Splitting and Merging
    page_ranges = models.CharField(
        max_length=255,
        null=True, blank=True,
        help_text="Page ranges to extract, e.g., '1-5, 8, 10-12'."
    )
    merge_order = models.JSONField(
        null=True, blank=True,
        help_text="An ordered list of filenames to merge, e.g., ['file1.pdf', 'file2.pdf']."
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Current status of the job."
    )
    output_url = models.URLField(
        max_length=500,
        null=True, blank=True,
        help_text="URL to the processed file(s)."
    )
    error_message = models.TextField(
        null=True, blank=True,
        help_text="Detailed message if the job failed."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PDF Tool Job"
        verbose_name_plural = "PDF Tool Jobs"
        db_table = 'pdf_tool_jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f"PDF Tool Job {self.id} | Type: {self.tool_type} | Status: {self.status}"
    
    def delete(self, *args, **kwargs):
        """
        Deletes the associated processed file from storage when the job is deleted.
        """
        if self.output_url:
            try:
                relative_path_in_media = self.output_url.replace(settings.MEDIA_URL, '', 1)
                full_path_to_file = os.path.join(settings.MEDIA_ROOT, relative_path_in_media)

                if os.path.exists(full_path_to_file):
                    os.remove(full_path_to_file)
                    logger.info(f"Deleted processed file: {full_path_to_file}")

                job_specific_dir = os.path.dirname(full_path_to_file)
                if os.path.exists(job_specific_dir) and not os.listdir(job_specific_dir):
                    os.rmdir(job_specific_dir)
                    logger.info(f"Deleted empty directory: {job_specific_dir}")

            except OSError as e:
                logger.error(f"Error deleting processed file for job {self.id}: {e}", exc_info=True)
        super().delete(*args, **kwargs)
