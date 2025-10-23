"""
Diagnostic script to check why posts aren't getting backfilled
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Post

# Check specific post
post = Post.objects.filter(reddit_id="1o0sthp").first()
if post:
    print(f"Post: {post.reddit_id}")
    print(f"  Score: {post.score}")
    print(f"  Ratio: {post.upvote_ratio}")
    print(f"  Engagement collected: {post.engagement_collected}")
    print(f"  Estimated upvotes: {post.estimated_upvotes}")
    print(f"  Estimated downvotes: {post.estimated_downvotes}")
    
    # Calculate what the votes should be
    if post.score and post.upvote_ratio and post.upvote_ratio != 0.5:
        total_votes = post.score / (2 * post.upvote_ratio - 1)
        est_up = round(total_votes * post.upvote_ratio)
        est_down = round(total_votes * (1 - post.upvote_ratio))
        print(f"\n  Should be: up={est_up}, down={est_down}")

# Check overall statistics
print("\n=== Overall Statistics ===")
total_with_engagement = Post.objects.filter(engagement_collected=True).count()
print(f"Posts with engagement collected: {total_with_engagement}")

has_score_and_ratio = Post.objects.filter(
    engagement_collected=True,
    score__isnull=False,
    upvote_ratio__isnull=False
).count()
print(f"Posts with score AND ratio: {has_score_and_ratio}")

needs_backfill = Post.objects.filter(
    engagement_collected=True,
    score__isnull=False,
    upvote_ratio__isnull=False,
    estimated_upvotes__isnull=True
).count()
print(f"Posts still needing backfill: {needs_backfill}")

already_done = Post.objects.filter(
    estimated_upvotes__isnull=False
).count()
print(f"Posts with estimated votes: {already_done}")