import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats
from reddit_oauth import get_subreddit_stats_oauth
from reddit_oauth import get_recent_post_count_oauth

# Get all subreddits from the database
all_subreddits = Subreddit.objects.all()

for subreddit in all_subreddits:
    print(f"Processing {subreddit.name}...")
    
    # Fetch data from both APIs
    subreddit_data = get_subreddit_stats_oauth(subreddit.name)
    post_count = get_recent_post_count_oauth(subreddit.name)
    
    # Extract subscriber count safely (returns None if API failed or structure is wrong)
    subscribers = None
    if subreddit_data and subreddit.name in subreddit_data:
        subscribers = subreddit_data[subreddit.name].get('subscribers_count')
    
    # post_count is already an integer or None if it failed
    posts = post_count
    
    # Only create snapshot if we got at least one metric
    if subscribers is not None or posts is not None:
        SubredditDailyStats.objects.create(
            subreddit=subreddit,
            subscribers_count=subscribers,
            posts_count=posts
        )
        print(f"  ✓ Snapshot saved (subs: {subscribers}, posts: {posts})")
    else:
        print(f"  ✗ Skipped - both API calls failed")

print("\nSnapshot collection complete!")