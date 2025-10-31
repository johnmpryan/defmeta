"""
Modified backfill script to calculate total_estimated_upvotes and total_estimated_downvotes
for existing SubredditDailyStats records that have 0 values (not NULL).
"""

import os
import django
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.db.models import Sum, Q

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats, Post
import logging
from logger_config import setup_logger

logger = setup_logger(__name__)

def backfill_snapshot_votes():
    """
    Calculate total estimated votes for snapshots with 0 values by summing Post votes.
    """
    logger.info("Starting backfill of total estimated votes for snapshots with 0 values")
    
    # Get all snapshots that have 0 for upvotes (likely means they need recalculation)
    # Also check if posts_count > 0 to avoid processing empty days
    snapshots = SubredditDailyStats.objects.filter(
        Q(total_estimated_upvotes=0) | Q(total_estimated_upvotes__isnull=True),
        posts_count__gt=0  # Only process if there were actually posts that day
    ).select_related('subreddit').order_by('date_created')
    
    total_snapshots = snapshots.count()
    logger.info(f"Found {total_snapshots} snapshots to backfill")
    
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
            
            # First check if posts exist for this date with vote data
            posts_with_votes = Post.objects.filter(
                subreddit=subreddit,
                created_utc__gte=start_of_day_utc,
                created_utc__lte=end_of_day_utc,
                estimated_upvotes__isnull=False,
                estimated_downvotes__isnull=False
            ).count()
            
            if posts_with_votes == 0:
                no_posts_count += 1
                logger.debug(f"No posts with vote data for {subreddit.name} on {target_date}")
                continue
            
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
            
            # Update snapshot with totals
            new_upvotes = vote_totals['total_up'] or 0
            new_downvotes = vote_totals['total_down'] or 0
            
            # Only update if we found actual votes
            if new_upvotes > 0 or new_downvotes > 0:
                snapshot.total_estimated_upvotes = new_upvotes
                snapshot.total_estimated_downvotes = new_downvotes
                snapshot.save(update_fields=['total_estimated_upvotes', 'total_estimated_downvotes'])
                
                updated_count += 1
                
                if updated_count % 10 == 0:
                    logger.info(f"Progress: {updated_count} snapshots updated")
                
                # Log first few updates as examples
                if updated_count <= 3:
                    logger.info(f"  {subreddit.name} on {target_date}: "
                               f"{posts_with_votes} posts, "
                               f"up={new_upvotes}, down={new_downvotes}")
            else:
                skipped_count += 1
            
        except Exception as e:
            logger.error(f"Error processing snapshot {snapshot.id}: {e}")
            skipped_count += 1
            continue
    
    logger.info(f"Backfill complete:")
    logger.info(f"  - {updated_count} snapshots updated with vote totals")
    logger.info(f"  - {no_posts_count} snapshots had no posts with vote data")
    logger.info(f"  - {skipped_count} snapshots skipped or errored")
    
    # Verify results
    snapshots_with_totals = SubredditDailyStats.objects.filter(
        total_estimated_upvotes__gt=0
    ).count()
    logger.info(f"Total snapshots now with vote totals > 0: {snapshots_with_totals}")
    
    # Show some examples
    logger.info("\nSample of updated snapshots:")
    samples = SubredditDailyStats.objects.filter(
        total_estimated_upvotes__gt=0
    ).order_by('-total_estimated_upvotes')[:5]
    
    for sample in samples:
        logger.info(f"  {sample.subreddit.name} ({sample.date_created.date()}): "
                   f"up={sample.total_estimated_upvotes}, down={sample.total_estimated_downvotes}")

if __name__ == "__main__":
    backfill_snapshot_votes()