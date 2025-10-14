from django.contrib import admin
from .models import Subreddit, SubredditDailyStats

@admin.register(Subreddit)
class SubredditAdmin(admin.ModelAdmin):
    list_display = ['name', 'population', 'subscribers_count_display', 'date_created']
    search_fields = ['name']
    list_editable = ['population']
    
    def subscribers_count_display(self, obj):
        latest = obj.subredditdailystats_set.order_by('-date_created').first()
        return latest.subscribers_count if latest else 'N/A'
    subscribers_count_display.short_description = 'Latest Subscribers'

@admin.register(SubredditDailyStats)
class SubredditDailyStatsAdmin(admin.ModelAdmin):
    list_display = ['subreddit', 'subscribers_count', 'posts_count', 'avg_post_score', 'date_created']
    list_filter = ['subreddit', 'date_created']
    readonly_fields = ['date_created', 'date_updated']