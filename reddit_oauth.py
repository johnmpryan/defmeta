import praw
import os

def get_reddit_client():
    """Create and return authenticated Reddit client."""
    reddit = praw.Reddit(
        client_id=os.environ.get('REDDIT_CLIENT_ID', '4sT2zBYhcKpAKFLt5u7oGA'),
        client_secret=os.environ.get('REDDIT_CLIENT_SECRET', 'WBF4KirnHrVSWQFB4VWn64iYZpMSfQ'),
        user_agent='SubredditStats/1.0 by goddamn2fa'  # Change YourUsername
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

if __name__ == "__main__":
    print("Testing OAuth connection...")
    
    # Test with a simple subreddit
    result = get_subreddit_stats_oauth('python')
    
    if result:
        print("✓ OAuth working!")
        print(f"Result: {result}")
    else:
        print("✗ OAuth failed")