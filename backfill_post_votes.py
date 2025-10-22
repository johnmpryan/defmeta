"""
Backfill script to calculate estimated_upvotes and estimated_downvotes 
for existing Posts that have engagement data.
"""

import os
import django
from datetime import datetime
import logging
from logger_config import setup_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Post

# Set up logging
logger = setup_logger(__name__)

def calculate_estimated_votes(score, upvote_ratio):
    """
    Calculate estimated upvotes and downvotes from score and upvote_ratio.
    
    Returns tuple of (estimated_upvotes, estimated_downvotes) or (None, None) if cannot calculate.
    """
    # Check if we can calculate (avoiding division by zero)
    if score is None or upvote_ratio is None or upvote_ratio == 0.5:
        return None, None
    
    try:
        # Calculate total votes using the formula
        total_votes = score / (2 * upvote_ratio - 1)
        
        # Calculate estimated upvotes and downvotes
        estimated_upvotes = round(total_votes * upvote_ratio)
        estimated_downvotes = round(total_votes * (1 - upvote_ratio))
        
        return estimated_upvotes, estimated_downvotes
    except (ZeroDivisionError, ValueError) as e:
        logger.warning(f"Could not calculate votes - score: {score}, ratio: {upvote_ratio}, error: {e}")
        return None, None

def backfill_post_votes():
    """
    Backfill estimated_upvotes and estimated_downvotes for all Posts with engagement data.
    """
    logger.info("Starting backfill of estimated votes for Posts")
    
    # Get posts with engagement data but no estimated votes
    posts_to_update = Post.objects.filter(
        engagement_collected=True,
        score__isnull=False,
        upvote_ratio__isnull=False,
        estimated_upvotes__isnull=True  # Not yet calculated
    )
    
    total_posts = posts_to_update.count()
    logger.info(f"Found {total_posts} posts to backfill")
    
    updated_count = 0
    skipped_count = 0
    
    # Process in batches for memory efficiency
    batch_size = 1000
    
    for i in range(0, total_posts, batch_size):
        batch = posts_to_update[i:i+batch_size]
        posts_to_save = []
        
        for post in batch:
            estimated_up, estimated_down = calculate_estimated_votes(post.score, post.upvote_ratio)
            
            if estimated_up is not None and estimated_down is not None:
                post.estimated_upvotes = estimated_up
                post.estimated_downvotes = estimated_down
                posts_to_save.append(post)
                updated_count += 1
            else:
                skipped_count += 1
                logger.debug(f"Skipped post {post.reddit_id} - cannot calculate votes")
        
        # Bulk update for efficiency
        if posts_to_save:
            Post.objects.bulk_update(posts_to_save, ['estimated_upvotes', 'estimated_downvotes'])
            logger.info(f"Processed batch {i//batch_size + 1}: Updated {len(posts_to_save)} posts")
    
    logger.info(f"Backfill complete: Updated {updated_count} posts, skipped {skipped_count}")
    
    # Verify the update
    posts_with_estimates = Post.objects.filter(
        estimated_upvotes__isnull=False,
        estimated_downvotes__isnull=False
    ).count()
    
    logger.info(f"Total posts with estimated votes: {posts_with_estimates}")
    
    # Show some examples
    logger.info("Sample of updated posts:")
    sample_posts = Post.objects.filter(
        estimated_upvotes__isnull=False
    ).order_by('-score')[:5]
    
    for post in sample_posts:
        logger.info(f"  {post.reddit_id}: score={post.score}, ratio={post.upvote_ratio:.2f}, "
                   f"up={post.estimated_upvotes}, down={post.estimated_downvotes}")

if __name__ == "__main__":
    backfill_post_votes()