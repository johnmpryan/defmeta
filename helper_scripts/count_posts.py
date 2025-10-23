import requests
from datetime import datetime, timedelta, UTC

def get_recent_post_count(subreddit_name):
    """Count posts from yesterday (previous calendar day)."""
    
    # Get yesterday's date range (midnight to midnight in UTC)
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today - timedelta(days=1)
    yesterday_end = today
    
    start_timestamp = yesterday_start.timestamp()
    end_timestamp = yesterday_end.timestamp()
    
    url = f"https://www.reddit.com/r/{subreddit_name}/new.json"
    headers = {'User-Agent': 'PostCounter/1.0'}
    params = {'limit': 100}
    
    post_count = 0
    after = None
    
    try:
        # Keep fetching until we hit posts older than yesterday
        while True:
            if after:
                params['after'] = after
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            posts = data['data']['children']
            
            # No more posts to fetch
            if not posts:
                break
            
            # Count posts within yesterday's timeframe
            found_old_post = False
            for post in posts:
                created = post['data']['created_utc']
                # Check if post was created yesterday
                if start_timestamp <= created < end_timestamp:
                    post_count += 1
                elif created < start_timestamp:
                    found_old_post = True
            
            # Stop if we've gone past yesterday
            if found_old_post:
                break
            
            # Get pagination token for next page
            after = data['data']['after']
            if not after:
                break
        
        return post_count
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching posts for {subreddit_name}: {e}")
        return None  # Return None instead of error string
    except KeyError as e:
        print(f"Error parsing data for {subreddit_name}: {e}")
        return None  # Return None instead of error string

if __name__ == "__main__":
    print("Fetching post count...")
    
    subreddit = "kentucky"
    count = get_recent_post_count(subreddit)
    
    if count is not None:
        print(f"\nr/{subreddit} had {count} posts yesterday")
    else:
        print(f"\nFailed to get post count for r/{subreddit}")