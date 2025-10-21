from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats
from django.db.models import Count, OuterRef, Subquery
from datetime import datetime, UTC
import plotext as plt

def homepage(request):
    """Homepage with tabbed DATA/ANALYSIS view"""
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
    elif sort_by == 'posts':
        subreddit_data.sort(
            key=lambda x: x['latest_snapshot'].posts_count if x['latest_snapshot'] and x['latest_snapshot'].posts_count else 0
        )
    elif sort_by == 'score':
        subreddit_data.sort(
            key=lambda x: x['latest_snapshot'].avg_post_score if x['latest_snapshot'] and x['latest_snapshot'].avg_post_score else 0
        )
    elif sort_by == 'latest_snapshot':
        subreddit_data.sort(
            key=lambda x: x['latest_snapshot'].date_created if x['latest_snapshot'] else datetime.min.replace(tzinfo=UTC)
        )
    
    # Reverse if descending order
    if order == 'desc':
        subreddit_data.reverse()
    
    # Generate ASCII chart for ANALYSIS tab
    chart_data = []
    for item in subreddit_data:
        if item['latest_snapshot'] and item['latest_snapshot'].subscribers_count:
            chart_data.append({
                'name': item['subreddit'].name,
                'subscribers': item['latest_snapshot'].subscribers_count
            })
    
    # Sort chart data by subscriber count (lowest to highest)
    chart_data.sort(key=lambda x: x['subscribers'])
    
    if chart_data:
        # Find max value for scaling
        max_subs = max(d['subscribers'] for d in chart_data)
        
        # Build simple ASCII bar chart
        chart_lines = []
        chart_lines.append("Subscriber Counts by State Subreddit")
        chart_lines.append("=" * 80)
        chart_lines.append("")
        
        # Max bar width in characters
        max_bar_width = 50
        
        for item in chart_data:
            name = item['name'].ljust(15)  # Left-justify name to 15 chars
            count = item['subscribers']
            
            # Calculate bar length (proportional to subscriber count)
            bar_length = int((count / max_subs) * max_bar_width)
            bar = '█' * bar_length
            
            # Format the line
            line = f"{name} │ {bar} {count:,}"
            chart_lines.append(line)
        
        chart_output = '\n'.join(chart_lines)
    else:
        chart_output = "No data available for chart"
    
    # Paginate (25 per page)
    paginator = Paginator(subreddit_data, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'subreddit_data': page_obj,
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order,
        'chart': chart_output,
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