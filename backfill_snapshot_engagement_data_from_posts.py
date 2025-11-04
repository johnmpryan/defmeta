"""
Updated backfill script to calculate post_count, total_comments, total_estimated_upvotes 
and total_estimated_downvotes for existing SubredditDailyStats records.
"""

import os
import django
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db.models import Sum, Count, Q

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats, Post
import logging
from logger_config import setup_logger

logger = setup_logger(__name__)

def backfill_snapshot_metrics():
    """
    Calculate all aggregated metrics for snapshots by summing Post data.
    Updates: posts_count, total_comments, total_estimated_upvotes, total_estimated_downvotes
    """
    logger.info("Starting backfill of all metrics for snapshots")
    
    # Get all snapshots that might need updating
    # Check for 0 values OR NULL values in any of the aggregate fields
    snapshots = SubredditDailyStats.objects.filter(
        Q(total_estimated_upvotes=0) | Q(total_estimated_upvotes__isnull=True) |
        Q(posts_count=0) | Q(posts_count__isnull=True) |
        Q(total_comments=0) | Q(total_comments__isnull=True)
    ).select_related('subreddit').order_by('date_created')
    
    total_snapshots = snapshots.count()
    logger.info(f"Found {total_snapshots} snapshots to check for backfill")
    
    updated_count = 0
    skipped_count = 0
    no_posts_count = 0
    
    for snapshot in snapshots:
        try:
            subreddit = snapshot.subreddit
            
            # Use timezone from database, fallback to Eastern if not set
            timezone_str = subreddit.timezone or 'America/New_York'
            tz = ZoneInfo(timezone_str)
            
            # Get the date of the snapshot (in the subreddit's timezone)
            snapshot_date_utc = snapshot.date_created
            snapshot_date_local = snapshot_date_utc.astimezone(tz).date()
            
            # Calculate the day before (since snapshots collect yesterday's data)
            target_date = snapshot_date_local - timedelta(days=1)
            
            # Get start and end of that day in local time
            start_of_day_local = datetime.combine(target_date, time.min, tzinfo=tz)
            end_of_day_local = datetime.combine(target_date, time.max, tzinfo=tz)
            
            # Convert to UTC for querying
            start_of_day_utc = start_of_day_local.astimezone(ZoneInfo('UTC'))
            end_of_day_utc = end_of_day_local.astimezone(ZoneInfo('UTC'))
            
            # Aggregate ALL metrics from posts for that day
            # Don't filter by estimated_upvotes being non-null - we want post count regardless
            post_metrics = Post.objects.filter(
                subreddit=subreddit,
                created_utc__gte=start_of_day_utc,
                created_utc__lte=end_of_day_utc
            ).aggregate(
                post_count=Count('id'),
                total_comments=Sum('num_comments'),
                total_up=Sum('estimated_upvotes'),
                total_down=Sum('estimated_downvotes')
            )
            
            # Check if we found any posts
            if post_metrics['post_count'] == 0:
                no_posts_count += 1
                logger.debug(f"No posts found for {subreddit.name} on {target_date}")
                continue
            
            # Update snapshot with all metrics
            new_post_count = post_metrics['post_count'] or 0
            new_comments = post_metrics['total_comments'] or 0
            new_upvotes = post_metrics['total_up'] or 0
            new_downvotes = post_metrics['total_down'] or 0
            
            # Update all fields
            snapshot.posts_count = new_post_count
            snapshot.total_comments = new_comments
            snapshot.total_estimated_upvotes = new_upvotes
            snapshot.total_estimated_downvotes = new_downvotes
            
            snapshot.save(update_fields=[
                'posts_count', 
                'total_comments',
                'total_estimated_upvotes', 
                'total_estimated_downvotes'
            ])
            
            updated_count += 1
            
            if updated_count % 10 == 0:
                logger.info(f"Progress: {updated_count} snapshots updated")
            
            # Log first few updates as examples
            if updated_count <= 3:
                logger.info(f"  {subreddit.name} on {target_date}: "
                           f"{new_post_count} posts, "
                           f"{new_comments} comments, "
                           f"up={new_upvotes}, down={new_downvotes}")
            
        except Exception as e:
            logger.error(f"Error processing snapshot {snapshot.id}: {e}")
            skipped_count += 1
            continue
    
    logger.info(f"Backfill complete:")
    logger.info(f"  - {updated_count} snapshots updated with metrics")
    logger.info(f"  - {no_posts_count} snapshots had no posts in database")
    logger.info(f"  - {skipped_count} snapshots skipped or errored")
    
    # Verify results
    snapshots_with_data = SubredditDailyStats.objects.filter(
        posts_count__gt=0,
        total_estimated_upvotes__gt=0
    ).count()
    logger.info(f"Total snapshots now with post counts > 0: {snapshots_with_data}")
    
    # Show some examples of updated snapshots
    logger.info("\nSample of updated snapshots:")
    samples = SubredditDailyStats.objects.filter(
        posts_count__gt=0
    ).order_by('-total_estimated_upvotes')[:5]
    
    for sample in samples:
        logger.info(f"  {sample.subreddit.name} ({sample.date_created.date()}): "
                   f"{sample.posts_count} posts, {sample.total_comments} comments, "
                   f"up={sample.total_estimated_upvotes}, down={sample.total_estimated_downvotes}")

if __name__ == "__main__":
    backfill_snapshot_metrics()