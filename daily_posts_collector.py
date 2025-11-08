import os
import django
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, Post
from reddit_oauth import get_reddit_client
import logging
from logger_config import setup_logger

logger = setup_logger(__name__)

def collect_yesterday_posts():
    """
    Collect all posts from yesterday for each tracked subreddit.
    Respects timezone for each state to get accurate 'yesterday'.
    """
    reddit = get_reddit_client()
    
    # Get all subreddits
    subreddits = Subreddit.objects.all()
    
    logger.info(f"Starting daily post collection for {subreddits.count()} subreddits")
    
    total_posts_saved = 0
    total_errors = 0
    
    for subreddit_obj in subreddits:
        try:
            # Use timezone from database, fallback to Eastern if not set
            timezone_str = subreddit_obj.timezone or 'America/New_York'
            tz = ZoneInfo(timezone_str)
            
            # Calculate yesterday in the subreddit's timezone
            now_local = datetime.now(tz)
            yesterday = (now_local - timedelta(days=1)).date()
            
            # Get start and end of yesterday in local time
            start_of_day_local = datetime.combine(yesterday, time.min, tzinfo=tz)
            end_of_day_local = datetime.combine(yesterday, time.max, tzinfo=tz)
            
            start_timestamp = start_of_day_local.timestamp()
            end_timestamp = end_of_day_local.timestamp()
            
            logger.info(f"Collecting posts for r/{subreddit_obj.name} from {yesterday}")
            
            # Get Reddit subreddit object
            subreddit = reddit.subreddit(subreddit_obj.name)
            
            posts_saved = 0
            posts_skipped = 0
            posts_checked = 0
            
            # Fetch recent posts
            for post in subreddit.new(limit=500):  # Usually enough to cover 24 hours
                posts_checked += 1
                
                # Check if post is from yesterday
                if start_timestamp <= post.created_utc <= end_timestamp:
                    # Convert UTC timestamp to datetime objects
                    utc_time = datetime.fromtimestamp(post.created_utc, ZoneInfo('UTC'))
                    local_time = utc_time.astimezone(tz).date()  # Add .date() to get just the date
                    
                    # Create post record
                    post_obj, created = Post.objects.get_or_create(
                        reddit_id=post.id,
                        defaults={
                            'subreddit': subreddit_obj,
                            'title': post.title[:500],
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
                    # Posts are newest first, so we've gone past yesterday
                    break
            
            if posts_saved > 0 or posts_skipped > 0:
                logger.info(f"  r/{subreddit_obj.name}: {posts_saved} new, {posts_skipped} existing")
            
            total_posts_saved += posts_saved
            
        except Exception as e:
            logger.error(f"Error collecting posts for r/{subreddit_obj.name}: {e}")
            total_errors += 1
            continue
    
    logger.info(f"Daily collection complete: {total_posts_saved} posts saved, {total_errors} errors")
    return total_posts_saved

def main():
    """
    Main function for daily post collection.
    """
    collect_yesterday_posts()

if __name__ == "__main__":
    main()