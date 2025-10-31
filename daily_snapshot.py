import os
import django
from datetime import datetime, timedelta, time, UTC
from zoneinfo import ZoneInfo
from django.db.models import Sum, Count
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats, Post
from reddit_oauth import get_subreddit_stats_oauth
from logger_config import setup_logger

logger = setup_logger('daily_snapshot')

def collect_daily_snapshot(test_mode=False, test_date=None, test_subreddit=None):
    """
    Collect daily snapshot for all tracked subreddits
    
    Args:
        test_mode: If True, run in test mode with specific date/subreddit
        test_date: Date string in YYYY-MM-DD format (for test mode)
        test_subreddit: Subreddit name (for test mode)
    """
    
    # Parse test date if provided
    if test_mode and test_date:
        try:
            target_date = datetime.strptime(test_date, '%Y-%m-%d').date()
            logger.info(f"TEST MODE: Running for date {target_date}")
        except ValueError:
            logger.error(f"Invalid date format: {test_date}. Use YYYY-MM-DD")
            return
    else:
        target_date = datetime.now(UTC).date()
    
    # Filter subreddits if test mode
    if test_mode and test_subreddit:
        all_subreddits = Subreddit.objects.filter(name=test_subreddit)
        if not all_subreddits.exists():
            logger.error(f"Subreddit '{test_subreddit}' not found in database")
            return
        logger.info(f"TEST MODE: Running for r/{test_subreddit}")
    else:
        all_subreddits = Subreddit.objects.all()
    
    logger.info(f"Starting snapshot collection for {all_subreddits.count()} subreddits on {target_date}")
    
    for subreddit in all_subreddits:
        logger.info(f"Processing r/{subreddit.name}")
        
        # Get subscriber count from Reddit API
        subreddit_data = get_subreddit_stats_oauth(subreddit.name)
        subscribers = None
        if subreddit_data and subreddit.name in subreddit_data:
            subscribers = subreddit_data[subreddit.name].get('subscribers_count')
        
        # Get post metrics from our Post table for yesterday (or target date)
        # Use timezone from database, fallback to Eastern if not set
        timezone_str = subreddit.timezone or 'America/New_York'
        tz = ZoneInfo(timezone_str)
        
        # Calculate the date to query posts for
        if test_mode and test_date:
            # In test mode, get posts from the day before target_date
            query_date = target_date - timedelta(days=1)
        else:
            # Normal mode: yesterday in the subreddit's timezone
            now_local = datetime.now(tz)
            query_date = (now_local - timedelta(days=1)).date()
        
        # Get start and end of query date in local time
        start_of_day_local = datetime.combine(query_date, time.min, tzinfo=tz)
        end_of_day_local = datetime.combine(query_date, time.max, tzinfo=tz)
        
        # Convert to UTC for querying
        start_of_day_utc = start_of_day_local.astimezone(ZoneInfo('UTC'))
        end_of_day_utc = end_of_day_local.astimezone(ZoneInfo('UTC'))
        
        logger.info(f"Querying posts from {query_date} ({timezone_str})")
        
        # Query Post table for metrics
        post_metrics = Post.objects.filter(
            subreddit=subreddit,
            created_utc__gte=start_of_day_utc,
            created_utc__lte=end_of_day_utc
        ).aggregate(
            post_count=Count('id'),
            total_upvotes=Sum('estimated_upvotes'),
            total_downvotes=Sum('estimated_downvotes'),
            total_comments=Sum('num_comments')
        )
        
        post_count = post_metrics['post_count'] or 0
        total_upvotes = post_metrics['total_upvotes'] or 0
        total_downvotes = post_metrics['total_downvotes'] or 0
        total_comments = post_metrics['total_comments'] or 0
        
        # Only save if we got at least one metric
        if subscribers is not None or post_count > 0:
            # Get or create snapshot for target date
            snapshot, created = SubredditDailyStats.objects.get_or_create(
                subreddit=subreddit,
                date_created__date=target_date,
                defaults={
                    'subscribers_count': subscribers,
                    'posts_count': post_count,
                    'total_estimated_upvotes': total_upvotes,
                    'total_estimated_downvotes': total_downvotes,
                    'total_comments': total_comments
                }
            )
            
            if created:
                logger.info(f"Created snapshot: {subscribers} subscribers, {post_count} posts, "
                          f"up={total_upvotes}, down={total_downvotes}, comments={total_comments}")
            else:
                # Update existing snapshot
                snapshot.subscribers_count = subscribers
                snapshot.posts_count = post_count
                snapshot.total_estimated_upvotes = total_upvotes
                snapshot.total_estimated_downvotes = total_downvotes
                snapshot.total_comments = total_comments
                snapshot.save()
                logger.info(f"Updated existing snapshot: {subscribers} subscribers, {post_count} posts, "
                          f"up={total_upvotes}, down={total_downvotes}, comments={total_comments}")
        else:
            logger.warning(f"No data retrieved for r/{subreddit.name}")

    logger.info("Snapshot collection complete")


if __name__ == "__main__":
    # Check for command line arguments for test mode
    # Usage: python daily_snapshot.py test 2025-10-20 kentucky
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_date = sys.argv[2] if len(sys.argv) > 2 else None
        test_subreddit = sys.argv[3] if len(sys.argv) > 3 else None
        
        if not test_date:
            print("Usage: python daily_snapshot.py test YYYY-MM-DD [subreddit_name]")
            print("Example: python daily_snapshot.py test 2025-10-20 kentucky")
            sys.exit(1)
        
        collect_daily_snapshot(test_mode=True, test_date=test_date, test_subreddit=test_subreddit)
    else:
        # Normal mode
        collect_daily_snapshot()