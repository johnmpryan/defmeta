"""
Daily script to update recent snapshots with aggregated post metrics.
Designed to run on Heroku Scheduler after engagement data is collected.
"""

import os
import django
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from django.db.models import Sum, Count
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import SubredditDailyStats, Post
import logging
from logger_config import setup_logger

logger = setup_logger(__name__)

def update_recent_snapshots(days_back=4):
    """
    Update snapshots from recent days with aggregated post metrics.
    Default is to update snapshots from 3-4 days ago when engagement data is ready.
    
    Args:
        days_back: How many days back to check for snapshots needing updates (default 4)
    """
    # Calculate date range
    # We want snapshots from 3-4 days ago since those have mature engagement data
    today = timezone.now().date()
    date_range_end = today - timedelta(days=3)
    date_range_start = today - timedelta(days=days_back)
    
    # Get snapshots in this range
    snapshots = SubredditDailyStats.objects.filter(
        date_created__date__gte=date_range_start,
        date_created__date__lte=date_range_end
    ).select_related('subreddit')
    
    logger.info(f"Updating {snapshots.count()} snapshots from {date_range_start} to {date_range_end}")
    
    updated_count = 0
    no_change_count = 0
    error_count = 0
    
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
            
            # Aggregate all metrics from posts
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
            
            # Get new values
            new_post_count = post_metrics['post_count'] or 0
            new_comments = post_metrics['total_comments'] or 0
            new_upvotes = post_metrics['total_up'] or 0
            new_downvotes = post_metrics['total_down'] or 0
            
            # Check if update is needed (compare with current values)
            needs_update = (
                snapshot.posts_count != new_post_count or
                snapshot.total_comments != new_comments or
                snapshot.total_estimated_upvotes != new_upvotes or
                snapshot.total_estimated_downvotes != new_downvotes
            )
            
            if needs_update:
                # Update snapshot
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
                logger.info(f"Updated {subreddit.name} ({snapshot_date_local}): "
                           f"{new_post_count} posts, {new_comments} comments, "
                           f"up={new_upvotes}, down={new_downvotes}")
            else:
                no_change_count += 1
                logger.debug(f"No changes needed for {subreddit.name} ({snapshot_date_local})")
                
        except Exception as e:
            error_count += 1
            logger.error(f"Error updating snapshot {snapshot.id}: {e}")
            continue
    
    # Summary
    logger.info(f"Daily snapshot update complete:")
    logger.info(f"  - {updated_count} snapshots updated")
    logger.info(f"  - {no_change_count} snapshots already had correct data")
    logger.info(f"  - {error_count} errors")
    
    return updated_count

if __name__ == "__main__":
    # When run directly, update last 4 days of snapshots
    update_recent_snapshots(days_back=4)