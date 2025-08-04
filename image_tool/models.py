# image_tool/models.py

import uuid
import os
from django.db import models
from django.conf import settings # Needed for MEDIA_ROOT and MEDIA_URL in delete methods
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# --- Helper functions for dynamic file upload paths ---

User = get_user_model()

def image_uploaded_file_path(instance, filename):
    """
    Generates the upload path for original image files:
    MEDIA_ROOT/image_tool_uploads/<uuid>/<filename>
    """
    return os.path.join('image_tool_uploads', str(instance.id), filename)

# Note: For processed files, the path will be generated in the Celery task
# and stored as a URL in output_url. The path in MEDIA_ROOT will be:
# MEDIA_ROOT/image_tool_processed/<job_uuid>/<filename>

# --- Image Tool Models ---

class UploadedFile(models.Model):
    """
    Represents an original image file uploaded by the user specifically for the image_tool.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=image_uploaded_file_path)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Image Uploaded File (Image Tool)"
        verbose_name_plural = "Image Uploaded Files (Image Tool)"
        # Explicit table name to avoid potential conflicts/clarify scope
        db_table = 'image_tool_uploaded_files'

    def __str__(self):
        return f"Image Upload: {self.original_filename} ({self.id})"

    def delete(self, *args, **kwargs):
        """
        Deletes the associated file from storage when the UploadedFile model instance is deleted.
        """
        if self.file:
            try:
                # Delete the actual file
                self.file.delete(save=False)
                # Try to remove the unique directory if it becomes empty
                file_dir = os.path.dirname(self.file.path)
                if os.path.exists(file_dir) and not os.listdir(file_dir):
                    os.rmdir(file_dir)
            except OSError as e:
                logger.error(f"Error deleting uploaded image file {self.file.path}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error during uploaded image file deletion for {self.file.path}: {e}", exc_info=True)
        super().delete(*args, **kwargs)


class ImageConversionJob(models.Model):
    """
    Represents a specific image conversion job requested by the user.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # Add common image formats for conversion
    FORMAT_CHOICES = [
        ('JPEG', 'JPEG'),
        ('PNG', 'PNG'),
        ('WEBP', 'WebP'),
        ('GIF', 'GIF'),
        ('BMP', 'BMP'), # Although less common for web, support if needed
        ('TIFF', 'TIFF'), # Although less common for web, support if needed
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Link to the specific UploadedFile for this image job
    # Note: This ForeignKey refers to the UploadedFile model within the *same* app.
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='image_conversion_jobs')
    uploaded_file = models.ForeignKey(
        UploadedFile,
        on_delete=models.CASCADE,
        related_name='image_conversion_jobs',
        help_text="The original image file uploaded for this conversion job."
    )

    # Image-specific parameters for the conversion
    tool_type = models.CharField(
        max_length=50,
        choices=[
            ('image_compressor', 'Image Compressor'),
            ('image_resizer', 'Image Resizer'),
            ('image_converter', 'Image Converter'), # Added new tool type
        ],
        default='image_compressor',
        help_text="The type of image operation to perform."
    )
    quality = models.IntegerField(
        null=True, blank=True,
        help_text="JPEG compression quality (0-100). Only applicable for JPEG output."
    )
    width = models.IntegerField(
        null=True, blank=True,
        help_text="Desired width for resizing. If only width or height is provided, aspect ratio is maintained."
    )
    height = models.IntegerField(
        null=True, blank=True,
        help_text="Desired height for resizing. If only width or height is provided, aspect ratio is maintained."
    )
    # New field for target format conversion
    target_format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        null=True, blank=True, # Allow null/blank if only compressing/resizing
        help_text="Desired output format (e.g., JPEG, PNG, WEBP). If not specified, original format will be maintained (if possible)."
    )

    # Job status and output information
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        help_text="Current status of the image conversion job."
    )
    output_url = models.URLField(
        max_length=500,
        null=True, blank=True,
        help_text="URL to the processed image file (relative to MEDIA_URL)."
    )
    error_message = models.TextField(
        null=True, blank=True,
        help_text="Detailed message if the job failed."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Image Conversion Job"
        verbose_name_plural = "Image Conversion Jobs"
        # Explicit table name for clarity and isolation
        db_table = 'image_tool_conversion_jobs'
        ordering = ['-created_at'] # Order by most recent jobs first

    def __str__(self):
        return f"Image Job {self.id} | Status: {self.status} | File: {self.uploaded_file.original_filename}"

    def delete(self, *args, **kwargs):
        """
        Deletes the associated processed file from storage when the ImageConversionJob is deleted.
        """
        if self.output_url:
            try:
                # Remove MEDIA_URL prefix to get relative path within MEDIA_ROOT
                relative_path_in_media = self.output_url.replace(settings.MEDIA_URL, '', 1)
                full_path_to_file = os.path.join(settings.MEDIA_ROOT, relative_path_in_media)

                if os.path.exists(full_path_to_file):
                    os.remove(full_path_to_file)
                    logger.info(f"Deleted processed file: {full_path_to_file}")

                    # Attempt to remove the job-specific directory if it's empty
                    job_specific_dir = os.path.dirname(full_path_to_file)
                    if os.path.exists(job_specific_dir) and not os.listdir(job_specific_dir):
                        os.rmdir(job_specific_dir)
                        logger.info(f"Deleted empty directory: {job_specific_dir}")

            except OSError as e:
                logger.error(f"Error deleting processed image file {full_path_to_file} for job {self.id}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error during processed image file deletion for job {self.id}: {e}", exc_info=True)
        super().delete(*args, **kwargs)