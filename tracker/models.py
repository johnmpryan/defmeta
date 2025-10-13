from django.db import models

class Subreddit(models.Model):
    name = models.CharField(max_length=100, unique=True)
    uri = models.URLField(max_length=200)
    subreddit_description = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subreddits'
        ordering = ['-date_created']
    
    def __str__(self):
        return self.name

class SubredditDailyStats(models.Model):
    subreddit = models.ForeignKey(Subreddit, on_delete=models.CASCADE)
    subscribers_count = models.IntegerField(null=True, blank=True)
    posts_two_weeks_count = models.IntegerField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subreddits_daily_stats'
        ordering = ['-date_created']
    
    def __str__(self):
        return f"{self.subreddit.name} - {str(self.date_created)}"