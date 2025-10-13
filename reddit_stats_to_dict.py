# Import the requests library to make HTTP requests
import requests

def get_subreddit_stats(subreddit_name):
    """Fetch statistics for a given subreddit and return as a dictionary."""
    
    # Build the URL for Reddit's JSON API endpoint. The /about.json endpoint returns subreddit metadata
    url = f"https://www.reddit.com/r/{subreddit_name}/about.json"
    
    # Set a User-Agent header (Reddit requires this to identify your app)
    headers = {'User-Agent': 'SubredditStats/1.0'}
    
    try:
        # Make GET request to Reddit's API
        response = requests.get(url, headers=headers)
        
        # Raise an exception if the request failed (4xx or 5xx status codes)
        response.raise_for_status()
        
        # Parse the JSON response into a Python dictionary
        data = response.json()
        
        # Extract subscriber count and active user count
        # Use .get() to return None if field doesn't exist
        subscribers_count = data['data'].get('subscribers', None)
        name = data['data'].get('display_name', None)
        uri = data['data'].get('url', None)

        
        # Create dictionary with subreddit name as key
        # and stats as nested dictionary
        stats_dict = {
            subreddit_name: {
                "name": name,
                "subscribers_count": subscribers_count,
                "uri": uri,
            }
        }
        
        # Return the dictionary
        return stats_dict
    
    # Catch any network-related errors (connection issues, timeouts, etc.)
    except requests.exceptions.RequestException as e:
        return f"Error fetching data: {e}"
    
    # Catch errors if the expected data structure isn't found
    except KeyError:
        return "Error: Could not find subscriber data"

# This block only runs when the script is executed directly
# (not when imported as a module)
if __name__ == "__main__":
    print("Starting script...")
    
    # Specify which subreddit to check
    subreddit = "kentucky"
    
    # Call the function to get stats dictionary
    stats = get_subreddit_stats(subreddit)
    
    # Print the complete dictionary
    print(f"\nSubreddit stats: {stats}")
    
    # Print formatted output
    if isinstance(stats, dict) and subreddit in stats:
        print(f"\nr/{subreddit}:")
        
        # Handle None values in formatting
        name = stats[subreddit]['name']
        subs = stats[subreddit]['subscribers_count']
        
        print(f"{name}  Subscribers: {subs:,}" if subs is not None else "  Subscribers: NULL")
    
    print("\nScript complete.")