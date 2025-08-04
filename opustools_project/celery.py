import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'opustools_project.settings')

app = Celery('opustools_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


from celery.schedules import crontab
app.conf.beat_schedule = {
    'delete-old-media-files-daily': {
        'task': 'image_tool.tasks.cleanup_old_media',
        'schedule': crontab(hour=0, minute=0),  # every day at midnight
    },
}