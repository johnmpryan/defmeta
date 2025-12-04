"""
Calculate rolling metrics for all subreddits and global benchmarks.
Designed to run nightly after engagement data is collected.

Usage:
    python calculate_metrics.py                  # Calculate for today
    python calculate_metrics.py 2025-12-01       # Calculate for specific date
    python calculate_metrics.py --backfill 30    # Backfill last 30 days
"""

import os
import django
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal
import statistics

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from django.db.models import Avg, Sum, Count
from django.db.models.functions import Coalesce
from tracker.models import (
    Subreddit, SubredditDailyStats, Post,
    GlobalMetrics, SubredditMetrics, MetricsDispersion
)
from logger_config import setup_logger

logger = setup_logger(__name__)

# D.C. subreddit name - excluded from global metrics and rankings
DC_SUBREDDIT_NAME = 'washingtondc'

# Metric names for dispersion table
METRIC_NAMES = [
    'subscribers_7day', 'subscribers_30day',
    'posts_7day', 'posts_30day',
    'score_7day', 'score_30day',
    'comments_7day', 'comments_30day',
    'upvotes_7day', 'upvotes_30day',
]


def calculate_subreddit_rolling_stats(subreddit, calc_date):
    """
    Calculate rolling averages for a single subreddit.
    
    Args:
        subreddit: Subreddit object
        calc_date: date object for calculation
        
    Returns:
        dict with all calculated metrics, or None if insufficient data
    """
    # Date ranges for subscribers/posts (from SubredditDailyStats)
    end_date_snapshot = calc_date
    start_date_7day_snapshot = calc_date - timedelta(days=6)
    start_date_30day_snapshot = calc_date - timedelta(days=29)
    
    # Date ranges for engagement (from Post table, offset by 3 days)
    end_date_engagement = calc_date - timedelta(days=3)
    start_date_7day_engagement = calc_date - timedelta(days=9)
    start_date_30day_engagement = calc_date - timedelta(days=32)
    
    # Query SubredditDailyStats for subscriber/post data
    snapshots_7day = SubredditDailyStats.objects.filter(
        subreddit=subreddit,
        date_created__date__gte=start_date_7day_snapshot,
        date_created__date__lte=end_date_snapshot
    )
    
    snapshots_30day = SubredditDailyStats.objects.filter(
        subreddit=subreddit,
        date_created__date__gte=start_date_30day_snapshot,
        date_created__date__lte=end_date_snapshot
    )
    
    # Calculate subscriber/post averages
    stats_7day = snapshots_7day.aggregate(
        subscribers_avg=Avg('subscribers_count'),
        posts_avg=Avg('posts_count')
    )
    
    stats_30day = snapshots_30day.aggregate(
        subscribers_avg=Avg('subscribers_count'),
        posts_avg=Avg('posts_count')
    )
    
    # Query Post table for engagement data
    posts_7day = Post.objects.filter(
        subreddit=subreddit,
        created_local__gte=start_date_7day_engagement,
        created_local__lte=end_date_engagement,
        engagement_collected=True
    )
    
    posts_30day = Post.objects.filter(
        subreddit=subreddit,
        created_local__gte=start_date_30day_engagement,
        created_local__lte=end_date_engagement,
        engagement_collected=True
    )
    
    # Calculate engagement averages
    engagement_7day = posts_7day.aggregate(
        score_avg=Avg('score'),
        comments_avg=Avg('num_comments'),
        upvotes_avg=Avg('estimated_upvotes')
    )
    
    engagement_30day = posts_30day.aggregate(
        score_avg=Avg('score'),
        comments_avg=Avg('num_comments'),
        upvotes_avg=Avg('estimated_upvotes')
    )
    
    return {
        'subscribers_7day_avg': stats_7day['subscribers_avg'],
        'posts_7day_avg': stats_7day['posts_avg'],
        'score_7day_avg': engagement_7day['score_avg'],
        'comments_7day_avg': engagement_7day['comments_avg'],
        'upvotes_7day_avg': engagement_7day['upvotes_avg'],
        'subscribers_30day_avg': stats_30day['subscribers_avg'],
        'posts_30day_avg': stats_30day['posts_avg'],
        'score_30day_avg': engagement_30day['score_avg'],
        'comments_30day_avg': engagement_30day['comments_avg'],
        'upvotes_30day_avg': engagement_30day['upvotes_avg'],
    }


