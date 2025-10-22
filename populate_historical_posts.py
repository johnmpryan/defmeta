import os
import django
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import logging
from logger_config import setup_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, Post
from reddit_oauth import get_reddit_client

# Set up logging
logger = setup_logger(__name__)

def get_posts_for_date_range(start_date_str, end_date_str, subreddit_filter=None):
    """
    Populate posts for all tracked subreddits within date range.
    
    Args:
        start_date_str: 'YYYY-MM-DD'
        end_date_str: 'YYYY-MM-DD' (inclusive)
        subreddit_filter: Optional - specific subreddit name to process
    """
    reddit = get_reddit_client()
    
    # Parse dates
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # Get subreddits to process
    if subreddit_filter:
        subreddits = Subreddit.objects.filter(name=subreddit_filter)
    else:
        subreddits = Subreddit.objects.all()
    
    logger.info(f"Starting post collection for {start_date} to {end_date}")
    logger.info(f"Processing {subreddits.count()} subreddits")
    
    total_posts_saved = 0
    
    for subreddit_obj in subreddits:
        try:
            # Use timezone from database, fallback to Eastern if not set
            timezone_str = subreddit_obj.timezone or 'America/New_York'
            tz = ZoneInfo(timezone_str)
            
            logger.info(f"Processing r/{subreddit_obj.name} (timezone: {timezone_str})")
            
            # Get Reddit subreddit object
            subreddit = reddit.subreddit(subreddit_obj.name)
            
            # Process each date in range
            current_date = start_date
            while current_date <= end_date:
                posts_saved = process_date_for_subreddit(
                    subreddit, 
                    subreddit_obj, 
                    current_date, 
                    tz
                )
                total_posts_saved += posts_saved
                current_date += timedelta(days=1)
                
        except Exception as e:
            logger.error(f"Error processing r/{subreddit_obj.name}: {e}")
            continue
    
    logger.info(f"Completed: Saved {total_posts_saved} total posts")
    return total_posts_saved

def process_date_for_subreddit(reddit_subreddit, db_subreddit, target_date, tz):
    """
    Process posts for a specific subreddit on a specific date.
    
    Returns:
        Number of posts saved
    """
    # Calculate date boundaries in local timezone
    start_of_day_local = datetime.combine(target_date, time.min, tzinfo=tz)
    end_of_day_local = datetime.combine(target_date, time.max, tzinfo=tz)
    
    start_timestamp = start_of_day_local.timestamp()
    end_timestamp = end_of_day_local.timestamp()
    
    posts_saved = 0
    posts_skipped = 0
    posts_checked = 0
    
    try:
        # Fetch posts from Reddit (newest first)
        # Limit to reasonable number to avoid timeout
        for post in reddit_subreddit.new(limit=1000):
            posts_checked += 1
            
            # Check if post is within our date range
            if start_timestamp <= post.created_utc <= end_timestamp:
                # Convert UTC timestamp to datetime objects
                utc_time = datetime.fromtimestamp(post.created_utc, ZoneInfo('UTC'))
                local_time = utc_time.astimezone(tz)
                
                # Use get_or_create to avoid duplicates
                post_obj, created = Post.objects.get_or_create(
                    reddit_id=post.id,
                    defaults={
                        'subreddit': db_subreddit,
                        'title': post.title[:500],  # Truncate very long titles
                        'author': str(post.author) if post.author else '[deleted]',
                        'body': post.selftext if post.selftext else None,
                        'url': post.url,
                        'is_self': post.is_self,
                        'permalink': post.permalink,
                        'over_18': post.over_18,
                        'spoiler': post.spoiler,
                        'stickied': post.stickied,
                        'locked': post.locked,
                        'link_flair_text': post.link_flair_text if hasattr(post, 'link_flair_text') else None,
                        'distinguished': post.distinguished if hasattr(post, 'distinguished') else None,
                        'created_utc': utc_time,
                        'created_local': local_time,
                        'engagement_collected': False,
                        'is_removed': False,
                    }
                )
                
                if created:
                    posts_saved += 1
                else:
                    posts_skipped += 1
                    
            elif post.created_utc < start_timestamp:
                # Posts are in reverse chronological order, so we can stop
                break
                
            # Stop if we've checked too many posts (prevents hanging on large subreddits)
            if posts_checked > 2000:
                logger.warning(f"Reached post limit for r/{db_subreddit.name} on {target_date}")
                break
    
    except Exception as e:
        logger.error(f"Error fetching posts for r/{db_subreddit.name} on {target_date}: {e}")
    
    if posts_saved > 0 or posts_skipped > 0:
        logger.info(f"  {target_date} - r/{db_subreddit.name}: {posts_saved} saved, {posts_skipped} skipped")
    
    return posts_saved

def backfill_all_historical():
    """
    Convenience function to backfill based on existing SubredditDailyStats data.
    Useful after initially populating the Post table.
    """
    from django.db import models
    
    # Get date range from existing snapshots
    date_range = SubredditDailyStats.objects.aggregate(
        min_date=models.Min('date_created'),
        max_date=models.Max('date_created')
    )
    
    if not date_range['min_date']:
        logger.info("No existing snapshots to determine date range")
        return
    
    # Use dates from snapshots
    start_date = date_range['min_date'].date()
    end_date = date_range['max_date'].date()
    
    logger.info(f"Backfilling posts from {start_date} to {end_date} based on existing snapshots")
    
    # Convert to string format for the main function
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    return get_posts_for_date_range(start_str, end_str)

def main():
    """
    Main function to populate posts for a date range.
    Edit the dates below to populate different ranges.
    """
    # EDIT THESE DATES for manual runs
    # Or comment out and use backfill_all_historical() instead
    
    # Option 1: Specific date range
    start_date = "2025-10-06"  
    end_date = "2025-10-20"
    get_posts_for_date_range(start_date, end_date)
    
    # Option 2: Backfill based on existing snapshots
    # backfill_all_historical()

if __name__ == "__main__":
    main()