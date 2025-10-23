import os
import django
from datetime import datetime, time
from zoneinfo import ZoneInfo

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from reddit_oauth import get_reddit_client

def list_posts_for_date(subreddit_name, target_date_str, timezone_str='America/New_York'):
    """
    List all posts from a specific date with timestamps.
    
    Args:
        subreddit_name: Subreddit name without 'r/'
        target_date_str: Date string 'YYYY-MM-DD'
        timezone_str: IANA timezone string (default: Eastern)
    """
    reddit = get_reddit_client()
    
    # Setup timezone and date boundaries
    tz = ZoneInfo(timezone_str)
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    
    start_of_day_local = datetime.combine(target_date, time.min, tzinfo=tz)
    end_of_day_local = datetime.combine(target_date, time.max, tzinfo=tz)
    
    start_timestamp = start_of_day_local.timestamp()
    end_timestamp = end_of_day_local.timestamp()
    
    # Get subreddit
    subreddit = reddit.subreddit(subreddit_name)
    
    print(f"\nPosts from r/{subreddit_name} on {target_date_str} ({timezone_str})")
    print("=" * 80)
    
    # Fetch and display posts
    post_count = 0
    for post in subreddit.new(limit=None):
        if start_timestamp <= post.created_utc <= end_timestamp:
            post_count += 1
            
            # Convert UTC timestamp to UTC datetime, then to Eastern
            utc_time = datetime.fromtimestamp(post.created_utc, ZoneInfo('UTC'))
            eastern_time = utc_time.astimezone(tz)
            
            print(f"\nPost #{post_count}")
            print(f"UTC Time:     {utc_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"Eastern Time: {eastern_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"Title:        {post.title}")
            
        elif post.created_utc < start_timestamp:
            break
    
    print("\n" + "=" * 80)
    print(f"Total posts: {post_count}")

if __name__ == "__main__":
    # Modify these values
    subreddit = "python"
    date = "2025-10-16"
    timezone = "America/New_York"
    
    list_posts_for_date(subreddit, date, timezone)