def calculate_wow_change(current_value, previous_value):
    """
    Calculate week-over-week percentage change.
    
    Returns:
        Float percentage change, or None if cannot calculate
    """
    if current_value is None or previous_value is None:
        return None
    if previous_value == 0:
        return None
    
    return ((current_value - previous_value) / previous_value) * 100


def get_previous_week_metrics(subreddit, calc_date):
    """
    Get metrics from 7 days ago for WoW calculation.
    
    Returns:
        SubredditMetrics object or None
    """
    previous_date = calc_date - timedelta(days=7)
    try:
        return SubredditMetrics.objects.get(subreddit=subreddit, date=previous_date)
    except SubredditMetrics.DoesNotExist:
        return None


def calculate_ranks(subreddit_metrics_list, metric_field):
    """
    Calculate ranks for a given metric across all subreddits.
    Higher values get better (lower) ranks.
    
    Args:
        subreddit_metrics_list: List of (subreddit, metrics_dict) tuples
        metric_field: String name of the metric to rank
        
    Returns:
        Dict mapping subreddit name to rank (1 = highest)
    """
    # Filter out D.C. and None values
    valid_entries = [
        (sub, metrics[metric_field])
        for sub, metrics in subreddit_metrics_list
        if sub.name.lower() != DC_SUBREDDIT_NAME.lower() and metrics.get(metric_field) is not None
    ]
    
    if not valid_entries:
        return {}
    
    # Sort by value descending (highest = rank 1)
    sorted_entries = sorted(valid_entries, key=lambda x: x[1], reverse=True)
    
    # Assign ranks
    ranks = {}
    for rank, (sub, value) in enumerate(sorted_entries, start=1):
        ranks[sub.name] = rank
    
    return ranks


def calculate_dispersion_stats(values):
    """
    Calculate dispersion statistics for a list of values.
    
    Args:
        values: List of numeric values (None values filtered out)
        
    Returns:
        Dict with median, std_dev, min_value, max_value, p25, p75
    """
    # Filter out None values
    clean_values = [v for v in values if v is not None]
    
    if len(clean_values) < 2:
        return {
            'median': clean_values[0] if clean_values else None,
            'std_dev': None,
            'min_value': clean_values[0] if clean_values else None,
            'max_value': clean_values[0] if clean_values else None,
            'p25': None,
            'p75': None,
        }
    
    sorted_values = sorted(clean_values)
    n = len(sorted_values)
    
    # Calculate percentile indices
    p25_idx = int(n * 0.25)
    p75_idx = int(n * 0.75)
    
    return {
        'median': statistics.median(clean_values),
        'std_dev': statistics.stdev(clean_values),
        'min_value': min(clean_values),
        'max_value': max(clean_values),
        'p25': sorted_values[p25_idx],
        'p75': sorted_values[p75_idx],
    }


