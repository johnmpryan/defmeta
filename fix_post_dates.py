"""
Script to fix created_local dates for all existing posts.
The created_local field should contain the date in the subreddit's local timezone,
not the UTC date.

Usage:
    # Test mode - see what would change for specific subreddit/date
    python fix_post_dates.py test california 2025-11-06
    
    # Test mode - see changes for all posts on a specific date
    python fix_post_dates.py test all 2025-11-06
    
    # Dry run - show all changes without applying
    python fix_post_dates.py dryrun
    
    # Actually fix the data
    python fix_post_dates.py fix
"""

import os
import django
from datetime import datetime, date
from zoneinfo import ZoneInfo
import sys
from django.db.models import F

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Post, Subreddit
import logging
from logger_config import setup_logger

logger = setup_logger(__name__)


def get_correct_local_date(post):
    """
    Calculate what the created_local date SHOULD be for a post.
    
    Returns:
        date object representing the correct local date
    """
    # Get the subreddit's timezone
    timezone_str = post.subreddit.timezone or 'America/New_York'
    tz = ZoneInfo(timezone_str)
    
    # Convert UTC time to local timezone and extract date
    local_datetime = post.created_utc.astimezone(tz)
    correct_local_date = local_datetime.date()
    
    return correct_local_date


def test_single_subreddit(subreddit_name, test_date=None):
    """
    Test mode: Show what would change for a specific subreddit.
    
    Args:
        subreddit_name: Name of subreddit to test (or 'all' for all subreddits)
        test_date: Optional date string 'YYYY-MM-DD' to filter posts
    """
    # Build query
    if subreddit_name.lower() == 'all':
        posts_query = Post.objects.all()
        print(f"\nTesting all subreddits" + (f" for date {test_date}" if test_date else ""))
    else:
        subreddit = Subreddit.objects.filter(name=subreddit_name).first()
        if not subreddit:
            print(f"Subreddit '{subreddit_name}' not found!")
            return
        posts_query = Post.objects.filter(subreddit=subreddit)
        print(f"\nTesting r/{subreddit_name} (timezone: {subreddit.timezone or 'America/New_York'})")
    
    # Filter by date if specified
    if test_date:
        try:
            filter_date = datetime.strptime(test_date, '%Y-%m-%d').date()
            posts_query = posts_query.filter(created_utc__date=filter_date)
            print(f"Filtering to posts created (UTC) on {filter_date}")
        except ValueError:
            print(f"Invalid date format: {test_date}. Use YYYY-MM-DD")
            return
    
    # Get sample of posts
    posts = posts_query.select_related('subreddit').order_by('-created_utc')[:20]
    
    if not posts:
        print("No posts found matching criteria")
        return
    
    print(f"\nShowing up to 20 posts:\n")
    print("-" * 100)
    
    changes_needed = 0
    for post in posts:
        current_local_date = post.created_local
        correct_local_date = get_correct_local_date(post)
        
        if current_local_date != correct_local_date:
            changes_needed += 1
            print(f"POST: {post.title[:60]}...")
            print(f"  Subreddit: r/{post.subreddit.name} ({post.subreddit.timezone or 'America/New_York'})")
            print(f"  UTC time: {post.created_utc}")
            print(f"  Current local date: {current_local_date} (WRONG)")
            print(f"  Correct local date: {correct_local_date} (FIXED)")
            print(f"  Change: {current_local_date} → {correct_local_date}")
            print()
    
    if changes_needed == 0:
        print("All checked posts have correct dates!")
    else:
        # Get total count needing fixes
        total_query = posts_query
        total_needing_fix = 0
        
        print(f"\nFound {changes_needed} posts (out of 20 checked) needing date corrections")
        
        # Count total if not too many
        if posts_query.count() < 10000:
            for post in posts_query.select_related('subreddit'):
                if post.created_local != get_correct_local_date(post):
                    total_needing_fix += 1
            print(f"Total posts needing fix in this query: {total_needing_fix} out of {posts_query.count()}")


