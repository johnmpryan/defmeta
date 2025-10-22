from django.db import models

class Subreddit(models.Model):
    name = models.CharField(max_length=100, unique=True)
    uri = models.URLField(max_length=200)
    subreddit_description = models.TextField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    land_area = models.IntegerField(null=True, blank=True)
    region = models.CharField(max_length=100,null=True, blank=True)
    timezone = models.CharField(max_length=100,null=True, blank=True)
    residents_over_18 = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'subreddits'
        ordering = ['-date_created']
    
    def __str__(self):
        return self.name

class SubredditDailyStats(models.Model):
    subreddit = models.ForeignKey(Subreddit, on_delete=models.CASCADE)
    subscribers_count = models.IntegerField(null=True, blank=True)
    posts_count = models.IntegerField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    avg_post_score = models.FloatField(null=True, blank=True)
    avg_upvote_ratio = models.FloatField(null=True, blank=True)
    total_comments = models.IntegerField(null=True, blank=True)
    engagement_collected = models.BooleanField(default=False)  # Track if we've collected this yet
    
    # Total vote fields (aggregated from Post table)
    total_estimated_upvotes = models.IntegerField(null=True, blank=True)
    total_estimated_downvotes = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'subreddits_daily_stats'
        ordering = ['-date_created']

    def __str__(self):
        return f"{self.subreddit.name} - {str(self.date_created)}"

class Post(models.Model):
    subreddit = models.ForeignKey(Subreddit, on_delete=models.CASCADE)
    reddit_id = models.CharField(max_length=20, unique=True)
    title = models.TextField()
    author = models.CharField(max_length=100)
    body = models.TextField(null=True, blank=True)
    
    # Content type fields
    url = models.URLField(max_length=500, null=True, blank=True)
    is_self = models.BooleanField(default=False)
    permalink = models.CharField(max_length=300, null=True, blank=True)
    
    # Metadata fields
    over_18 = models.BooleanField(default=False)
    spoiler = models.BooleanField(default=False)
    stickied = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)
    link_flair_text = models.CharField(max_length=100, null=True, blank=True)
    distinguished = models.CharField(max_length=20, null=True, blank=True)
    
    # Timestamp fields
    created_utc = models.DateTimeField()  # UTC timestamp from Reddit
    created_local = models.DateTimeField()  # Local timezone for the state
    
    # Engagement fields (populated 3 days later)
    score = models.IntegerField(null=True, blank=True)
    upvote_ratio = models.FloatField(null=True, blank=True)
    num_comments = models.IntegerField(null=True, blank=True)
    is_removed = models.BooleanField(default=False)
    engagement_collected = models.BooleanField(default=False)
    
    # Estimated vote fields (calculated from score and upvote_ratio)
    estimated_upvotes = models.IntegerField(null=True, blank=True)
    estimated_downvotes = models.IntegerField(null=True, blank=True)
    
    # Django timestamps
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'posts'
        ordering = ['-created_utc']
        indexes = [
            models.Index(fields=['subreddit', 'created_local']),
            models.Index(fields=['engagement_collected', 'created_utc']),
        ]
    
    def __str__(self):
        return f"{self.subreddit.name}: {self.title[:50]}..."