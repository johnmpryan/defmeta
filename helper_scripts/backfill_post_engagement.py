import os
import django
from datetime import datetime, timedelta, UTC

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Post
from reddit_oauth import get_reddit_client
import logging
from logger_config import setup_logger

logger = setup_logger(__name__)

def backfill_engagement_for_date_range(start_date_str=None, end_date_str=None):
    """
    Backfill engagement data for posts in a date range.
    Only processes posts at least 3 days old.
    
    Args:
        start_date_str: 'YYYY-MM-DD' - start of range (optional)
        end_date_str: 'YYYY-MM-DD' - end of range (optional)
    """
    reddit = get_reddit_client()
    
    # Build query
    three_days_ago = datetime.now(UTC) - timedelta(days=3)
    posts_query = Post.objects.filter(
        engagement_collected=False,
        created_utc__lte=three_days_ago
    )
    
    # Add date range filters if provided
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=UTC)
        posts_query = posts_query.filter(created_utc__gte=start_date)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').replace(tzinfo=UTC) + timedelta(days=1)
        posts_query = posts_query.filter(created_utc__lt=end_date)
    
    posts_to_update = posts_query.order_by('created_utc')
    total_posts = posts_to_update.count()
    
    logger.info(f"Found {total_posts} posts needing engagement data")
    
    updated_count = 0
    removed_count = 0
    error_count = 0
    
    for i, post in enumerate(posts_to_update):
        try:
            # Fetch current metrics from Reddit
            submission = reddit.submission(id=post.reddit_id)
            
            # Check if post still exists
            try:
                _ = submission.score  # This will fail if post is removed
                
                # Update engagement metrics
                post.score = submission.score
                post.upvote_ratio = submission.upvote_ratio
                post.num_comments = submission.num_comments
                post.engagement_collected = True
                post.save()
                
                updated_count += 1
                
            except:
                # Post was likely removed
                post.is_removed = True
                post.engagement_collected = True
                post.save()
                removed_count += 1
            
            # Progress indicator
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i+1}/{total_posts} posts processed")
                
        except Exception as e:
            error_count += 1
            logger.error(f"Error updating post {post.reddit_id}: {e}")
            continue
    
    logger.info(f"Complete: {updated_count} updated, {removed_count} removed, {error_count} errors")
    return updated_count + removed_count

def main():
    """
    Main function - edit dates or leave empty to process all eligible posts.
    """
    # Option 1: Process ALL posts that are 3+ days old and need engagement
    # backfill_engagement_for_date_range()
    
    # Option 2: Process specific date range (uncomment and edit dates)
    backfill_engagement_for_date_range("2025-10-06", "2025-10-17")

if __name__ == "__main__":
    main()