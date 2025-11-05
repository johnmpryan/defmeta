import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'defmeta.settings')
django.setup()

from tracker.models import Tag

TAGS_TO_CREATE = {
    'topic': [
        ('photography', 'Photos, cameras, photography spots and techniques'),
        ('community', 'Neighborhood issues, local groups, civic engagement'),
        ('agriculture', 'Farming, crops, livestock, rural issues'),
        ('travel', 'Travel planning, road trips, visiting the area'),
        ('shopping', 'Retail stores, malls, shopping recommendations'),
        ('science', 'Scientific topics, research, STEM discussions'),
        ('culture', 'Arts, museums, cultural events and heritage'),
        ('family', 'Family activities, parenting, family-friendly content'),
        ('wildlife', 'Animals, wildlife sightings, nature observation'),
        ('nature', 'Natural landscapes, outdoor activities, conservation'),
        ('economy', 'Economic conditions, business climate, financial topics'),
        ('legal', 'Legal questions, law, regulatory issues'),
    ],
    'content_type': [
        ('humor', 'Comedic content, jokes, funny observations'),  # Note: different from 'humorous' sentiment
        ('protest', 'Demonstrations, activism, social movements'),
        ('investigation', 'Investigative reporting, exposés'),
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