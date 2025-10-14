from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats
from django.db.models import Count

def homepage(request):
    # Annotate each subreddit with the count of related snapshots
    subreddits = Subreddit.objects.annotate(
        snapshot_count=Count('subredditdailystats')
    ).all()
    
    # Get the latest snapshot for each subreddit
    subreddit_data = []  # Changed variable name
    for subreddit in subreddits:
        latest_snapshot = subreddit.subredditdailystats_set.order_by('-date_created').first()
        subreddit_data.append({
            'subreddit': subreddit,
            'latest_snapshot': latest_snapshot,
            'snapshot_count': subreddit.snapshot_count
        })
    
    return render(request, 'tracker/homepage.html', {
        'subreddit_data': subreddit_data  # Changed to match template
    })

def subreddit_detail(request, subreddit_name):
    """Display detail page for a specific subreddit with snapshot history."""
    # Get the subreddit or return 404 if not found
    subreddit = get_object_or_404(Subreddit, name=subreddit_name)
    
    # Get all snapshots for this subreddit, newest first
    snapshots = SubredditDailyStats.objects.filter(
        subreddit=subreddit
    ).order_by('-date_created')
    
    # Paginate - 10 per page
    paginator = Paginator(snapshots, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'tracker/subreddit_detail.html', {
        'subreddit': subreddit,
        'page_obj': page_obj
    })