def calculate_metrics_for_date(calc_date):
    """
    Main function to calculate all metrics for a given date.
    
    Args:
        calc_date: date object
    """
    logger.info(f"Calculating metrics for {calc_date}")
    
    # Get all subreddits
    subreddits = Subreddit.objects.all()
    logger.info(f"Processing {subreddits.count()} subreddits")
    
    # Step 1: Calculate metrics for each subreddit
    subreddit_metrics_data = []  # List of (subreddit, metrics_dict)
    
    for subreddit in subreddits:
        metrics = calculate_subreddit_rolling_stats(subreddit, calc_date)
        
        if metrics is None:
            logger.warning(f"Insufficient data for {subreddit.name}")
            continue
        
        # Calculate WoW changes
        previous_metrics = get_previous_week_metrics(subreddit, calc_date)
        
        if previous_metrics:
            metrics['subscribers_wow_change'] = calculate_wow_change(
                metrics['subscribers_7day_avg'], previous_metrics.subscribers_7day_avg
            )
            metrics['posts_wow_change'] = calculate_wow_change(
                metrics['posts_7day_avg'], previous_metrics.posts_7day_avg
            )
            metrics['score_wow_change'] = calculate_wow_change(
                metrics['score_7day_avg'], previous_metrics.score_7day_avg
            )
            metrics['comments_wow_change'] = calculate_wow_change(
                metrics['comments_7day_avg'], previous_metrics.comments_7day_avg
            )
            metrics['upvotes_wow_change'] = calculate_wow_change(
                metrics['upvotes_7day_avg'], previous_metrics.upvotes_7day_avg
            )
        else:
            metrics['subscribers_wow_change'] = None
            metrics['posts_wow_change'] = None
            metrics['score_wow_change'] = None
            metrics['comments_wow_change'] = None
            metrics['upvotes_wow_change'] = None
        
        subreddit_metrics_data.append((subreddit, metrics))
    
    # Step 2: Calculate ranks (excluding D.C.)
    rank_fields = [
        ('subscribers_7day_avg', 'subscribers_7day_rank'),
        ('posts_7day_avg', 'posts_7day_rank'),
        ('score_7day_avg', 'score_7day_rank'),
        ('comments_7day_avg', 'comments_7day_rank'),
        ('upvotes_7day_avg', 'upvotes_7day_rank'),
    ]
    
    all_ranks = {}
    for metric_field, rank_field in rank_fields:
        all_ranks[rank_field] = calculate_ranks(subreddit_metrics_data, metric_field)
    
    # Step 3: Save SubredditMetrics
    for subreddit, metrics in subreddit_metrics_data:
        is_dc = subreddit.name.lower() == DC_SUBREDDIT_NAME.lower()
        
        # Add ranks (None for D.C.)
        for metric_field, rank_field in rank_fields:
            if is_dc:
                metrics[rank_field] = None
            else:
                metrics[rank_field] = all_ranks[rank_field].get(subreddit.name)
        
        # Create or update SubredditMetrics
        SubredditMetrics.objects.update_or_create(
            subreddit=subreddit,
            date=calc_date,
            defaults=metrics
        )
    
    logger.info(f"Saved SubredditMetrics for {len(subreddit_metrics_data)} subreddits")
    
    # Step 4: Calculate GlobalMetrics (excluding D.C.)
    non_dc_metrics = [
        metrics for sub, metrics in subreddit_metrics_data
        if sub.name.lower() != DC_SUBREDDIT_NAME.lower()
    ]
    
    if non_dc_metrics:
        global_data = {
            'subscribers_7day_avg': safe_mean([m['subscribers_7day_avg'] for m in non_dc_metrics]),
            'posts_7day_avg': safe_mean([m['posts_7day_avg'] for m in non_dc_metrics]),
            'score_7day_avg': safe_mean([m['score_7day_avg'] for m in non_dc_metrics]),
            'comments_7day_avg': safe_mean([m['comments_7day_avg'] for m in non_dc_metrics]),
            'upvotes_7day_avg': safe_mean([m['upvotes_7day_avg'] for m in non_dc_metrics]),
            'subscribers_30day_avg': safe_mean([m['subscribers_30day_avg'] for m in non_dc_metrics]),
            'posts_30day_avg': safe_mean([m['posts_30day_avg'] for m in non_dc_metrics]),
            'score_30day_avg': safe_mean([m['score_30day_avg'] for m in non_dc_metrics]),
            'comments_30day_avg': safe_mean([m['comments_30day_avg'] for m in non_dc_metrics]),
            'upvotes_30day_avg': safe_mean([m['upvotes_30day_avg'] for m in non_dc_metrics]),
            'subreddits_included': len(non_dc_metrics),
        }
        
        # Calculate global WoW changes
        try:
            prev_global = GlobalMetrics.objects.get(date=calc_date - timedelta(days=7))
            global_data['subscribers_wow_change'] = calculate_wow_change(
                global_data['subscribers_7day_avg'], prev_global.subscribers_7day_avg
            )
            global_data['posts_wow_change'] = calculate_wow_change(
                global_data['posts_7day_avg'], prev_global.posts_7day_avg
            )
            global_data['score_wow_change'] = calculate_wow_change(
                global_data['score_7day_avg'], prev_global.score_7day_avg
            )
            global_data['comments_wow_change'] = calculate_wow_change(
                global_data['comments_7day_avg'], prev_global.comments_7day_avg
            )
            global_data['upvotes_wow_change'] = calculate_wow_change(
                global_data['upvotes_7day_avg'], prev_global.upvotes_7day_avg
            )
        except GlobalMetrics.DoesNotExist:
            global_data['subscribers_wow_change'] = None
            global_data['posts_wow_change'] = None
            global_data['score_wow_change'] = None
            global_data['comments_wow_change'] = None
            global_data['upvotes_wow_change'] = None
        
        GlobalMetrics.objects.update_or_create(
            date=calc_date,
            defaults=global_data
        )
        logger.info(f"Saved GlobalMetrics for {calc_date}")
    
    # Step 5: Calculate and save dispersion statistics
    
    # Global dispersion (across subreddits, excluding D.C.)
    metric_to_field = {
        'subscribers_7day': 'subscribers_7day_avg',
        'subscribers_30day': 'subscribers_30day_avg',
        'posts_7day': 'posts_7day_avg',
        'posts_30day': 'posts_30day_avg',
        'score_7day': 'score_7day_avg',
        'score_30day': 'score_30day_avg',
        'comments_7day': 'comments_7day_avg',
        'comments_30day': 'comments_30day_avg',
        'upvotes_7day': 'upvotes_7day_avg',
        'upvotes_30day': 'upvotes_30day_avg',
    }
    
    for metric_name, field_name in metric_to_field.items():
        values = [m[field_name] for m in non_dc_metrics]
        dispersion = calculate_dispersion_stats(values)
        
        MetricsDispersion.objects.update_or_create(
            date=calc_date,
            entity_type='global',
            subreddit=None,
            metric_name=metric_name,
            defaults=dispersion
        )
    
    logger.info(f"Saved global MetricsDispersion for {len(metric_to_field)} metrics")
    
    # Subreddit-level dispersion (across days within the rolling window)
    for subreddit, metrics in subreddit_metrics_data:
        # Get historical values for this subreddit over the past 7 days
        historical_metrics = SubredditMetrics.objects.filter(
            subreddit=subreddit,
            date__gte=calc_date - timedelta(days=6),
            date__lte=calc_date
        )
        
        if historical_metrics.count() < 2:
            continue  # Not enough data for dispersion
        
        for metric_name, field_name in metric_to_field.items():
            values = list(historical_metrics.values_list(field_name, flat=True))
            dispersion = calculate_dispersion_stats(values)
            
            MetricsDispersion.objects.update_or_create(
                date=calc_date,
                entity_type='subreddit',
                subreddit=subreddit,
                metric_name=metric_name,
                defaults=dispersion
            )
    
    logger.info(f"Saved subreddit MetricsDispersion")
    logger.info(f"Completed metrics calculation for {calc_date}")


