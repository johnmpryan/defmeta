import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Post
posts = Post.objects.all()[:5]
for p in posts:
    print(f"Reddit created: {p.created_utc}, DB created: {p.date_created}")