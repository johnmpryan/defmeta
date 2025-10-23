import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit
from reddit_oauth import get_subreddit_stats_oauth

# Fetch the data
# Original set: subreddits_to_fetch = ['kentucky','tennessee','WestVirginia','Indiana','ohio','NorthCarolina','Arkansas','missouri','illinois','louisiana','alabama','oregon','Oklahoma','Connecticut','utah','nevada','minnesota']
subreddits_to_fetch = ['Maine', 'NewHampshire', 'Vermont', 'massachusetts', 'RhodeIsland', 'newyork', 'pennsylvania', 'newjersey','Delaware', 'maryland', 'Virginia', 'SouthCarolina', 'georgia', 'florida', 'Michigan', 'wisconsin', 'Iowa', 'NorthDakota', 'SouthDakota', 'nebraska', 'kansas', 'texas', 'NewMexico', 'Colorado', 'wyoming', 'Montana', 'Idaho', 'california', 'washington', 'arizona','Alaska', 'hawaii']

for subreddit in subreddits_to_fetch:
    print(f"Processing {subreddit}...")
    stats = get_subreddit_stats_oauth(subreddit)
    
    # Check if we got valid data (a dictionary with the expected structure)
    if not isinstance(stats, dict) or subreddit not in stats:
        print(f"  ✗ Failed to fetch data for {subreddit}")
        print(f"      Response was: {stats}")  # Add this line
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