# Import the requests library to make HTTP requests
import requests

def get_subreddit_subscribers(subreddit_name):
    """Fetch subscriber count for a given subreddit."""
    
    # Build the URL for Reddit's JSON API endpoint
    # The /about.json endpoint returns subreddit metadata
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
        
        # Extract the subscriber count from the nested data structure
        # Structure: data['data']['subscribers']
        subscribers = data['data'].get('subscribers', None)
        active_users = data['data'].get('active_user_count', None)
        
        # Return the subscriber count
        return subscribers
    
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
    subreddit = "louisiana"

    # Specify multiple subreddits to check
    subreddits = ["kentucky", "louisiana"]
    
    # Call the function to get subscriber count
    subscribers_count = get_subreddit_subscribers(subreddit)
    
    # Print the result with comma formatting for readability
    # Example: 50000 displays as "50,000"
    print(f"r/{subreddit} has {subscribers_count} subscribers")
    
    print("Script complete.")