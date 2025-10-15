from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats
from django.db.models import Count, OuterRef, Subquery

def homepage(request):
    # Get sort parameters from URL (default: name, desc)
    sort_by = request.GET.get('sort_by', 'name')
    order = request.GET.get('order', 'desc')
    
    # Subquery to get the latest snapshot ID for each subreddit
    latest_snapshot_subquery = SubredditDailyStats.objects.filter(
        subreddit=OuterRef('pk')
    ).order_by('-date_created').values('pk')[:1]
    
    # Annotate subreddits with latest snapshot data and snapshot count
    # This reduces N+1 queries by pulling data in the main query
    subreddits = Subreddit.objects.annotate(
        snapshot_count=Count('subredditdailystats'),
        latest_snapshot_id=Subquery(latest_snapshot_subquery),
        latest_subscribers=Subquery(
            SubredditDailyStats.objects.filter(
                pk=OuterRef('latest_snapshot_id')
            ).values('subscribers_count')[:1]
        ),
        latest_posts=Subquery(
            SubredditDailyStats.objects.filter(
                pk=OuterRef('latest_snapshot_id')
            ).values('posts_count')[:1]
        ),
        latest_score=Subquery(
            SubredditDailyStats.objects.filter(
                pk=OuterRef('latest_snapshot_id')
            ).values('avg_post_score')[:1]
        ),
    )
    
    # Map sort parameter to database field
    sort_mapping = {
        'name': 'name',
        'subscribers': 'latest_subscribers',
        'snapshots': 'snapshot_count',
        'posts': 'latest_posts',
        'score': 'latest_score'
    }
    
    # Get the database field to sort by
    sort_field = sort_mapping.get(sort_by, 'name')
    
    # Add descending prefix if needed
    if order == 'desc':
        sort_field = f'-{sort_field}'
    
    # Apply sorting at database level
    subreddits = subreddits.order_by(sort_field)
    
    # Paginate - 25 per page
    paginator = Paginator(subreddits, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Build data structure for template
    # We still need to fetch the actual snapshot objects for the template
    subreddit_data = []
    for subreddit in page_obj:
        # Get the actual latest snapshot object if it exists
        if subreddit.latest_snapshot_id:
            latest_snapshot = SubredditDailyStats.objects.get(pk=subreddit.latest_snapshot_id)
        else:
            latest_snapshot = None
            
        subreddit_data.append({
            'subreddit': subreddit,
            'latest_snapshot': latest_snapshot,
            'snapshot_count': subreddit.snapshot_count
        })
    
    return render(request, 'tracker/homepage.html', {
        'subreddit_data': subreddit_data,
        'page_obj': page_obj,  # Add page object for pagination controls
        'current_sort': sort_by,
        'current_order': order
    })

def subreddit_detail(request, subreddit_name):
    """Display detail page for a specific subreddit with snapshot history."""
    # Get sort parameters from URL (default: date_created, desc)
    sort_by = request.GET.get('sort_by', 'date_created')
    order = request.GET.get('order', 'desc')
    
    # Get the subreddit or return 404 if not found
    subreddit = get_object_or_404(Subreddit, name=subreddit_name)
    
    # Build the order_by clause
    order_prefix = '-' if order == 'desc' else ''
    order_clause = f"{order_prefix}{sort_by}"
    
    # Get all snapshots for this subreddit with sorting
    snapshots = SubredditDailyStats.objects.filter(
        subreddit=subreddit
    ).order_by(order_clause)
    
    # Paginate - 10 per page
    paginator = Paginator(snapshots, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'tracker/subreddit_detail.html', {
        'subreddit': subreddit,
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order
    })