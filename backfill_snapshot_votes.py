"""
Backfill script to calculate total_estimated_upvotes and total_estimated_downvotes
for existing SubredditDailyStats records by aggregating from Post table.
"""

import os
import django
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db.models import Sum

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats, Post
import logging
from logger_config import setup_logger

logger = setup_logger(__name__)

def backfill_snapshot_votes():
    """
    Calculate total estimated votes for all existing snapshots by summing Post votes.
    """
    logger.info("Starting backfill of total estimated votes for snapshots")
    
    # Get all snapshots that don't have total votes calculated yet
    snapshots = SubredditDailyStats.objects.filter(
        total_estimated_upvotes__isnull=True
    ).select_related('subreddit').order_by('date_created')
    
    total_snapshots = snapshots.count()
    logger.info(f"Found {total_snapshots} snapshots to backfill")
    
    updated_count = 0
    skipped_count = 0
    
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
            
            # Aggregate votes from posts for that day
            vote_totals = Post.objects.filter(
                subreddit=subreddit,
                created_utc__gte=start_of_day_utc,
                created_utc__lte=end_of_day_utc,
                estimated_upvotes__isnull=False,
                estimated_downvotes__isnull=False
            ).aggregate(
                total_up=Sum('estimated_upvotes'),
                total_down=Sum('estimated_downvotes')
            )
            
            # Update snapshot with totals (will be None if no posts with votes)
            snapshot.total_estimated_upvotes = vote_totals['total_up'] or 0
            snapshot.total_estimated_downvotes = vote_totals['total_down'] or 0
            snapshot.save(update_fields=['total_estimated_upvotes', 'total_estimated_downvotes'])
            
            updated_count += 1
            
            if updated_count % 50 == 0:
                logger.info(f"Progress: {updated_count}/{total_snapshots} snapshots updated")
            
            # Log example for first few
            if updated_count <= 3:
                post_count = Post.objects.filter(
                    subreddit=subreddit,
                    created_utc__gte=start_of_day_utc,
                    created_utc__lte=end_of_day_utc
                ).count()
                logger.info(f"  {subreddit.name} on {target_date}: "
                           f"{post_count} posts, "
                           f"up={snapshot.total_estimated_upvotes}, "
                           f"down={snapshot.total_estimated_downvotes}")
            
        except Exception as e:
            logger.error(f"Error processing snapshot {snapshot.id}: {e}")
            skipped_count += 1
            continue
    
    logger.info(f"Backfill complete: {updated_count} updated, {skipped_count} errors")
    
    # Verify results
    snapshots_with_totals = SubredditDailyStats.objects.filter(
        total_estimated_upvotes__isnull=False
    ).count()
    logger.info(f"Total snapshots with vote totals: {snapshots_with_totals}")
    
    # Show some examples
    logger.info("Sample of updated snapshots:")
    samples = SubredditDailyStats.objects.filter(
        total_estimated_upvotes__isnull=False,
        total_estimated_upvotes__gt=0
    ).order_by('-total_estimated_upvotes')[:5]
    
    for sample in samples:
        logger.info(f"  {sample.subreddit.name} ({sample.date_created.date()}): "
                   f"up={sample.total_estimated_upvotes}, down={sample.total_estimated_downvotes}")

if __name__ == "__main__":
    backfill_snapshot_votes()