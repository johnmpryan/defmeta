from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats
from django.db.models import Count, OuterRef, Subquery
from datetime import datetime, UTC

# Update your homepage view function to handle the new sort option

def homepage(request):
    # Get sorting parameters
    sort_by = request.GET.get('sort_by', 'name')  # Default sort by name
    order = request.GET.get('order', 'asc')  # Default ascending
    
    # Get all subreddits
    subreddits = Subreddit.objects.all()
    
    # Build data structure with latest snapshot info
    subreddit_data = []
    for subreddit in subreddits:
        latest_snapshot = subreddit.subredditdailystats_set.order_by('-date_created').first()
        snapshot_count = subreddit.subredditdailystats_set.count()
        
        subreddit_data.append({
            'subreddit': subreddit,
            'latest_snapshot': latest_snapshot,
            'snapshot_count': snapshot_count,
        })
    
    # Apply sorting
    if sort_by == 'name':
        subreddit_data.sort(key=lambda x: x['subreddit'].name.lower())
    elif sort_by == 'subscribers':
        subreddit_data.sort(
            key=lambda x: x['latest_snapshot'].subscribers_count if x['latest_snapshot'] and x['latest_snapshot'].subscribers_count else 0
        )
    elif sort_by == 'snapshots':
        subreddit_data.sort(key=lambda x: x['snapshot_count'])
    elif sort_by == 'latest_snapshot':
        subreddit_data.sort(
            key=lambda x: x['latest_snapshot'].date_created if x['latest_snapshot'] else datetime.min.replace(tzinfo=UTC)
        )
    
    # Reverse if descending order
    if order == 'desc':
        subreddit_data.reverse()
    
    # Paginate (25 per page)
    paginator = Paginator(subreddit_data, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'subreddit_data': page_obj,
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order,
    }
    
    return render(request, 'tracker/homepage.html', context)

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