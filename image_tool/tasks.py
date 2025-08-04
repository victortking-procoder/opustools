# image_tool/tasks.py

import os
import logging
from celery import shared_task
from django.conf import settings
from PIL import Image # Ensure Pillow is installed (pip install Pillow)
import datetime
import mimetypes

# Import the model from the current app
from .models import ImageConversionJob

logger = logging.getLogger(__name__)

# Helper to get PIL format from filename extension, or default
def get_pil_format_from_filename(filename):
    """
    Determines the PIL format string (e.g., 'JPEG', 'PNG') from a filename's extension.
    Returns None if the extension is not recognized by Pillow,
    or a common format string otherwise.
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
    # Add more as needed
    return None

@shared_task(bind=True) # bind=True allows access to task instance properties like self.request
def process_image_task(self, file_path_relative_to_media_root, job_id, tool_type, quality, width, height, target_format):
    """
    Celery task to handle image compression, resizing, and format conversion for the image_tool.
    """
    logger.info(f"Task {self.request.id}: Starting image processing for job ID: {job_id}")
    logger.info(f"Original file path relative to MEDIA_ROOT: {file_path_relative_to_media_root}")
    logger.info(f"Parameters: tool_type={tool_type}, quality={quality}, width={width}, height={height}, target_format={target_format}")

    job = None # Initialize job to None
    absolute_source_file_path = os.path.join(settings.MEDIA_ROOT, file_path_relative_to_media_root)

    try:
        # Retrieve the job instance from the database
        job = ImageConversionJob.objects.get(id=job_id)
        job.status = 'PROCESSING'
        job.save()
        logger.info(f"Task {self.request.id}: Job {job_id} status updated to PROCESSING.")

        # --- Validate Source File Existence ---
        if not os.path.exists(absolute_source_file_path):
            raise FileNotFoundError(f"Source file does not exist at {absolute_source_file_path}")

        # --- Open Image with Pillow ---
        with Image.open(absolute_source_file_path) as img:
            logger.info(f"Task {self.request.id}: Successfully opened image: {absolute_source_file_path}")

            original_width, original_height = img.size
            original_format = img.format # Get the original format of the image
            logger.info(f"Task {self.request.id}: Original image dimensions: {original_width}x{original_height}, format: {original_format}")

            processed_img = img.copy() # Work on a copy to avoid modifying original in memory

            # --- Resizing Logic ---
            if width is not None and height is not None:
                # Resize to exact dimensions
                processed_img = processed_img.resize((width, height), Image.LANCZOS)
                logger.info(f"Task {self.request.id}: Resized image to exact dimensions: {width}x{height}")
            elif width is not None:
                # Resize to target width, maintaining aspect ratio
                new_height = int(original_height * (width / original_width))
                processed_img = processed_img.resize((width, new_height), Image.LANCZOS)
                logger.info(f"Task {self.request.id}: Resized image to width {width}, calculated height: {new_height}")
            elif height is not None:
                # Resize to target height, maintaining aspect ratio
                new_width = int(original_width * (height / original_height))
                processed_img = processed_img.resize((new_width, height), Image.LANCZOS)
                logger.info(f"Task {self.request.id}: Resized image to height {height}, calculated width: {new_width}")

            # --- Determine Output Format and Handle Transparency ---
            # If target_format is provided, use it. Otherwise, default to original format.
            output_format = target_format.upper() if target_format else original_format

            # Fallback for unrecognized original formats or if output_format is still None
            if output_format is None or output_format.upper() not in [choice[0] for choice in job.FORMAT_CHOICES]:
                output_format = 'JPEG' # Default fallback to a universally supported format
                logger.info(f"Task {self.request.id}: Output format not explicitly determined or not supported. Defaulting to JPEG.")
            else:
                output_format = output_format.upper() # Ensure uppercase for PIL

            logger.info(f"Task {self.request.id}: Final output format determined as: {output_format}")


            # Handle RGBA (transparency) conversion if saving as JPEG (JPEG does not support transparency)
            if output_format == 'JPEG' and processed_img.mode == 'RGBA':
                logger.info(f"Task {self.request.id}: Converting RGBA image to RGB for JPEG save (filling transparency with white).")
                background = Image.new('RGB', processed_img.size, (255, 255, 255)) # White background
                background.paste(processed_img, (0, 0), processed_img) # Paste image onto background
                processed_img = background
            # If converting to PNG and it's not already RGBA but could benefit from it (e.g., from original RGBA)
            elif output_format == 'PNG' and processed_img.mode != 'RGBA' and 'A' in img.mode:
                # This ensures if original had alpha, PNG output keeps it
                processed_img = processed_img.convert('RGBA')
                logger.info(f"Task {self.request.id}: Ensuring PNG output is RGBA if original had alpha channel.")
            elif output_format == 'GIF' and processed_img.mode == 'RGBA':
                # GIF supports transparency but needs specific handling for palette mode
                # Convert to P mode (palette) with transparency
                logger.info(f"Task {self.request.id}: Converting RGBA image to P (palette) for GIF save with transparency.")
                processed_img = processed_img.convert('P', palette=Image.ADAPTIVE, colors=256)
                alpha = img.getchannel('A') # Get alpha channel from original image
                mask = Image.eval(alpha, lambda x: 255 if x > 128 else 0) # Create a mask for transparency
                processed_img.info['transparency'] = processed_img.getpixel((0,0)) # Or find a better transparent color
            
            # General conversion for other formats if the mode is incompatible
            # For example, if saving a JPEG (RGB) to PNG (RGBA)
            if output_format == 'PNG' and processed_img.mode == 'RGB' and 'A' in img.mode:
                 # If original was RGBA, and we processed it to RGB (e.g., from resize preserving RGB only),
                 # and now want PNG output, ensure it becomes RGBA
                 processed_img = processed_img.convert('RGBA')
                 logger.info(f"Task {self.request.id}: Converted processed image to RGBA for PNG output to preserve alpha.")
            elif output_format == 'WEBP' and processed_img.mode == 'RGBA':
                # WebP supports transparency, convert to RGBA explicitly if needed
                processed_img = processed_img.convert('RGBA')
                logger.info(f"Task {self.request.id}: Converted processed image to RGBA for WebP output (supports alpha).")


            # --- Define Output File Path ---
            base_filename = os.path.splitext(os.path.basename(file_path_relative_to_media_root))[0]
            # Ensure a clean filename, avoiding multiple dots if original had them
            output_filename = f"processed_{base_filename}.{output_format.lower()}"

            # Directory for processed files, unique per job to avoid conflicts
            output_dir_relative_to_media_root = os.path.join('image_tool_processed', str(job.id))
            output_full_absolute_path = os.path.join(settings.MEDIA_ROOT, output_dir_relative_to_media_root, output_filename)

            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(output_full_absolute_path), exist_ok=True)
            logger.info(f"Task {self.request.id}: Saving processed image locally to: {output_full_absolute_path}")

            # --- Save Processed Image ---
            save_params = {}
            if output_format == 'JPEG':
                # Apply quality for JPEG. Default to 85 if not specified for compression.
                save_params['quality'] = quality if quality is not None else 85
                save_params['optimize'] = True
                logger.info(f"Task {self.request.id}: Saving as JPEG with quality={save_params['quality']}")
            elif output_format == 'PNG':
                # Pillow PNG save handles compression automatically to a good default.
                # 'quality' in PNG usually refers to compression level (0-9).
                # If you want to map 0-100 quality to PNG compression, you can do so:
                if quality is not None:
                    # Map 0-100 to 9-0 (higher quality = lower compression level)
                    save_params['compress_level'] = 9 - round(quality / 100 * 9)
                    logger.info(f"Task {self.request.id}: Saving as PNG with compress_level={save_params['compress_level']}")
            elif output_format == 'WEBP':
                # WebP also supports quality parameter
                save_params['quality'] = quality if quality is not None else 85
                save_params['lossless'] = False # Default to lossy compression
                logger.info(f"Task {self.request.id}: Saving as WebP with quality={save_params['quality']}")
            elif output_format == 'GIF':
                # GIF options, e.g., duration for animations, optimize for smaller size
                save_params['optimize'] = True
                logger.info(f"Task {self.request.id}: Saving as GIF (optimized).")
            # For other formats like BMP, TIFF, no specific quality parameter is typically needed by default.

            processed_img.save(output_full_absolute_path, format=output_format, **save_params)
            logger.info(f"Task {self.request.id}: Processed image successfully saved.")

            # --- Update Job with Output URL ---
            # Construct the URL accessible via HTTP
            download_url = os.path.join(settings.MEDIA_URL, output_dir_relative_to_media_root, output_filename)
            logger.info(f"Task {self.request.id}: Generated download URL: {download_url}")

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
        logger.error(f"Task {self.request.id}: An unexpected error occurred during image processing for job {job_id}: {e}", exc_info=True)
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