def safe_mean(values):
    """Calculate mean, filtering out None values."""
    clean_values = [v for v in values if v is not None]
    if not clean_values:
        return None
    return sum(clean_values) / len(clean_values)


def backfill_metrics(days_back):
    """
    Backfill metrics for the specified number of days.
    
    Args:
        days_back: Number of days to backfill
    """
    today = date.today()
    
    logger.info(f"Starting backfill for {days_back} days")
    
    for i in range(days_back, -1, -1):  # Start from oldest to newest
        calc_date = today - timedelta(days=i)
        try:
            calculate_metrics_for_date(calc_date)
        except Exception as e:
            logger.error(f"Error calculating metrics for {calc_date}: {e}")
            continue
    
    logger.info(f"Backfill complete")


def main():
    """
    Main entry point.
    
    Usage:
        python calculate_metrics.py                  # Calculate for today
        python calculate_metrics.py 2025-12-01       # Calculate for specific date
        python calculate_metrics.py --backfill 30    # Backfill last 30 days
    """
    args = sys.argv[1:]
    
    if not args:
        # Default: calculate for today
        calculate_metrics_for_date(date.today())
    
    elif args[0] == '--backfill' and len(args) > 1:
        # Backfill mode
        days_back = int(args[1])
        backfill_metrics(days_back)
    
    else:
        # Specific date
        try:
            calc_date = datetime.strptime(args[0], '%Y-%m-%d').date()
            calculate_metrics_for_date(calc_date)
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            print("Usage:")
            print("  python calculate_metrics.py                  # Calculate for today")
            print("  python calculate_metrics.py 2025-12-01       # Specific date")
            print("  python calculate_metrics.py --backfill 30    # Backfill last 30 days")
            sys.exit(1)


if __name__ == "__main__":
    main()