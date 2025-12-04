from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats, Post, PostTag
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from datetime import datetime, UTC, timedelta
import json
import math


def calculate_vs_avg(value, global_avg):
    """
    Calculate percentage difference vs global average.
    
    Returns:
        Float percentage (positive = above avg, negative = below)
        None if cannot calculate
    """
    if value is None or global_avg is None or global_avg == 0:
        return None
    return ((value - global_avg) / global_avg) * 100


def calculate_quintile_tiers(values, labels):
    """
    Assign quintile tier (1-5) to each value.
    Returns dict: {label: tier}
    Tier 1 = smallest, Tier 5 = largest
    """
    if not values:
        return {}
    
    # Filter out None values while keeping track of labels
    valid_pairs = [(v, l) for v, l in zip(values, labels) if v is not None]
    if not valid_pairs:
        return {}
    
    valid_values, valid_labels = zip(*valid_pairs)
    
    # Calculate quintile thresholds
    sorted_values = sorted(valid_values)
    n = len(sorted_values)
    
    if n == 0:
        return {}
    
    thresholds = [
        sorted_values[max(0, int(n * 0.2) - 1)],
        sorted_values[max(0, int(n * 0.4) - 1)],
        sorted_values[max(0, int(n * 0.6) - 1)],
        sorted_values[max(0, int(n * 0.8) - 1)],
    ]
    
    def get_tier(val):
        if val <= thresholds[0]:
            return 1
        elif val <= thresholds[1]:
            return 2
        elif val <= thresholds[2]:
            return 3
        elif val <= thresholds[3]:
            return 4
        else:
            return 5
    
    return {l: get_tier(v) for v, l in zip(valid_values, valid_labels)}


