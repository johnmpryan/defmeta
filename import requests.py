import requests
from datetime import datetime, timedelta

def get_recent_post_count(subreddit_name, days=14):
    """Count posts from the last X days in a subreddit."""
    
    # Calculate cutoff timestamp (2 weeks ago)
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    cutoff_timestamp = cutoff_date.timestamp()
    
    url = f"https://www.reddit.com/r/{subreddit_name}/new.json"
    headers = {'User-Agent': 'PostCounter/1.0'}
    params = {'limit': 100}
    
    post_count = 0
    after = None
    
    try:
        # Keep fetching until we hit posts older than cutoff
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
            
            # Count posts within timeframe
            found_old_post = False
            for post in posts:
                created = post['data']['created_utc']
                if created >= cutoff_timestamp:
                    post_count += 1
                else:
                    found_old_post = True
            
            # Stop if we've gone past the 2-week mark
            if found_old_post:
                break
            
            # Get pagination token for next page
            after = data['data']['after']
            if not after:
                break
        
        return post_count
    
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"
    except KeyError as e:
        return f"Error parsing data: {e}"

if __name__ == "__main__":
    print("Fetching post count...")
    
    subreddit = "kentucky"
    count = get_recent_post_count(subreddit, days=14)
    
    print(f"\nr/{subreddit} has had {count} posts in the last 2 weeks")