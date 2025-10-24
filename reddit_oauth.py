import praw
import os
from dotenv import load_dotenv

load_dotenv()

def get_reddit_client():
    """Create and return authenticated Reddit client."""
    reddit = praw.Reddit(
        client_id=os.environ.get('REDDIT_CLIENT_ID'),
        client_secret=os.environ.get('REDDIT_CLIENT_SECRET'),
        user_agent=os.environ.get('REDDIT_USER_AGENT')
    )
    return reddit

def get_subreddit_stats_oauth(subreddit_name):
    """Fetch subreddit stats using OAuth."""
    try:
        reddit = get_reddit_client()
        subreddit = reddit.subreddit(subreddit_name)
        
        return {
            subreddit_name: {
                'name': subreddit.display_name,
                'subscribers_count': subreddit.subscribers,
                'uri': f'/r/{subreddit.display_name}/',
                'subreddit_description': subreddit.public_description
            }
        }
    except Exception as e:
        print(f"Error fetching {subreddit_name}: {e}")
        return None

def get_recent_post_count_oauth(subreddit_name):
    """Count posts from yesterday using OAuth."""
    from datetime import datetime, timedelta, UTC
    
    try:
        reddit = get_reddit_client()
        subreddit = reddit.subreddit(subreddit_name)
        
        # Get yesterday's date range
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today - timedelta(days=1)
        yesterday_end = today
        
        start_timestamp = yesterday_start.timestamp()
        end_timestamp = yesterday_end.timestamp()
        
        # Count posts from yesterday
        post_count = 0
        for submission in subreddit.new(limit=None):
            if start_timestamp <= submission.created_utc < end_timestamp:
                post_count += 1
            elif submission.created_utc < start_timestamp:
                break  # Stop when we hit older posts
        
        return post_count
    except Exception as e:
        print(f"Error fetching posts for {subreddit_name}: {e}")
        return None

if __name__ == "__main__":
    print("Testing OAuth connection...")
    
    # Test 1: Subreddit stats
    result = get_subreddit_stats_oauth('python')
    if result:
        print("✓ Subreddit stats working!")
        print(f"Result: {result}")
    else:
        print("✗ Subreddit stats failed")
    
    # Test 2: Post count
    print("\nTesting post count...")
    count = get_recent_post_count_oauth('python')
    if count is not None:
        print(f"✓ Post count working!")
        print(f"Yesterday's posts in r/python: {count}")
    else:
        print("✗ Post count failed")