def homepage(request):
    """Homepage with tabbed DATA/CHARTS/EXPLORE view"""
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

    # === EXPLORE TAB DATA ===
    # Build comprehensive metrics for each subreddit
    ten_days_ago = datetime.now(UTC) - timedelta(days=10)
    three_days_ago = datetime.now(UTC) - timedelta(days=3)
    explore_data = []
    
    # Collect raw values for quintile calculation
    pop_values = []
    density_values = []
    sub_names = []
    
    for subreddit in subreddits:
        # Skip DC (extreme outlier)
        if subreddit.name.lower() == 'washingtondc':
            continue
        # Get latest subscriber count
        latest_snapshot = subreddit.subredditdailystats_set.order_by('-date_created').first()
        subscribers = latest_snapshot.subscribers_count if latest_snapshot else None
        
        # Get 7-day post metrics from Post table
        post_stats = Post.objects.filter(
            subreddit=subreddit,
            created_utc__gte=ten_days_ago,
            created_utc__lt=three_days_ago
        ).aggregate(
            post_count=Count('id'),
            total_comments=Sum('num_comments'),
            total_upvotes=Sum('estimated_upvotes'),
            total_downvotes=Sum('estimated_downvotes')
        )
        
        posts_7d = post_stats['post_count'] or 0
        comments_7d = post_stats['total_comments'] or 0
        upvotes_7d = post_stats['total_upvotes'] or 0
        
        # Get base values
        population = subreddit.population
        pop_density = subreddit.pop_density
        region = subreddit.region
        
        # Population-based metrics (per 10k population)
        subs_per_10k_pop = (subscribers / population * 10000) if (subscribers and population) else None
        posts_per_10k_pop = (posts_7d / population * 10000) if population else None
        
        # Subscriber-based metrics (per 1k subscribers)
        posts_per_1k_subs = (posts_7d / subscribers * 1000) if subscribers else None
        comments_per_1k_subs = (comments_7d / subscribers * 1000) if subscribers else None
        upvotes_per_1k_subs = (upvotes_7d / subscribers * 1000) if subscribers else None
        
        # Post-based metrics
        comments_per_post = (comments_7d / posts_7d) if posts_7d > 0 else None
        upvotes_per_post = (upvotes_7d / posts_7d) if posts_7d > 0 else None
        
        explore_data.append({
            'name': subreddit.name,
            'region': region or 'Unknown',
            'population': population,
            'pop_density': pop_density,
            'subscribers': subscribers,
            'posts_7d': posts_7d,
            'comments_7d': comments_7d,
            'upvotes_7d': upvotes_7d,
            # Calculated metrics
            'subs_per_10k_pop': round(subs_per_10k_pop, 2) if subs_per_10k_pop else None,
            'posts_per_10k_pop': round(posts_per_10k_pop, 4) if posts_per_10k_pop else None,
            'posts_per_1k_subs': round(posts_per_1k_subs, 2) if posts_per_1k_subs else None,
            'comments_per_1k_subs': round(comments_per_1k_subs, 2) if comments_per_1k_subs else None,
            'upvotes_per_1k_subs': round(upvotes_per_1k_subs, 2) if upvotes_per_1k_subs else None,
            'comments_per_post': round(comments_per_post, 2) if comments_per_post else None,
            'upvotes_per_post': round(upvotes_per_post, 2) if upvotes_per_post else None,
        })
        
        # Collect for quintile calculation
        sub_names.append(subreddit.name)
        pop_values.append(population)
        density_values.append(pop_density)
    
    # Calculate quintile tiers
    pop_tiers = calculate_quintile_tiers(pop_values, sub_names)
    density_tiers = calculate_quintile_tiers(density_values, sub_names)
    
    # Add tiers to explore_data
    for item in explore_data:
        item['pop_tier'] = pop_tiers.get(item['name'])
        item['density_tier'] = density_tiers.get(item['name'])
    
    explore_data_json = json.dumps(explore_data)
    
    # === END EXPLORE TAB DATA ===

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
        'explore_data': explore_data_json,
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
    
    # === HERO STATS ===
    # Get latest SubredditMetrics for this subreddit
    from tracker.models import SubredditMetrics, GlobalMetrics
    
    latest_metrics = SubredditMetrics.objects.filter(
        subreddit=subreddit
    ).order_by('-date').first()
    
    # Get GlobalMetrics for the same date
    global_metrics = None
    if latest_metrics:
        global_metrics = GlobalMetrics.objects.filter(
            date=latest_metrics.date
        ).first()
    
    # Calculate % vs national avg for each metric
    hero_stats = None
    is_dc = subreddit.name.lower() == 'washingtondc'
    
    if latest_metrics:
        hero_stats = {
            'date': latest_metrics.date,
            'subscribers': {
                'value': latest_metrics.subscribers_7day_avg,
                'rank': latest_metrics.subscribers_7day_rank,
                'vs_avg': calculate_vs_avg(latest_metrics.subscribers_7day_avg, 
                                           global_metrics.subscribers_7day_avg if global_metrics else None),
            },
            'posts': {
                'value': latest_metrics.posts_7day_avg,
                'rank': latest_metrics.posts_7day_rank,
                'vs_avg': calculate_vs_avg(latest_metrics.posts_7day_avg,
                                           global_metrics.posts_7day_avg if global_metrics else None),
            },
            'score': {
                'value': latest_metrics.score_7day_avg,
                'rank': latest_metrics.score_7day_rank,
                'vs_avg': calculate_vs_avg(latest_metrics.score_7day_avg,
                                           global_metrics.score_7day_avg if global_metrics else None),
            },
            'comments': {
                'value': latest_metrics.comments_7day_avg,
                'rank': latest_metrics.comments_7day_rank,
                'vs_avg': calculate_vs_avg(latest_metrics.comments_7day_avg,
                                           global_metrics.comments_7day_avg if global_metrics else None),
            },
        }
    # === END HERO STATS ===
    
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
        'chart_data': chart_data_json,
        'hero_stats': hero_stats,
        'is_dc': is_dc,
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