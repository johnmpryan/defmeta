from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from tracker.models import Subreddit, SubredditDailyStats

def homepage(request):
    """Display all tracked subreddits with their latest stats."""
    # Get all subreddits, ordered alphabetically
    subreddits = Subreddit.objects.all().order_by('name')
    
    # For each subreddit, get its latest snapshot
    subreddit_data = []
    for subreddit in subreddits:
        latest_snapshot = SubredditDailyStats.objects.filter(
            subreddit=subreddit
        ).order_by('-date_created').first()
        
        subreddit_data.append({
            'subreddit': subreddit,
            'latest_snapshot': latest_snapshot
        })
    
    return render(request, 'tracker/homepage.html', {
        'subreddit_data': subreddit_data
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