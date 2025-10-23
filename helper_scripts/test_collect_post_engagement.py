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

def collect_engagement_for_three_day_old_posts():
    """
    Collect engagement metrics for posts that are 3 days old.
    Updates score, upvote_ratio, and num_comments.
    """
    reddit = get_reddit_client()
    
    # Calculate date range for 3-day-old posts (with some buffer)
    now = datetime.now(UTC)
    three_days_ago_start = now - timedelta(days=3, hours=2)  # 2 hour buffer
    three_days_ago_end = now - timedelta(days=2, hours=22)   # 2 hour buffer
    
    # Find posts from 3 days ago that need engagement data
    posts_to_update = Post.objects.filter(
        engagement_collected=False,
        created_utc__gte=three_days_ago_start,
        created_utc__lt=three_days_ago_end
    ).order_by('created_utc')
    
    total_posts = posts_to_update.count()
    logger.info(f"Found {total_posts} posts from 3 days ago needing engagement data")
    
    updated_count = 0
    removed_count = 0
    error_count = 0
    
    # Process in batches to avoid memory issues
    batch_size = 100
    
    for i in range(0, total_posts, batch_size):
        batch = posts_to_update[i:i+batch_size]
        
        for post in batch:
            try:
                # Fetch current metrics from Reddit
                submission = reddit.submission(id=post.reddit_id)
                
                # Try to access score to check if post exists
                try:
                    _ = submission.score
                    
                    # Post exists - update engagement metrics
                    post.score = submission.score
                    post.upvote_ratio = submission.upvote_ratio
                    post.num_comments = submission.num_comments
                    post.engagement_collected = True
                    post.save()
                    
                    updated_count += 1
                    
                except:
                    # Post was removed or deleted
                    post.is_removed = True
                    post.engagement_collected = True
                    post.score = 0  # Set to 0 for removed posts
                    post.num_comments = 0
                    post.save()
                    
                    removed_count += 1
                    logger.info(f"Post {post.reddit_id} marked as removed")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error updating post {post.reddit_id}: {e}")
                continue
        
        # Log progress
        processed = min(i + batch_size, total_posts)
        logger.info(f"Progress: {processed}/{total_posts} posts processed")
    
    logger.info(f"Engagement collection complete:")
    logger.info(f"  - {updated_count} posts updated with metrics")
    logger.info(f"  - {removed_count} posts marked as removed")
    logger.info(f"  - {error_count} errors")
    
    return updated_count + removed_count

def main():
    """
    Main function for engagement collection.
    """
    collect_engagement_for_three_day_old_posts()

if __name__ == "__main__":
    main()