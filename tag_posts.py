import os
import django
from datetime import datetime, timedelta, UTC
import json
from anthropic import Anthropic
import sys
import time
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Post, Tag
from logger_config import setup_logger

logger = setup_logger(__name__)

# Initialize Claude client
client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

# Tag definitions - pulled from database
def get_tag_definitions():
    """Get current tags from database, grouped by category"""
    tags_by_category = {}
    for tag in Tag.objects.all():
        if tag.category not in tags_by_category:
            tags_by_category[tag.category] = []
        tags_by_category[tag.category].append(tag.name)
    return tags_by_category

def batch_tag_posts(posts, model="claude-3-5-haiku-20241022"):
    """
    Send multiple posts to Claude for tagging in one API call.
    
    Args:
        posts: List of Post objects to tag
        model: Claude model to use
        
    Returns:
        Dictionary mapping post IDs to their tags with confidence scores
    """
    if not posts:
        return {}
    
    # Get current tag definitions
    tag_definitions = get_tag_definitions()
    
    # Build posts data for prompt
    posts_data = []
    for i, post in enumerate(posts):
        body_text = (post.body[:1000] if post.body else "No body text")
        posts_data.append({
            'id': i,
            'reddit_id': post.reddit_id,
            'subreddit': post.subreddit.name,
            'title': post.title,
            'body': body_text
        })
    
    # Build prompt
    prompt = f"""Analyze these {len(posts)} Reddit posts and assign 3-5 relevant tags to each with confidence scores.

Available tags by category:
{json.dumps(tag_definitions, indent=2)}

Posts to analyze:
{json.dumps(posts_data, indent=2)}

For each post, return a JSON object with this structure:
{{
  "0": {{
    "tags": [
      {{"name": "tag1", "confidence": 0.95}},
      {{"name": "tag2", "confidence": 0.85}}
    ]
  }},
  "1": {{ ... }}
}}

Where confidence is 0.0-1.0 (how certain you are the tag applies).

Rules:
- Assign 3-5 tags per post
- Use only tags from the available list above
- Consider the post's title AND body
- Tags should be relevant to the content and context
- Return ONLY the JSON object, no other text"""

    try:
        # Call Claude API
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        response_text = response.content[0].text.strip()
        
        # Try to extract JSON if wrapped in markdown code blocks
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        tags_by_id = json.loads(response_text)
        
        # Map back to reddit_ids
        result = {}
        for i, post in enumerate(posts):
            str_id = str(i)
            if str_id in tags_by_id:
                result[post.reddit_id] = tags_by_id[str_id]['tags']
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response was: {response_text}")
        return {}
    except Exception as e:
        logger.error(f"Error calling Claude API: {e}")
        return {}

def save_post_tags(post, tags_with_confidence):
    """
    Save tags for a post to the database with confidence scores.
    
    Args:
        post: Post object
        tags_with_confidence: List of dicts [{"name": "tag1", "confidence": 0.95}, ...]
        
    Returns:
        Number of tags saved
    """
    if not tags_with_confidence:
        return 0
    
    from tracker.models import PostTag
    
    # Extract tag names
    tag_names = [t['name'] for t in tags_with_confidence]
    
    # Get Tag objects from database
    tags = Tag.objects.filter(name__in=tag_names)
    
    # Check for unknown tags
    found_names = set(tag.name for tag in tags)
    unknown_tags = set(tag_names) - found_names
    if unknown_tags:
        logger.warning(f"Unknown tags returned for post {post.reddit_id}: {unknown_tags}")
    
    # Clear existing tags for this post
    PostTag.objects.filter(post=post).delete()
    
    # Create dict for confidence lookup
    confidence_map = {t['name']: t.get('confidence', 0.0) for t in tags_with_confidence}
    
    # Add new tags with confidence scores
    for tag in tags:
        PostTag.objects.create(
            post=post,
            tag=tag,
            applied_by='claude-ai',
            confidence_score=confidence_map.get(tag.name, 0.0)
        )
    
    # Mark as tagged
    post.tags_collected = True
    post.save(update_fields=['tags_collected'])
    
    return len(tags)

