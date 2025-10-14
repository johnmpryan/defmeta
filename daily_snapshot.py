import os
import django
from datetime import datetime, timedelta, UTC

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats
from reddit_oauth import get_subreddit_stats_oauth, get_recent_post_count_oauth

def collect_daily_snapshot():
    """Collect daily snapshot for all tracked subreddits"""
    
    all_subreddits = Subreddit.objects.all()
    today = datetime.now(UTC).date()
    
    print(f"Collecting snapshots for {all_subreddits.count()} subreddits on {today}")
    
    for subreddit in all_subreddits:
        print(f"\nProcessing r/{subreddit.name}...")
        
        # Fetch data
        subreddit_data = get_subreddit_stats_oauth(subreddit.name)
        post_count = get_recent_post_count_oauth(subreddit.name)
        
        # Extract values
        subscribers = None
        if subreddit_data and subreddit.name in subreddit_data:
            subscribers = subreddit_data[subreddit.name].get('subscribers_count')
        
        # Only save if we got at least one metric
        if subscribers is not None or post_count is not None:
            # Get or create snapshot for today
            snapshot, created = SubredditDailyStats.objects.get_or_create(
                subreddit=subreddit,
                date_created__date=today,
                defaults={
                    'subscribers_count': subscribers,
                    'posts_count': post_count
                }
            )
            
            if created:
                print(f"  ✓ Created snapshot: {subscribers} subscribers, {post_count} posts")
            else:
                # Update existing snapshot
                snapshot.subscribers_count = subscribers
                snapshot.posts_count = post_count
                snapshot.save()
                print(f"  ↻ Updated existing snapshot: {subscribers} subscribers, {post_count} posts")
        else:
            print(f"  ✗ No data retrieved")

if __name__ == "__main__":
    collect_daily_snapshot()