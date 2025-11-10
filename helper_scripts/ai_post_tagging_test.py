import os
import django
from datetime import datetime, timedelta, UTC
import json
from anthropic import Anthropic
from collections import Counter
import time
from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Post

# Initialize Claude client
client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

# Tag definitions
TEST_TAGS = {
    'topic': [
        'politics', 'weather', 'sports', 'food', 'tourism', 
        'education', 'employment', 'housing', 'transportation',
        'environment', 'crime', 'health', 'business', 'entertainment',
        'local_news', 'history', 'technology', 'infrastructure'
    ],
    'content_type': [
        'question', 'advice_request', 'discussion', 'photograph', 
        'news_article', 'personal_story', 'recommendation', 'rant',
        'announcement', 'help_needed', 'opinion', 'event'
    ],
    'sentiment': ['positive', 'negative', 'neutral', 'controversial', 'humorous']
}

def test_ai_tagging(post, model="claude-3-haiku-20240307"):
    """Test AI tagging on a single post using Claude"""
    
    body_text = (post.body[:1000] if post.body else "No body text")
    
    prompt = f"""Analyze this Reddit post from r/{post.subreddit.name} and assign 3-5 relevant tags.

Title: {post.title}
Body: {body_text}

Available Tags:
Topics: {', '.join(TEST_TAGS['topic'])}
Content Types: {', '.join(TEST_TAGS['content_type'])}
Sentiments: {', '.join(TEST_TAGS['sentiment'])}

Return ONLY valid JSON (no other text) with this exact format:
{{
    "tags": ["tag1", "tag2", "tag3"],
    "confidence": {{"tag1": 0.95, "tag2": 0.85, "tag3": 0.80}},
    "primary_tag": "tag1",
    "reasoning": "Brief explanation"
}}

Rules:
- Choose 3-5 most relevant tags total
- Include at least one content_type tag
- Confidence scores between 0.0-1.0
- Only use tags from the provided lists
- Return ONLY the JSON object, no other text"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=200,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON from Claude's response
        result = json.loads(response.content[0].text)
        
        # Add token usage
        result['tokens_used'] = response.usage.input_tokens + response.usage.output_tokens
        result['model'] = model
        return result
        
    except json.JSONDecodeError as e:
        return {'error': f'JSON parse error: {str(e)}', 'response': response.content[0].text}
    except Exception as e:
        return {'error': str(e)}

def run_test_batch(num_posts=50, subreddit_filter=None):
    """Run tagging test on batch of posts"""
    
    # Build query
    query = Post.objects.filter(
        body__isnull=False,
        body__gt='',
        created_utc__gte=datetime.now(UTC) - timedelta(days=30)
    )
    
    if subreddit_filter:
        query = query.filter(subreddit__name=subreddit_filter)
    
    # Get random sample
    posts = query.order_by('?')[:num_posts]
    
    if not posts:
        print("No posts found matching criteria")
        return None
    
    results = []
    total_tokens = 0
    errors = 0
    
    # Claude Haiku pricing
    INPUT_COST_PER_M = 0.25
    OUTPUT_COST_PER_M = 1.25
    
    print(f"Testing AI tagging on {len(posts)} posts using Claude Haiku...\n")
    print("-" * 80)
    
    for i, post in enumerate(posts, 1):
        print(f"[{i}/{len(posts)}] {post.title[:60]}...")
        
        # Rate limiting for Claude (avoid hitting rate limits)
        if i > 1:
            time.sleep(1)  # Claude has stricter rate limits than OpenAI
        
        result = test_ai_tagging(post)
        
        if 'error' not in result:
            tokens = result.get('tokens_used', 0)
            total_tokens += tokens
            
            # Store result
            results.append({
                'post_id': post.reddit_id,
                'subreddit': post.subreddit.name,
                'title': post.title,
                'tags': result.get('tags', []),
                'confidence': result.get('confidence', {}),
                'primary_tag': result.get('primary_tag', ''),
                'reasoning': result.get('reasoning', ''),
                'tokens': tokens
            })
            
            # Display inline results
            tags_str = ', '.join(result.get('tags', []))
            confidences = result.get('confidence', {})
            avg_confidence = sum(confidences.values()) / max(len(confidences), 1)
            print(f"  → Tags: {tags_str}")
            print(f"  → Avg confidence: {avg_confidence:.2f}")
            
            # Flag low confidence
            low_conf = [k for k, v in confidences.items() if v < 0.7]
            if low_conf:
                print(f"  ⚠ Low confidence tags: {', '.join(low_conf)}")
        else:
            errors += 1
            print(f"  ✗ Error: {result['error']}")
            if 'response' in result:
                print(f"  Response was: {result['response'][:100]}...")
        
        print()
    
    # Calculate cost (rough estimate - assuming 80% input, 20% output)
    input_tokens = total_tokens * 0.8
    output_tokens = total_tokens * 0.2
    total_cost = (input_tokens * INPUT_COST_PER_M + output_tokens * OUTPUT_COST_PER_M) / 1_000_000
    
    # Print summary
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Successfully processed: {len(results)}/{len(posts)} posts")
    print(f"Errors: {errors}")
    print(f"Total tokens used: {total_tokens:,}")
    print(f"Estimated cost: ${total_cost:.4f}")
    print(f"Average tokens per post: {total_tokens/max(len(results), 1):.0f}")
    
    if results:
        # Tag frequency analysis
        all_tags = []
        all_confidences = []
        
        for r in results:
            all_tags.extend(r['tags'])
            all_confidences.extend(r['confidence'].values())
        
        print(f"\nTAG FREQUENCY (top 15):")
        for tag, count in Counter(all_tags).most_common(15):
            percentage = (count / len(results)) * 100
            print(f"  {tag:20} {count:3} times ({percentage:.1f}%)")
        
        # Confidence analysis
        if all_confidences:
            avg_confidence = sum(all_confidences) / len(all_confidences)
            low_conf_count = sum(1 for c in all_confidences if c < 0.7)
            high_conf_count = sum(1 for c in all_confidences if c >= 0.9)
            
            print(f"\nCONFIDENCE METRICS:")
            print(f"  Average confidence: {avg_confidence:.3f}")
            print(f"  High confidence (≥0.9): {high_conf_count} tags")
            print(f"  Low confidence (<0.7): {low_conf_count} tags")
            print(f"  Would need review: {low_conf_count/len(all_confidences)*100:.1f}% of tags")
        
        # Category distribution
        category_counts = {'topic': 0, 'content_type': 0, 'sentiment': 0}
        for tag in all_tags:
            for category, tag_list in TEST_TAGS.items():
                if tag in tag_list:
                    category_counts[category] += 1
                    break
        
        print(f"\nCATEGORY DISTRIBUTION:")
        for category, count in category_counts.items():
            print(f"  {category:15} {count:4} tags")
        
        # Save results
        output_file = f'claude_tagging_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(output_file, 'w') as f:
            json.dump({
                'summary': {
                    'posts_processed': len(results),
                    'total_tokens': total_tokens,
                    'estimated_cost': total_cost,
                    'average_confidence': avg_confidence if all_confidences else 0,
                    'tag_frequency': dict(Counter(all_tags).most_common())
                },
                'results': results
            }, f, indent=2)
        
        print(f"\nDetailed results saved to: {output_file}")
    
    return results

if __name__ == "__main__":
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("Please set ANTHROPIC_API_KEY environment variable")
        print("Windows: set ANTHROPIC_API_KEY=sk-ant-...")
        exit(1)
    
    # Install anthropic if needed
    try:
        import anthropic
    except ImportError:
        print("Installing anthropic library...")
        import subprocess
        subprocess.run(["pip", "install", "anthropic"])
        print("Please restart the script")
        exit(1)
    
    # Run test
    results = run_test_batch(
        num_posts=50,  # Start with 50, increase if needed
        subreddit_filter=None  # Or specify like 'kentucky'
    )