"""
Improved backfill script with explicit updates and better diagnostics
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
    
    # Get ALL posts with score and ratio (not just ones missing estimates)
    posts_to_check = Post.objects.filter(
        score__isnull=False,
        upvote_ratio__isnull=False
    ).exclude(
        upvote_ratio=0.5  # Exclude the problematic ratio
    )
    
    total_posts = posts_to_check.count()
    logger.info(f"Found {total_posts} posts to check")
    
    updated_count = 0
    skipped_count = 0
    already_had_count = 0
    
    # Process individually for better tracking
    for i, post in enumerate(posts_to_check):
        # Skip if already has non-zero estimates (indicating real calculation)
        if (post.estimated_upvotes is not None and post.estimated_upvotes > 0) or \
           (post.estimated_downvotes is not None and post.estimated_downvotes > 0):
            already_had_count += 1
            continue
                
        estimated_up, estimated_down = calculate_estimated_votes(post.score, post.upvote_ratio)
        
        if estimated_up is not None and estimated_down is not None:
            post.estimated_upvotes = estimated_up
            post.estimated_downvotes = estimated_down
            post.save(update_fields=['estimated_upvotes', 'estimated_downvotes'])
            updated_count += 1
            
            if updated_count % 100 == 0:
                logger.info(f"Progress: {i+1}/{total_posts} - Updated {updated_count} posts")
        else:
            skipped_count += 1
            logger.debug(f"Skipped post {post.reddit_id} - score={post.score}, ratio={post.upvote_ratio}")
    
    logger.info(f"Backfill complete:")
    logger.info(f"  - Updated: {updated_count}")
    logger.info(f"  - Already had estimates: {already_had_count}")
    logger.info(f"  - Skipped (cannot calculate): {skipped_count}")
    
    # Verify specific post
    test_post = Post.objects.filter(reddit_id="1o0sthp").first()
    if test_post:
        logger.info(f"\nTest post 1o0sthp: up={test_post.estimated_upvotes}, down={test_post.estimated_downvotes}")

if __name__ == "__main__":
    backfill_post_votes()