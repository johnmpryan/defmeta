import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Tag

TAGS_TO_CREATE = {
    'topic': [
        ('politics', 'Political discussions, elections, government'),
        ('weather', 'Weather conditions, forecasts, storms'),
        ('sports', 'Sports teams, games, athletic events'),
        ('food', 'Restaurants, recipes, dining recommendations'),
        ('tourism', 'Tourist attractions, travel tips, vacation planning'),
        ('education', 'Schools, universities, educational resources'),
        ('employment', 'Job opportunities, workplace issues, career advice'),
        ('housing', 'Real estate, rentals, housing market, neighborhoods'),
        ('transportation', 'Public transit, roads, traffic, commuting'),
        ('environment', 'Nature, parks, conservation, pollution'),
        ('crime', 'Public safety, law enforcement, criminal incidents'),
        ('health', 'Healthcare, medical services, wellness'),
        ('business', 'Local businesses, economy, commercial development'),
        ('entertainment', 'Events, concerts, movies, nightlife'),
        ('local_news', 'Breaking news, local media coverage'),
        ('history', 'Historical facts, local heritage, past events'),
        ('technology', 'Tech industry, innovation, digital services'),
        ('infrastructure', 'Utilities, construction, public works')
    ],
    'content_type': [
        ('question', 'User asking for information or help'),
        ('discussion', 'Open-ended conversation starter'),
        ('advice_request', 'Seeking recommendations or guidance'),
        ('photograph', 'Image post with visual content'),
        ('news_article', 'Link to news story or article'),
        ('personal_story', 'Anecdote or personal experience'),
        ('recommendation', 'Suggesting places, services, or things'),
        ('rant', 'Venting frustration or complaint'),
        ('announcement', 'Public notice or event information'),
        ('help_needed', 'Urgent request for assistance'),
        ('opinion', 'Sharing personal viewpoint or stance'),
        ('event', 'Upcoming or ongoing local event')
    ],
    'sentiment': [
        ('positive', 'Upbeat, appreciative, or celebratory tone'),
        ('negative', 'Critical, frustrated, or disappointed tone'),
        ('neutral', 'Factual, objective, or informational tone'),
        ('controversial', 'Divisive topic likely to spark debate'),
        ('humorous', 'Comedic, lighthearted, or satirical tone')
    ]
}

for category, tags_list in TAGS_TO_CREATE.items():
    for name, description in tags_list:
        Tag.objects.get_or_create(
            name=name,
            defaults={
                'category': category,
                'description': description
            }
        )
print(f"Created {Tag.objects.count()} tags")