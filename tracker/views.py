from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats, Post
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import TruncDate
from datetime import datetime, UTC, timedelta
import json

def homepage(request):
    """Homepage with tabbed DATA/ANALYSIS view"""
    # Get sorting parameters
    sort_by = request.GET.get('sort_by', 'subscribers')  # Default sort by name
    order = request.GET.get('order', 'desc')  # Default ascending
    
    # Get all subreddits
    subreddits = Subreddit.objects.all()
    
    # Build data structure with latest snapshot info
    subreddit_data = []
    for subreddit in subreddits:
        latest_snapshot = subreddit.subredditdailystats_set.order_by('-date_created').first()
        snapshot_count = subreddit.subredditdailystats_set.count()
        
        # Calculate subscribers per capita (per 10,000 people)
        per_capita = None
        if (subreddit.population and subreddit.population > 0 and 
            latest_snapshot and latest_snapshot.subscribers_count):
            per_capita = (latest_snapshot.subscribers_count / subreddit.population) * 10000
        
        subreddit_data.append({
            'subreddit': subreddit,
            'latest_snapshot': latest_snapshot,
            'snapshot_count': snapshot_count,
            'per_capita': per_capita,
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
    elif sort_by == 'per_capita':
        subreddit_data.sort(
            key=lambda x: x['per_capita'] if x['per_capita'] else 0
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
    paginator = Paginator(subreddit_data, 51)
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
    """Display detail page for a specific subreddit with snapshot history and charts."""
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
    
    # === CHART DATA PREPARATION (NEW) ===
    # Get all snapshots ordered by date (oldest first for the chart)
    all_snapshots = SubredditDailyStats.objects.filter(
        subreddit=subreddit,
        subscribers_count__isnull=False  # Only include snapshots with subscriber data
    ).order_by('date_created')
    
    # Build chart data as JSON
    chart_labels = []
    chart_data_values = []
    
    for snapshot in all_snapshots:
        # Format date as YYYY-MM-DD
        chart_labels.append(snapshot.date_created.strftime('%Y-%m-%d'))
        chart_data_values.append(snapshot.subscribers_count)
    
    # Create chart data dictionary and convert to JSON
    chart_data = {
        'labels': chart_labels,
        'data': chart_data_values
    }
    chart_data_json = json.dumps(chart_data)
    # === END CHART DATA PREPARATION ===
    
    return render(request, 'tracker/subreddit_detail.html', {
        'subreddit': subreddit,
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order,
        'chart_data': chart_data_json  # NEW: Pass JSON to template
    })

def post_list(request, subreddit_name, date):
    """Display posts for a specific subreddit on a specific date."""
    
    # Get sort parameters from URL (default: score, desc)
    sort_by = request.GET.get('sort_by', 'score')
    order = request.GET.get('order', 'desc')
    
    # Get the subreddit or return 404 if not found
    subreddit = get_object_or_404(Subreddit, name=subreddit_name)
    
    # Parse the date string (YYYY-MM-DD) or return 404 if invalid
    try:
        parsed_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        from django.http import Http404
        raise Http404("Invalid date format")
    
    # Build the order_by clause
    order_prefix = '-' if order == 'desc' else ''
    order_clause = f"{order_prefix}{sort_by}"
    
    # Get all posts for this subreddit on this date with sorting
    posts = Post.objects.filter(
        subreddit=subreddit,
        created_local__date=parsed_date
    ).order_by(order_clause)
    
    # Format date for breadcrumb (e.g., "Wednesday, 10/22")
    formatted_date = parsed_date.strftime('%A, %m/%d')
    
    # Paginate - 10 per page
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'tracker/post_list.html', {
        'subreddit': subreddit,
        'date': date,  # Keep original format for URLs
        'formatted_date': formatted_date,  # For display
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order
    })