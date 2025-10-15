import os
import django
from datetime import datetime, timedelta, UTC

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats
from reddit_oauth import get_reddit_client
from logger_config import setup_logger

logger = setup_logger('backfill_engagement')

def backfill_engagement_data(days_back=14):
    """
    Backfill engagement metrics for snapshots from the last N days.
    
    Args:
        days_back: Number of days to backfill (default 14)
    """
    reddit = get_reddit_client()
    today = datetime.now(UTC).date()
    
    logger.info(f"Starting engagement backfill for last {days_back} days")
    
    for day_offset in range(days_back, 0, -1):
        target_date = today - timedelta(days=day_offset)
        
        # Find snapshots from this date that haven't collected engagement yet
        snapshots = SubredditDailyStats.objects.filter(
            date_created__date=target_date,
            engagement_collected=False
        )
        
        if not snapshots.exists():
            logger.info(f"{target_date}: No snapshots to process")
            continue
        
        logger.info(f"{target_date}: Processing {snapshots.count()} snapshots")
        
        for snapshot in snapshots:
            subreddit_name = snapshot.subreddit.name
            logger.info(f"  r/{subreddit_name}")
            
            try:
                subreddit = reddit.subreddit(subreddit_name)
                posts_from_that_day = []
                
                # Fetch recent posts and filter to that specific day
                for post in subreddit.new(limit=100):
                    post_date = datetime.fromtimestamp(post.created_utc, UTC).date()
                    if post_date == target_date:
                        posts_from_that_day.append(post)
                    elif post_date < target_date:
                        break
                
                if not posts_from_that_day:
                    logger.info(f"    No posts found from {target_date}")
                    snapshot.engagement_collected = True
                    snapshot.save()
                    continue
                
                # Calculate aggregates
                total_score = sum(post.score for post in posts_from_that_day)
                total_ratio = sum(post.upvote_ratio for post in posts_from_that_day)
                total_comments = sum(post.num_comments for post in posts_from_that_day)
                post_count = len(posts_from_that_day)
                
                avg_score = total_score / post_count
                avg_ratio = total_ratio / post_count
                
                # Update the snapshot
                snapshot.avg_post_score = avg_score
                snapshot.avg_upvote_ratio = avg_ratio
                snapshot.total_comments = total_comments
                snapshot.engagement_collected = True
                snapshot.save()
                
                logger.info(f"    {post_count} posts, avg score={avg_score:.1f}, avg ratio={avg_ratio:.2f}, {total_comments} comments")
                
            except Exception as e:
                logger.error(f"    Error processing r/{subreddit_name}: {e}")
                continue
    
    logger.info("Engagement backfill complete")

if __name__ == "__main__":
    # Backfill last 14 days
    backfill_engagement_data(days_back=7)