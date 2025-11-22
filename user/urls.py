from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    FriendListView, ChatMessageView, SendMessageView,
    MarkAsReadView, UnreadCountView
)

urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("chat/friends/", FriendListView.as_view(), name="friend-list"),
    path("chat/messages/<int:friend_id>/", ChatMessageView.as_view(), name="chat-messages"),
    path("chat/send-message/", SendMessageView.as_view(), name="send-message"),
    path("chat/mark-as-read/", MarkAsReadView.as_view(), name="mark-as-read"),
    path("chat/unread-count/", UnreadCountView.as_view(), name="unread-count"),
]

urlpatterns = format_suffix_patterns(urlpatterns)