import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit
from reddit_stats_to_dict import get_subreddit_stats

# Fetch the data
subreddits_to_fetch = ['kentucky','tennessee','WestVirginia','Indiana','ohio','NorthCarolina','Arkansas','missouri','illinois','louisiana','alabama','oregon','Oklahoma','Connecticut','utah','nevada','minnesota']

for subreddit in subreddits_to_fetch:
    print(f"Processing {subreddit}...")
    stats = get_subreddit_stats(subreddit)
    
    # Check if we got valid data (a dictionary with the expected structure)
    if not isinstance(stats, dict) or subreddit not in stats:
        print(f"  ✗ Failed to fetch data for {subreddit}")
        continue
    
    # Ensure subreddit exists in reference table
    subreddit_obj, created = Subreddit.objects.get_or_create(
        name=stats[subreddit]['name'],
        defaults={
            'uri': stats[subreddit]['uri'],
            'subreddit_description': stats[subreddit].get('subreddit_description', None)
        }
    )
    
    if created:
        print(f"  ✓ {subreddit} created successfully!")
    else:
        print(f"  ✓ {subreddit} already exists")

print("\nSubreddit setup complete!")