def tag_posts_batch(posts, batch_size=5, delay=1.0):
    """
    Tag posts in batches to respect rate limits.
    
    Args:
        posts: QuerySet or list of Post objects
        batch_size: Number of posts per API call
        delay: Seconds to wait between API calls
        
    Returns:
        Dictionary with stats
    """
    total = len(posts)
    tagged_count = 0
    error_count = 0
    
    logger.info(f"Starting to tag {total} posts in batches of {batch_size}")
    
    # Process in batches
    for i in range(0, total, batch_size):
        batch = posts[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} posts)")
        
        # Get tags from Claude (now returns tags with confidence)
        tags_by_reddit_id = batch_tag_posts(batch)
        
        # Save to database
        for post in batch:
            if post.reddit_id in tags_by_reddit_id:
                tags_with_conf = tags_by_reddit_id[post.reddit_id]
                saved = save_post_tags(post, tags_with_conf)
                if saved > 0:
                    tagged_count += 1
                    tag_names = [t['name'] for t in tags_with_conf]
                    logger.debug(f"Tagged post {post.reddit_id} with {saved} tags: {tag_names}")
                else:
                    error_count += 1
            else:
                error_count += 1
                logger.warning(f"No tags returned for post {post.reddit_id}")
        
        # Rate limiting delay
        if i + batch_size < total:
            time.sleep(delay)
    
    return {
        'total': total,
        'tagged': tagged_count,
        'errors': error_count
    }

def tag_posts_by_criteria(start_date=None, end_date=None, subreddit_name=None, 
                          limit=None, test_mode=False):
    """
    Tag posts matching specified criteria.
    
    Args:
        start_date: String 'YYYY-MM-DD' or None
        end_date: String 'YYYY-MM-DD' or None
        subreddit_name: String or None
        limit: Maximum number of posts to process
        test_mode: If True, only process first 10 posts
        
    Returns:
        Dictionary with stats
    """
    # Build query
    query = Post.objects.filter(tags_collected=False)
    
    # Add date filters
    if start_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=UTC)
        query = query.filter(created_utc__gte=start_dt)
        logger.info(f"Filtering posts from {start_date}")
    
    if end_date:
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=UTC)
        query = query.filter(created_utc__lt=end_dt)
        logger.info(f"Filtering posts before {end_date}")
    
    # Add subreddit filter
    if subreddit_name:
        query = query.filter(subreddit__name=subreddit_name)
        logger.info(f"Filtering to r/{subreddit_name}")
    
    # Order by date
    query = query.order_by('created_utc')
    
    # Apply limit
    if test_mode:
        query = query[:10]
        logger.info("TEST MODE: Processing only 10 posts")
    elif limit:
        query = query[:limit]
        logger.info(f"Limiting to {limit} posts")
    
    # Get posts
    posts = list(query)
    
    if not posts:
        logger.info("No posts found matching criteria")
        return {'total': 0, 'tagged': 0, 'errors': 0}
    
    logger.info(f"Found {len(posts)} posts to tag")
    
    # Tag the posts
    return tag_posts_batch(posts)

def tag_yesterday_posts():
    """Tag posts from yesterday (for daily scheduler)"""
    yesterday = (datetime.now(UTC) - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now(UTC).strftime('%Y-%m-%d')
    
    logger.info(f"Tagging posts from yesterday ({yesterday})")
    
    return tag_posts_by_criteria(start_date=yesterday, end_date=today)

def main():
    """
    Main function with command-line argument parsing.
    
    Usage examples:
        python tag_posts.py                          # Tag yesterday's posts
        python tag_posts.py test                     # Test mode (10 posts)
        python tag_posts.py --start 2025-10-20       # From date
        python tag_posts.py --start 2025-10-20 --end 2025-10-25  # Date range
        python tag_posts.py --subreddit kentucky     # Specific subreddit
        python tag_posts.py --start 2025-10-20 --subreddit kentucky --limit 100
    """
    # Parse arguments
    args = sys.argv[1:]
    
    # Check for test mode
    if 'test' in args:
        logger.info("Running in TEST MODE")
        stats = tag_posts_by_criteria(test_mode=True)
        logger.info(f"Test complete: {stats}")
        return
    
    # Parse named arguments
    start_date = None
    end_date = None
    subreddit_name = None
    limit = None
    
    i = 0
    while i < len(args):
        if args[i] == '--start' and i + 1 < len(args):
            start_date = args[i + 1]
            i += 2
        elif args[i] == '--end' and i + 1 < len(args):
            end_date = args[i + 1]
            i += 2
        elif args[i] == '--subreddit' and i + 1 < len(args):
            subreddit_name = args[i + 1]
            i += 2
        elif args[i] == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1
    
    # If no arguments provided, tag yesterday's posts
    if not any([start_date, end_date, subreddit_name, limit]):
        stats = tag_yesterday_posts()
    else:
        stats = tag_posts_by_criteria(
            start_date=start_date,
            end_date=end_date,
            subreddit_name=subreddit_name,
            limit=limit
        )
    
    logger.info(f"Tagging complete: {stats}")
    logger.info(f"  - Total posts: {stats['total']}")
    logger.info(f"  - Successfully tagged: {stats['tagged']}")
    logger.info(f"  - Errors: {stats['errors']}")

if __name__ == "__main__":
    main()