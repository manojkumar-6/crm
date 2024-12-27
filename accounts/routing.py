# your_app/routing.py

from django.urls import re_path
from . import views

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<phone>\d+)/$', views.ChatConsumer.as_asgi()),  # WebSocket URL for each phone number
    re_path(r'ws/chat/(?P<room_name>\w+)/$', views.VideoChatConsumer.as_asgi()),
]
