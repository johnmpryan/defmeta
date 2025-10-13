import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit
from reddit_stats_to_dict import get_subreddit_stats

# Fetch the data
subreddits_to_fetch = ['politics','lexington','pensacola']

for subreddit in subreddits_to_fetch:
    stats = get_subreddit_stats(subreddit)
    #Ensure subreddit exists in reference table
    subreddit_obj, created = Subreddit.objects.get_or_create(
        name=stats[subreddit]['name'],
        defaults={
            'uri': stats[subreddit]['uri'],
            'subreddit_description': stats[subreddit].get('subreddit_description', None)
        }
    )
    if created:
        print(f"{subreddit} created successfully!")
    else:
        print(f"{subreddit} already created.")

