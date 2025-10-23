import os
import django
from datetime import datetime, timedelta, UTC

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats
from reddit_oauth import get_subreddit_stats_oauth, get_reddit_client
from logger_config import setup_logger

logger = setup_logger('backfill_snapshots')

def get_posts_for_date(subreddit_name, target_date):
    """
    Get post count for a specific date.
    
    Args:
        subreddit_name: Name of subreddit (without r/)
        target_date: datetime.date object for the target day
    
    Returns:
        Number of posts created on that date, or None if error
    """
    try:
        reddit = get_reddit_client()
        subreddit = reddit.subreddit(subreddit_name)
        
        # Define time range for target date (start of day to end of day in UTC)
        start_of_day = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC)
        end_of_day = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=UTC)
        
        start_timestamp = int(start_of_day.timestamp())
        end_timestamp = int(end_of_day.timestamp())
        
        # Search for posts in this time range
        post_count = 0
        for post in subreddit.new(limit=None):
            post_time = datetime.fromtimestamp(post.created_utc, tz=UTC)
            
            if post_time < start_of_day:
                # We've gone past our target date
                break
            
            if start_of_day <= post_time <= end_of_day:
                post_count += 1
        
        return post_count
        
    except Exception as e:
        logger.error(f"Error fetching posts for r/{subreddit_name} on {target_date}: {e}")
        return None

def backfill_snapshots(days_back=14):
    """
    Backfill snapshots for the last N days.
    
    Args:
        days_back: Number of days to backfill (default 14 for 2 weeks)
    """
    all_subreddits = Subreddit.objects.all()
    today = datetime.now(UTC).date()
    
    logger.info(f"Starting backfill for {all_subreddits.count()} subreddits, going back {days_back} days")
    
    for subreddit in all_subreddits:
        logger.info(f"\nProcessing r/{subreddit.name}")
        
        # Get current subscriber count (will be same for all backfilled records)
        subreddit_data = get_subreddit_stats_oauth(subreddit.name)
        current_subscribers = None
        if subreddit_data and subreddit.name in subreddit_data:
            current_subscribers = subreddit_data[subreddit.name].get('subscribers_count')
        
        if current_subscribers is None:
            logger.warning(f"Could not fetch subscriber count for r/{subreddit.name}, skipping")
            continue
        
        # Iterate through each day going backwards
        for day_offset in range(days_back, 0, -1):
            target_date = today - timedelta(days=day_offset)
            
            # Check if snapshot already exists
            existing = SubredditDailyStats.objects.filter(
                subreddit=subreddit,
                date_created__date=target_date
            ).first()
            
            if existing:
                logger.info(f"  {target_date}: Snapshot already exists, skipping")
                continue
            
            # Get post count for this specific date
            logger.info(f"  {target_date}: Fetching post count...")
            post_count = get_posts_for_date(subreddit.name, target_date)
            
            if post_count is not None:
                # Create snapshot with historical date
                snapshot = SubredditDailyStats(
                    subreddit=subreddit,
                    subscribers_count=current_subscribers,
                    posts_count=post_count
                )
                snapshot.save()
                
                # Manually set date_created to historical date
                SubredditDailyStats.objects.filter(pk=snapshot.pk).update(
                    date_created=datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC)
                )
                
                logger.info(f"  {target_date}: Created snapshot - {current_subscribers} subscribers, {post_count} posts")
            else:
                logger.warning(f"  {target_date}: Failed to fetch post count")
    
    logger.info("\nBackfill complete!")

if __name__ == "__main__":
    # Backfill last 14 days (2 weeks)
    backfill_snapshots(days_back=7)