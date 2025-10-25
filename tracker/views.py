from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats, Post
from django.db.models import Sum
from django.db.models.functions import TruncDate
from datetime import datetime, UTC, timedelta
import json

def homepage(request):
    """Homepage with tabbed DATA/CHARTS view"""
    # Get sorting parameters
    sort_by = request.GET.get('sort_by', 'subscribers')
    order = request.GET.get('order', 'desc')
    
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
    
    # === CHART DATA PREPARATION FOR CHARTS TAB ===
    # Aggregate total subscribers by date across all subreddits
    aggregated_data = SubredditDailyStats.objects.filter(
        subscribers_count__isnull=False
    ).extra(
        select={'date_only': 'DATE(date_created)'}
    ).values('date_only').annotate(
        total_subscribers=Sum('subscribers_count')
    ).order_by('date_only')
    
    # Build chart data as JSON
    chart_labels = []
    chart_data_values = []
    
    for item in aggregated_data:
        # Format date as YYYY-MM-DD
        chart_labels.append(str(item['date_only']))
        chart_data_values.append(item['total_subscribers'])
    
    # Create chart data dictionary and convert to JSON
    chart_data = {
        'labels': chart_labels,
        'data': chart_data_values
    }
    chart_data_json = json.dumps(chart_data)
    # === END CHART DATA PREPARATION ===
    
    # Paginate (51 per page)
    paginator = Paginator(subreddit_data, 51)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'subreddit_data': page_obj,
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order,
        'chart_data': chart_data_json,
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
    
    # === CHART DATA PREPARATION ===
    # Get all snapshots ordered by date (oldest first for the chart)
    all_snapshots = SubredditDailyStats.objects.filter(
        subreddit=subreddit,
        subscribers_count__isnull=False
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
        'chart_data': chart_data_json
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
        'date': date,
        'formatted_date': formatted_date,
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order
    })