import os
import django
from datetime import datetime, UTC

# Django setup - required before importing models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from reddit_oauth import get_reddit_client

def count_posts_for_date(subreddit_name, target_date_str):
    """
    Count posts from a specific date in a subreddit.
    
    Args:
        subreddit_name: Name of subreddit without 'r/' (example: 'python')
        target_date_str: Date string in format 'YYYY-MM-DD' (example: '2025-10-15')
    
    Returns:
        Integer count of posts from that date
    """
    # Step 1: Get authenticated Reddit client
    reddit = get_reddit_client()
    
    # Step 2: Parse the date string into a date object
    # This converts '2025-10-15' into a date we can compare against
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    print(f"Searching r/{subreddit_name} for posts from {target_date}")
    
    # Step 3: Get the subreddit object from Reddit
    subreddit = reddit.subreddit(subreddit_name)
    
    # Step 4: Initialize counter
    post_count = 0
    
    # Step 5: Fetch newest posts and filter to our target date
    # limit=None means "get as many as possible" (Reddit API limits this to ~1000)
    print("Fetching posts...")
    for post in subreddit.new(limit=None):
        # Convert post's Unix timestamp to a date object
        post_date = datetime.fromtimestamp(post.created_utc, UTC).date()
        
        # If post is from our target date, count it
        if post_date == target_date:
            post_count += 1
        
        # If we've gone past our target date, stop searching
        # Posts are returned newest-first, so once we see an older date, we're done
        elif post_date < target_date:
            break
    
    # Step 6: Return the result
    print(f"Found {post_count} posts from {target_date}")
    return post_count

if __name__ == "__main__":
    # Example usage - modify these values to test different dates/subreddits
    subreddit = "Kentucky"  # Change this to any subreddit
    date = "2025-10-14"     # Change this to any date (YYYY-MM-DD format)
    
    count = count_posts_for_date(subreddit, date)
    print(f"\nResult: {count} posts")