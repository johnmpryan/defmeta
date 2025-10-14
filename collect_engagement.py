import os
import django
from datetime import datetime, timedelta, UTC

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Subreddit, SubredditDailyStats
from reddit_oauth import get_reddit_client

def collect_engagement_data():
    """Collect engagement metrics for posts from 3 days ago"""
    
    reddit = get_reddit_client()
    three_days_ago = datetime.now(UTC).date() - timedelta(days=3)
    
    # Find snapshots from 3 days ago that haven't collected engagement yet
    snapshots = SubredditDailyStats.objects.filter(
        date_created__date=three_days_ago,
        engagement_collected=False
    )
    
    print(f"Found {snapshots.count()} snapshots from {three_days_ago} to process")
    
    for snapshot in snapshots:
        subreddit_name = snapshot.subreddit.name
        print(f"\nProcessing r/{subreddit_name}...")
        
        try:
            subreddit = reddit.subreddit(subreddit_name)
            posts_from_that_day = []
            
            # Fetch recent posts and filter to that specific day
            for post in subreddit.new(limit=100):
                post_date = datetime.fromtimestamp(post.created_utc, UTC).date()
                if post_date == three_days_ago:
                    posts_from_that_day.append(post)
                elif post_date < three_days_ago:
                    break  # Posts are sorted newest first, stop when we pass the target date
            
            if not posts_from_that_day:
                print(f"  No posts found from {three_days_ago}")
                # Mark as collected even if no posts (so we don't keep checking)
                snapshot.engagement_collected = True
                snapshot.save()
                continue
            
            # Calculate aggregates
            total_score = sum(post.score for post in posts_from_that_day)
            total_ratio = sum(post.upvote_ratio for post in posts_from_that_day)
            total_comments = sum(post.num_comments for post in posts_from_that_day)
            post_count = len(posts_from_that_day)
            
            avg_score = total_score / post_count
            avg_ratio = total_ratio / post_count
            
            # Update the snapshot
            snapshot.avg_post_score = avg_score
            snapshot.avg_upvote_ratio = avg_ratio
            snapshot.total_comments = total_comments
            snapshot.engagement_collected = True
            snapshot.save()
            
            print(f"  ✓ Updated: {post_count} posts, avg score={avg_score:.1f}, avg ratio={avg_ratio:.2f}, {total_comments} comments")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    print("\nEngagement collection complete!")

if __name__ == "__main__":
    collect_engagement_data()