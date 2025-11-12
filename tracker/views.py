from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats, Post, PostTag
from django.db.models import Sum, Count
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
    
    # LINE CHART: Aggregate total subscribers by date across all subreddits
    aggregated_data = SubredditDailyStats.objects.filter(
        subscribers_count__isnull=False
    ).extra(
        select={'date_only': 'DATE(date_created)'}
    ).values('date_only').annotate(
        total_subscribers=Sum('subscribers_count')
    ).order_by('date_only')
    
    # Build line chart data as JSON
    chart_labels = []
    chart_data_values = []
    
    for item in aggregated_data:
        # Format date as YYYY-MM-DD
        chart_labels.append(str(item['date_only']))
        chart_data_values.append(item['total_subscribers'])
    
    # Create line chart data dictionary and convert to JSON
    line_chart_data = {
        'labels': chart_labels,
        'data': chart_data_values
    }
    line_chart_data_json = json.dumps(line_chart_data)
    
    # BUBBLE CHART 1: Subscribers vs Posts (last 7 days) with Population as bubble size
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    
    bubble_data = []
    for subreddit in subreddits:
        # Get latest subscriber count
        latest_snapshot = subreddit.subredditdailystats_set.order_by('-date_created').first()
        
        # Get post count from last 7 days
        posts_last_week = Post.objects.filter(
            subreddit=subreddit,
            created_utc__gte=seven_days_ago
        ).count()
        
        # Only include if we have all required data
        if latest_snapshot and latest_snapshot.subscribers_count and subreddit.population:
            bubble_data.append({
                'x': posts_last_week,
                'y': latest_snapshot.subscribers_count,
                'r': subreddit.population / 500000,  # Scale population for bubble size
                'name': subreddit.name,
                'population': subreddit.population  # Add original population for tooltip
            })
    
    bubble_chart_data_json = json.dumps(bubble_data)
    
    # BUBBLE CHART 2: Subscribers vs Posts (last 7 days) with Pop Density as bubble size
    density_bubble_data = []
    for subreddit in subreddits:
        # Skip washingtondc (extreme outlier)
        if subreddit.name.lower() == 'washingtondc':
            continue
            
        # Get latest subscriber count
        latest_snapshot = subreddit.subredditdailystats_set.order_by('-date_created').first()
        
        # Get post count from last 7 days
        posts_last_week = Post.objects.filter(
            subreddit=subreddit,
            created_utc__gte=seven_days_ago
        ).count()
        
        # Only include if we have all required data
        if latest_snapshot and latest_snapshot.subscribers_count and subreddit.pop_density:
            density_bubble_data.append({
                'x': posts_last_week,
                'y': latest_snapshot.subscribers_count,
                'r': subreddit.pop_density / 50,  # Scale density for bubble size
                'name': subreddit.name,
                'pop_density': subreddit.pop_density  # Add original density for tooltip
            })
    
    density_bubble_chart_data_json = json.dumps(density_bubble_data)
    # === END CHART DATA PREPARATION ===
    
    # === TAG ANALYSIS FOR CONTENT TAB ===
    # Get top 20 topic tags from last 7 days globally
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    # Get total post count for last 7 days (for percentage calculations)
    total_posts_last_week = Post.objects.filter(
        created_utc__gte=seven_days_ago
    ).count()
    
    # Get post count per subreddit for last 7 days
    posts_per_subreddit = {}
    for subreddit in subreddits:
        post_count = Post.objects.filter(
            subreddit=subreddit,
            created_utc__gte=seven_days_ago
        ).count()
        posts_per_subreddit[subreddit.name] = post_count

    top_tags_global = PostTag.objects.filter(
        post__created_utc__gte=seven_days_ago,
        tag__category='topic',
    ).values('tag__name').annotate(
        total_count=Count('id')
    ).order_by('-total_count')[:20]

    # Extract tag names for the top 20 tags
    top_tag_names = [item['tag__name'] for item in top_tags_global]
    
    # Get counts per subreddit for these specific tags
    tag_breakdown_by_subreddit = {}
    
    for tag_name in top_tag_names:
        # Get count per subreddit for this tag
        subreddit_counts = PostTag.objects.filter(
            post__created_utc__gte=seven_days_ago,
            tag__category='topic',
            tag__name=tag_name
        ).values('post__subreddit__name').annotate(
            count=Count('id')
        )
        
        # Store in dictionary: tag_name -> {subreddit_name: count}
        tag_breakdown_by_subreddit[tag_name] = {
            item['post__subreddit__name']: item['count'] 
            for item in subreddit_counts
        }
    
    # Prepare data for frontend
    tag_chart_data = {
        'tag_names': top_tag_names,
        'global_counts': [item['total_count'] for item in top_tags_global],
        'breakdown_by_subreddit': tag_breakdown_by_subreddit,
        'total_posts': total_posts_last_week,
        'posts_per_subreddit': posts_per_subreddit
    }
    tag_chart_data_json = json.dumps(tag_chart_data)
    
    # Get list of all subreddit names for dropdown (alphabetically, case-insensitive)
    subreddit_names = sorted([s.name for s in subreddits], key=str.lower)
    subreddit_names_json = json.dumps(subreddit_names)

    # === END TAG ANALYSIS ===

    # Paginate (51 per page)
    paginator = Paginator(subreddit_data, 51)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'subreddit_data': page_obj,
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_order': order,
        'line_chart_data': line_chart_data_json,
        'bubble_chart_data': bubble_chart_data_json,
        'density_bubble_chart_data': density_bubble_chart_data_json,
        'tag_chart_data': tag_chart_data_json,
        'subreddit_names': subreddit_names_json,
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
        # Subtract 1 day because snapshots are created the day after
        from datetime import timedelta
        parsed_date = parsed_date - timedelta(days=1)
    except ValueError:
       from django.http import Http404
       raise Http404("Invalid date format")
    
    # Build the order_by clause
    order_prefix = '-' if order == 'desc' else ''
    order_clause = f"{order_prefix}{sort_by}"
    
    # Get all posts for this subreddit on this date with sorting
    posts = Post.objects.filter(
        subreddit=subreddit,
        created_local=parsed_date
    ).prefetch_related('tags__tag').order_by(order_clause)
    
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