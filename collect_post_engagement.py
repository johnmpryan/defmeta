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

def calculate_estimated_votes(score, upvote_ratio):
    """
    Calculate estimated upvotes and downvotes from score and upvote_ratio.
    
    Returns tuple of (estimated_upvotes, estimated_downvotes) or (None, None) if cannot calculate.
    """
    if score is None or upvote_ratio is None or upvote_ratio == 0.5:
        return None, None
    
    try:
        total_votes = score / (2 * upvote_ratio - 1)
        estimated_upvotes = round(total_votes * upvote_ratio)
        estimated_downvotes = round(total_votes * (1 - upvote_ratio))
        return estimated_upvotes, estimated_downvotes
    except (ZeroDivisionError, ValueError) as e:
        logger.warning(f"Could not calculate votes - score: {score}, ratio: {upvote_ratio}, error: {e}")
        return None, None

def collect_engagement_for_three_day_old_posts():
    """
    Collect engagement metrics for posts that are 3 days old.
    Updates score, upvote_ratio, num_comments, and calculated vote estimates.
    """
    reddit = get_reddit_client()
    
    # Get posts from 3 days ago using created_local (DateField)
    target_date = datetime.now(UTC).date() - timedelta(days=3)
    
    # Convert to list upfront to prevent QuerySet re-evaluation during iteration
    posts_to_update = list(Post.objects.filter(
        engagement_collected=False,
        created_local=target_date
    ).order_by('created_utc'))
    
    total_posts = len(posts_to_update)
    logger.info(f"Found {total_posts} posts from {target_date} needing engagement data")
    
    updated_count = 0
    removed_count = 0
    error_count = 0
    
    # Process in batches for progress logging
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
                    
                    # Calculate estimated votes
                    est_up, est_down = calculate_estimated_votes(submission.score, submission.upvote_ratio)
                    post.estimated_upvotes = est_up
                    post.estimated_downvotes = est_down
                    
                    post.engagement_collected = True
                    post.save()
                    
                    updated_count += 1
                    
                except:
                    # Post was removed or deleted
                    post.is_removed = True
                    post.engagement_collected = True
                    post.score = 0
                    post.num_comments = 0
                    post.estimated_upvotes = 0
                    post.estimated_downvotes = 0
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
    collect_engagement_for_three_day_old_posts()

if __name__ == "__main__":
    main()