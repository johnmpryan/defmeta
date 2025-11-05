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
    pop_density = models.IntegerField(null=True, blank=True)
    
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
    tags_collected = models.BooleanField(default=False)
    
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

class Tag(models.Model):
    CATEGORY_CHOICES = [
        ('topic', 'Topic'),
        ('content_type', 'Content Type'),
        ('sentiment', 'Sentiment'),
        ('geographic', 'Geographic'),
        ('temporal', 'Temporal'),
        ('meta', 'Meta'),
    ]
    
    name = models.CharField(max_length=50, unique=True, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    description = models.TextField(help_text="When to apply this tag - used for AI context")
    
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    is_primary = models.BooleanField(default=False, help_text="Primary tags shown more prominently")
    display_order = models.IntegerField(default=999)
    is_active = models.BooleanField(default=True)
    
    created_by = models.CharField(max_length=50, default='system', choices=[('ai', 'AI'), ('admin', 'Admin'), ('system', 'System')])
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tags'
        ordering = ['category', 'display_order', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['usage_count']),
        ]
    
    def __str__(self):
        return f"{self.category}: {self.name}"


class PostTag(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='tagged_posts')
    
    applied_by = models.CharField(max_length=50)
    applied_at = models.DateTimeField(auto_now_add=True)
    confidence_score = models.FloatField(null=True, blank=True)
    needs_review = models.BooleanField(default=False)
    
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.CharField(max_length=100, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'post_tags'
        unique_together = ['post', 'tag']
        indexes = [
            models.Index(fields=['post', 'tag']),
            models.Index(fields=['needs_review', 'reviewed']),
            models.Index(fields=['applied_at']),
        ]

class AITaggingLog(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    
    model_version = models.CharField(max_length=50)
    prompt_template = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=20, default='v1.0')
    
    raw_response = models.JSONField()
    tags_applied = models.JSONField()
    confidence_scores = models.JSONField(null=True)
    
    processing_time_ms = models.IntegerField(null=True)
    token_count = models.IntegerField(null=True)
    estimated_cost = models.DecimalField(max_digits=6, decimal_places=4, null=True)
    
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    
    date_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ai_tagging_logs'
        ordering = ['-date_created']
        indexes = [
            models.Index(fields=['-date_created']),
            models.Index(fields=['post', '-date_created']),
            models.Index(fields=['success']),
        ]

class Tag(models.Model):
    CATEGORY_CHOICES = [
        ('topic', 'Topic'),
        ('content_type', 'Content Type'),
        ('sentiment', 'Sentiment'),
        ('geographic', 'Geographic'),
        ('temporal', 'Temporal'),
        ('meta', 'Meta'),
    ]
    
    name = models.CharField(max_length=50, unique=True, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    description = models.TextField(help_text="When to apply this tag - used for AI context")
    
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    is_primary = models.BooleanField(default=False, help_text="Primary tags shown more prominently")
    display_order = models.IntegerField(default=999)
    is_active = models.BooleanField(default=True)
    
    created_by = models.CharField(max_length=50, default='system', choices=[('ai', 'AI'), ('admin', 'Admin'), ('system', 'System')])
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tags'
        ordering = ['category', 'display_order', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['usage_count']),
        ]
    
    def __str__(self):
        return f"{self.category}: {self.name}"


class PostTag(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='tagged_posts')
    
    applied_by = models.CharField(max_length=50)
    applied_at = models.DateTimeField(auto_now_add=True)
    confidence_score = models.FloatField(null=True, blank=True)
    needs_review = models.BooleanField(default=False)
    
    reviewed = models.BooleanField(default=False)
    reviewed_by = models.CharField(max_length=100, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'post_tags'
        unique_together = ['post', 'tag']
        indexes = [
            models.Index(fields=['post', 'tag']),
            models.Index(fields=['needs_review', 'reviewed']),
            models.Index(fields=['applied_at']),
        ]


class AITaggingLog(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    
    model_version = models.CharField(max_length=50)
    prompt_template = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=20, default='v1.0')
    
    raw_response = models.JSONField()
    tags_applied = models.JSONField()
    confidence_scores = models.JSONField(null=True)
    
    processing_time_ms = models.IntegerField(null=True)
    token_count = models.IntegerField(null=True)
    estimated_cost = models.DecimalField(max_digits=6, decimal_places=4, null=True)
    
    success = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    
    date_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ai_tagging_logs'
        ordering = ['-date_created']
        indexes = [
            models.Index(fields=['-date_created']),
            models.Index(fields=['post', '-date_created']),
            models.Index(fields=['success']),
        ]