def dry_run():
    """
    Show a summary of all changes that would be made without applying them.
    """
    print("\nDRY RUN - Analyzing all posts...")
    
    all_posts = Post.objects.select_related('subreddit').order_by('created_utc')
    total_posts = all_posts.count()
    
    print(f"Total posts in database: {total_posts}")
    print("\nChecking for incorrect dates...")
    
    incorrect_count = 0
    sample_errors = []
    
    for i, post in enumerate(all_posts):
        current_date = post.created_local
        correct_date = get_correct_local_date(post)
        
        if current_date != correct_date:
            incorrect_count += 1
            
            # Collect first 10 examples
            if len(sample_errors) < 10:
                sample_errors.append({
                    'title': post.title[:50],
                    'subreddit': post.subreddit.name,
                    'timezone': post.subreddit.timezone or 'America/New_York',
                    'utc': post.created_utc,
                    'current': current_date,
                    'correct': correct_date
                })
        
        # Progress indicator
        if (i + 1) % 1000 == 0:
            print(f"  Checked {i + 1}/{total_posts} posts...")
    
    print(f"\nResults:")
    print(f"  Posts with correct dates: {total_posts - incorrect_count}")
    print(f"  Posts needing correction: {incorrect_count}")
    print(f"  Percentage needing fix: {(incorrect_count/total_posts*100):.1f}%")
    
    if sample_errors:
        print(f"\nSample of posts needing correction:")
        print("-" * 80)
        for error in sample_errors:
            print(f"r/{error['subreddit']}: {error['title']}")
            print(f"  Timezone: {error['timezone']}")
            print(f"  Current: {error['current']} → Correct: {error['correct']}")
            print()


def fix_all_dates():
    """
    Actually fix all the created_local dates in the database.
    """
    print("\nFIXING ALL DATES - This will update the database!")
    
    response = input("Are you sure you want to proceed? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return
    
    all_posts = Post.objects.select_related('subreddit').order_by('created_utc')
    total_posts = all_posts.count()
    
    print(f"\nProcessing {total_posts} posts...")
    
    fixed_count = 0
    already_correct = 0
    error_count = 0
    
    # Process in batches for efficiency
    batch_size = 500
    posts_to_update = []
    
    for i, post in enumerate(all_posts):
        try:
            current_date = post.created_local
            correct_date = get_correct_local_date(post)
            
            if current_date != correct_date:
                post.created_local = correct_date
                posts_to_update.append(post)
                fixed_count += 1
                
                # Batch update
                if len(posts_to_update) >= batch_size:
                    Post.objects.bulk_update(posts_to_update, ['created_local'])
                    logger.info(f"Updated batch of {len(posts_to_update)} posts")
                    posts_to_update = []
            else:
                already_correct += 1
            
            # Progress indicator
            if (i + 1) % 1000 == 0:
                print(f"  Processed {i + 1}/{total_posts} posts... ({fixed_count} fixed so far)")
                
        except Exception as e:
            error_count += 1
            logger.error(f"Error processing post {post.id}: {e}")
    
    # Update any remaining posts
    if posts_to_update:
        Post.objects.bulk_update(posts_to_update, ['created_local'])
        logger.info(f"Updated final batch of {len(posts_to_update)} posts")
    
    print(f"\n" + "=" * 60)
    print(f"COMPLETE!")
    print(f"  Total posts processed: {total_posts}")
    print(f"  Dates fixed: {fixed_count}")
    print(f"  Already correct: {already_correct}")
    print(f"  Errors: {error_count}")
    print("=" * 60)


def show_usage():
    """Display usage instructions."""
    print(__doc__)


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 2:
        show_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'test':
        if len(sys.argv) < 3:
            print("Usage: python fix_post_dates.py test <subreddit_name|all> [YYYY-MM-DD]")
            return
        
        subreddit_name = sys.argv[2]
        test_date = sys.argv[3] if len(sys.argv) > 3 else None
        test_single_subreddit(subreddit_name, test_date)
        
    elif command == 'dryrun':
        dry_run()
        
    elif command == 'fix':
        fix_all_dates()
        
    else:
        print(f"Unknown command: {command}")
        show_usage()


if __name__ == "__main__":
    main()