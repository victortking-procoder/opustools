# image_tool/tasks.py

import os
import logging
import datetime
import shutil
import subprocess
from celery import shared_task
from django.conf import settings
from PIL import Image

# Import the model from the current app
from .models import ImageConversionJob

logger = logging.getLogger(__name__)

# Helper to get PIL format from filename extension, or default
def get_pil_format_from_filename(filename):
    """
    Determines the PIL format string (e.g., 'JPEG', 'PNG') from a filename's extension.
    Returns a default if not recognized.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.jpg' or ext == '.jpeg':
        return 'JPEG'
    elif ext == '.png':
        return 'PNG'
    elif ext == '.gif':
        return 'GIF'
    elif ext == '.webp':
        return 'WEBP'
    elif ext == '.bmp':
        return 'BMP'
    elif ext == '.tiff' or ext == '.tif':
        return 'TIFF'
    # Default to a common format
    return 'JPEG'

@shared_task(bind=True) # bind=True allows access to task instance properties like self.request
def process_image_task(self, job_id):
    """
    Celery task to handle all operations for the image_tool based on the 'tool_type'.
    This task consolidates image conversion, resizing, and compression.
    """
    job = None
    try:
        # Retrieve the job instance from the database using only the job ID
        job = ImageConversionJob.objects.get(id=job_id)
        job.status = 'PROCESSING'
        job.save()

        tool_type = job.tool_type
        logger.info(f"Task {self.request.id}: Starting image processing for job ID: {job_id} with tool_type: {tool_type}")

        # Retrieve all parameters from the job instance
        file_path_relative_to_media_root = job.uploaded_file.file.name
        absolute_source_file_path = os.path.join(settings.MEDIA_ROOT, file_path_relative_to_media_root)

        # Ensure the source file exists
        if not os.path.exists(absolute_source_file_path):
            raise FileNotFoundError(f"Source file does not exist at {absolute_source_file_path}")

        # Open the image once to be used by all processing logic
        with Image.open(absolute_source_file_path) as img:
            processed_img = img.copy()
            original_width, original_height = img.size
            original_format = img.format

            # Define output directory for processed files, unique per job
            output_dir_relative_to_media_root = os.path.join('image_tool_processed', str(job.id))
            os.makedirs(os.path.join(settings.MEDIA_ROOT, output_dir_relative_to_media_root), exist_ok=True)
            
            base_filename = os.path.splitext(os.path.basename(file_path_relative_to_media_root))[0]
            download_url = None # Initialize download URL to None

            if tool_type == 'image_resizer':
                # --- Resizing Logic ---
                logger.info("Tool type is 'image_resizer'. Applying resizing logic.")
                
                width = job.width
                height = job.height

                # Only resize if dimensions are provided
                if width is not None and height is not None:
                    processed_img = processed_img.resize((width, height), Image.LANCZOS)
                elif width is not None:
                    new_height = int(original_height * (width / original_width))
                    processed_img = processed_img.resize((width, new_height), Image.LANCZOS)
                elif height is not None:
                    new_width = int(original_width * (height / original_height))
                    processed_img = processed_img.resize((new_width, height), Image.LANCZOS)
                
                # Determine output format. If target_format is provided, use it. Otherwise, keep original.
                output_format = job.target_format.upper() if job.target_format else original_format
                output_filename = f"resized_{base_filename}.{output_format.lower()}"
                output_full_absolute_path = os.path.join(settings.MEDIA_ROOT, output_dir_relative_to_media_root, output_filename)
                
                # Handle transparency if converting to JPEG
                if output_format == 'JPEG' and processed_img.mode == 'RGBA':
                    background = Image.new('RGB', processed_img.size, (255, 255, 255))
                    background.paste(processed_img, (0, 0), processed_img)
                    processed_img = background

                # Save the resized image
                processed_img.save(output_full_absolute_path, format=output_format)
                
                download_url = os.path.join(settings.MEDIA_URL, output_dir_relative_to_media_root, output_filename).replace('\\', '/')

            elif tool_type == 'image_compressor':
                # --- Compression Logic (with special PNG handling) ---
                logger.info("Tool type is 'image_compressor'. Applying compression logic.")
                
                # Determine output format and quality
                output_format = job.target_format.upper() if job.target_format else original_format
                quality = job.quality
                
                output_filename = f"compressed_{base_filename}.{output_format.lower()}"
                output_full_absolute_path = os.path.join(settings.MEDIA_ROOT, output_dir_relative_to_media_root, output_filename)

                if output_format == 'PNG':
                    # Special handling for PNG using pngquant
                    logger.info("PNG compression requested. Running pngquant with quality 20-70.")
                    temp_output_path = f"{output_full_absolute_path}.tmp"
                    
                    try:
                        subprocess.run([
                            "pngquant",
                            "--quality", "40-80",
                            "--force",
                            "--output", temp_output_path,
                            absolute_source_file_path
                        ], check=True)
                        shutil.move(temp_output_path, output_full_absolute_path)
                        logger.info("PNG compression successful.")
                    except FileNotFoundError:
                        logger.warning("pngquant not found. Falling back to Pillow PNG compression.")
                        processed_img.save(output_full_absolute_path, format='PNG', optimize=True)
                    except subprocess.CalledProcessError as e:
                        logger.error(f"pngquant command failed with error: {e.stderr.decode()}. Falling back to Pillow.")
                        processed_img.save(output_full_absolute_path, format='PNG', optimize=True)
                else:
                    # Compression for other formats using Pillow
                    logger.info(f"Applying Pillow compression for format: {output_format}")
                    save_params = {'optimize': True}
                    if quality is not None:
                        save_params['quality'] = quality
                    
                    # Handle transparency if converting to JPEG
                    if output_format == 'JPEG' and processed_img.mode == 'RGBA':
                        background = Image.new('RGB', processed_img.size, (255, 255, 255))
                        background.paste(processed_img, (0, 0), processed_img)
                        processed_img = background

                    processed_img.save(output_full_absolute_path, format=output_format, **save_params)
                
                download_url = os.path.join(settings.MEDIA_URL, output_dir_relative_to_media_root, output_filename).replace('\\', '/')
            
            elif tool_type == 'image_converter':
                # --- Format Conversion Logic ---
                logger.info("Tool type is 'image_converter'. Applying format conversion logic.")
                
                # Define a mapping for user-friendly format strings to Pillow's internal format names
                format_mapping = {
                    'jpg': 'JPEG',
                    'jpeg': 'JPEG',
                    'png': 'PNG',
                    'gif': 'GIF',
                    'webp': 'WEBP',
                    'bmp': 'BMP',
                    'tiff': 'TIFF',
                    'tif': 'TIFF'
                }
                
                # Get the target format from the job and convert it to the correct PIL format name
                target_format_lower = job.target_format.lower()
                output_format = format_mapping.get(target_format_lower)

                if not output_format:
                    raise ValueError(f"Unsupported target format: {job.target_format}. Supported formats are: {', '.join(format_mapping.keys())}.")
                
                output_filename = f"converted_{base_filename}.{target_format_lower}"
                output_full_absolute_path = os.path.join(settings.MEDIA_ROOT, output_dir_relative_to_media_root, output_filename)
                
                # Handle transparency if converting to JPEG
                if output_format == 'JPEG' and processed_img.mode == 'RGBA':
                    background = Image.new('RGB', processed_img.size, (255, 255, 255))
                    background.paste(processed_img, (0, 0), processed_img)
                    processed_img = background

                # Save the converted image
                processed_img.save(output_full_absolute_path, format=output_format)

                download_url = os.path.join(settings.MEDIA_URL, output_dir_relative_to_media_root, output_filename).replace('\\', '/')

            else:
                raise ValueError(f"Unknown tool_type: {tool_type}")
            
            # Update job status and URL if the processing was successful
            if download_url:
                job.output_url = download_url
                job.status = 'COMPLETED'
                job.save()
                logger.info(f"Task {self.request.id}: Job {job_id} status updated to COMPLETED. Output URL stored.")

    except ImageConversionJob.DoesNotExist:
        logger.error(f"Task {self.request.id}: ImageConversionJob with ID {job_id} does not exist. Cannot update job status.", exc_info=True)
    except FileNotFoundError as e:
        logger.error(f"Task {self.request.id}: FileNotFoundError for job {job_id}: {e}", exc_info=True)
        if job:
            job.status = 'FAILED'
            job.error_message = f"Processing failed: Source file not found or accessible. Error: {e}"
            job.save()
    except Exception as e:
        logger.error(f"Task {self.request.id}: An unexpected error occurred for job {job_id}: {e}", exc_info=True)
        if job:
            job.status = 'FAILED'
            job.error_message = f"Processing failed due to an internal error: {str(e)}"
            job.save()

@shared_task
def cleanup_old_media():
    media_path = settings.MEDIA_ROOT
    threshold = datetime.datetime.now() - datetime.timedelta(days=1)  # delete files older than 1 day

    deleted = 0
    for dirpath, _, filenames in os.walk(media_path):
        for file in filenames:
            file_path = os.path.join(dirpath, file)
            if os.path.isfile(file_path):
                modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if modified_time < threshold:
                    os.remove(file_path)
                    deleted += 1
    return f"{deleted} old files deleted."