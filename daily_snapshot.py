import os
import django
from datetime import datetime, timedelta, time, UTC
from zoneinfo import ZoneInfo
from django.db.models import Sum, Count

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats, Post
from reddit_oauth import get_subreddit_stats_oauth
from logger_config import setup_logger

logger = setup_logger('daily_snapshot')

def collect_daily_snapshot():
    """Collect daily snapshot for all tracked subreddits"""
    
    all_subreddits = Subreddit.objects.all()
    today = datetime.now(UTC).date()
    
    logger.info(f"Starting snapshot collection for {all_subreddits.count()} subreddits on {today}")
    
    for subreddit in all_subreddits:
        logger.info(f"Processing r/{subreddit.name}")
        
        # Get subscriber count from Reddit API
        subreddit_data = get_subreddit_stats_oauth(subreddit.name)
        subscribers = None
        if subreddit_data and subreddit.name in subreddit_data:
            subscribers = subreddit_data[subreddit.name].get('subscribers_count')
        
        # Get post metrics from our Post table for yesterday
        # Use timezone from database, fallback to Eastern if not set
        timezone_str = subreddit.timezone or 'America/New_York'
        tz = ZoneInfo(timezone_str)
        
        # Calculate yesterday in the subreddit's timezone
        now_local = datetime.now(tz)
        yesterday = (now_local - timedelta(days=1)).date()
        
        # Get start and end of yesterday in local time
        start_of_day_local = datetime.combine(yesterday, time.min, tzinfo=tz)
        end_of_day_local = datetime.combine(yesterday, time.max, tzinfo=tz)
        
        # Convert to UTC for querying
        start_of_day_utc = start_of_day_local.astimezone(ZoneInfo('UTC'))
        end_of_day_utc = end_of_day_local.astimezone(ZoneInfo('UTC'))
        
        # Query Post table for yesterday's metrics
        post_metrics = Post.objects.filter(
            subreddit=subreddit,
            created_utc__gte=start_of_day_utc,
            created_utc__lte=end_of_day_utc
        ).aggregate(
            post_count=Count('id'),
            total_upvotes=Sum('estimated_upvotes'),
            total_downvotes=Sum('estimated_downvotes')
        )
        
        post_count = post_metrics['post_count'] or 0
        total_upvotes = post_metrics['total_upvotes'] or 0
        total_downvotes = post_metrics['total_downvotes'] or 0
        
        # Only save if we got at least one metric
        if subscribers is not None or post_count > 0:
            # Get or create snapshot for today
            snapshot, created = SubredditDailyStats.objects.get_or_create(
                subreddit=subreddit,
                date_created__date=today,
                defaults={
                    'subscribers_count': subscribers,
                    'posts_count': post_count,
                    'total_estimated_upvotes': total_upvotes,
                    'total_estimated_downvotes': total_downvotes
                }
            )
            
            if created:
                logger.info(f"Created snapshot: {subscribers} subscribers, {post_count} posts, "
                          f"up={total_upvotes}, down={total_downvotes}")
            else:
                # Update existing snapshot
                snapshot.subscribers_count = subscribers
                snapshot.posts_count = post_count
                snapshot.total_estimated_upvotes = total_upvotes
                snapshot.total_estimated_downvotes = total_downvotes
                snapshot.save()
                logger.info(f"Updated existing snapshot: {subscribers} subscribers, {post_count} posts, "
                          f"up={total_upvotes}, down={total_downvotes}")
        else:
            logger.warning(f"No data retrieved for r/{subreddit.name}")

    logger.info("Snapshot collection complete")


if __name__ == "__main__":
    collect_daily_snapshot()