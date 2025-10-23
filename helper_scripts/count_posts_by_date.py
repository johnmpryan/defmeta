import os
import django
from datetime import datetime, time
from zoneinfo import ZoneInfo

# Django setup - required before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from reddit_oauth import get_reddit_client

def count_posts_for_date(subreddit_name, target_date_str, timezone_str='America/New_York'):
    """
    Count posts from a specific date in a subreddit, using a specific timezone.
    
    Args:
        subreddit_name: Name of subreddit without 'r/' (example: 'Kentucky')
        target_date_str: Date string in format 'YYYY-MM-DD' (example: '2025-10-14')
        timezone_str: IANA timezone string (example: 'America/New_York' for Eastern)
                      For Pacific: 'America/Los_Angeles'
                      For Central: 'America/Chicago'
                      For Mountain: 'America/Denver'
    
    Returns:
        Integer count of posts from that date in the specified timezone
    """
    # Step 1: Get authenticated Reddit client
    reddit = get_reddit_client()
    
    # Step 2: Create timezone object
    # This handles daylight saving time automatically
    tz = ZoneInfo(timezone_str)
    
    # Step 3: Parse the date string and create start/end boundaries
    # We want the full 24-hour period in the LOCAL timezone
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    
    # Create datetime for start of day in local timezone (midnight)
    start_of_day_local = datetime.combine(target_date, time.min, tzinfo=tz)
    
    # Create datetime for end of day in local timezone (11:59:59 PM)
    end_of_day_local = datetime.combine(target_date, time.max, tzinfo=tz)
    
    # Convert both to UTC timestamps (what Reddit uses)
    # This is the key step - we're translating "October 14 Eastern" to UTC boundaries
    start_utc_timestamp = start_of_day_local.timestamp()
    end_utc_timestamp = end_of_day_local.timestamp()
    
    print(f"Searching r/{subreddit_name} for posts from {target_date} ({timezone_str})")
    print(f"  Local time range: {start_of_day_local} to {end_of_day_local}")
    print(f"  UTC equivalent: {datetime.fromtimestamp(start_utc_timestamp, ZoneInfo('UTC'))} to {datetime.fromtimestamp(end_utc_timestamp, ZoneInfo('UTC'))}")
    
    # Step 4: Get the subreddit object from Reddit
    subreddit = reddit.subreddit(subreddit_name)
    
    # Step 5: Initialize counter
    post_count = 0
    
    # Step 6: Fetch newest posts and filter by timestamp
    print("Fetching posts...")
    for post in subreddit.new(limit=None):
        # Check if post's UTC timestamp falls within our local day's UTC boundaries
        if start_utc_timestamp <= post.created_utc <= end_utc_timestamp:
            post_count += 1
        
        # If we've gone past our target date range, stop searching
        # Posts are returned newest-first, so once we're before the start time, we're done
        elif post.created_utc < start_utc_timestamp:
            break
    
    # Step 7: Return the result
    print(f"Found {post_count} posts from {target_date} in {timezone_str}")
    return post_count

if __name__ == "__main__":
    # Example usage - modify these values to test different dates/subreddits/timezones
    
    # Eastern timezone example
    subreddit = "python"
    date = "2025-10-16"
    timezone = "America/New_York"  # Eastern time
    
    # Pacific timezone example (uncomment to use):
    # subreddit = "California"
    # date = "2025-10-14"
    # timezone = "America/Los_Angeles"  # Pacific time
    
    count = count_posts_for_date(subreddit, date, timezone)
    print(f"\nResult: {count} posts")