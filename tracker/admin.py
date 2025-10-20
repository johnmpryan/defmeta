from django.contrib import admin
from .models import Subreddit, SubredditDailyStats, Post

@admin.register(Subreddit)
class SubredditAdmin(admin.ModelAdmin):
    list_display = ['name', 'population','timezone','region', 'subscribers_count_display','residents_over_18']
    search_fields = ['name']
    list_editable = ['population','residents_over_18','timezone','region']
    
    def subscribers_count_display(self, obj):
        latest = obj.subredditdailystats_set.order_by('-date_created').first()
        return latest.subscribers_count if latest else 'N/A'
    subscribers_count_display.short_description = 'Latest Subscribers'

@admin.register(SubredditDailyStats)
class SubredditDailyStatsAdmin(admin.ModelAdmin):
    list_display = ['subreddit', 'subscribers_count', 'posts_count', 'avg_post_score', 'date_created']
    list_filter = ['subreddit', 'date_created']
    readonly_fields = ['date_created', 'date_updated']

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        'subreddit',
        'title_preview',
        'author',
        'created_local',
        'score',
        'upvote_ratio',
        'num_comments',
        'engagement_collected',
    ]
    list_filter = [
        'subreddit',
        'engagement_collected',
        'is_removed',
        'created_local',
    ]
    search_fields = ['title', 'author', 'reddit_id']
    readonly_fields = ['reddit_id', 'created_utc', 'created_local', 'date_created', 'date_updated']
    date_hierarchy = 'created_local'
    list_per_page = 50  # More posts per page since you'll have many
    
    def title_preview(self, obj):
        """Show first 60 chars of title"""
        return obj.title[:60] + '...' if len(obj.title) > 60 else obj.title
    title_preview.short_description = 'Title'