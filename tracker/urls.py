from django.urls import path
from tracker import views

app_name = 'tracker'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('r/<str:subreddit_name>/', views.subreddit_detail, name='subreddit_detail'),
]