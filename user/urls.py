from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    FriendListView, ChatMessageView, SendMessageView,
    MarkAsReadView, UnreadCountView, SendFriendRequestView, MyFriendRequestsView, HandleFriendRequestView,
    CancelFriendRequestView, DeleteFriendView, UserPublicDetailView
)

urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("chat/friends/", FriendListView.as_view(), name="friend-list"),
    path("chat/messages/<int:friend_id>/", ChatMessageView.as_view(), name="chat-messages"),
    path("chat/send-message/", SendMessageView.as_view(), name="send-message"),
    path("chat/mark-as-read/", MarkAsReadView.as_view(), name="mark-as-read"),
    path("chat/unread-count/", UnreadCountView.as_view(), name="unread-count"),
    path("friend-request/send/", SendFriendRequestView.as_view(), name="send-friend-request"),  # 发送申请
    path("friend-request/my/", MyFriendRequestsView.as_view(), name="my-friend-requests"),    # 我的申请列表（收到的）
    path("friend-request/handle/", HandleFriendRequestView.as_view(), name="handle-friend-request"),  # 处理申请
    path("friend-request/cancel/<int:friend_id>/", CancelFriendRequestView.as_view(), name="cancel-friend-request"),  # 取消申请
    path("friend/delete/<int:friend_id>/", DeleteFriendView.as_view(), name="delete-friend"),  # 删除好友
    path('users/<int:id>/', UserPublicDetailView.as_view(), name='user-public-detail'),
]

urlpatterns = format_suffix_patterns(urlpatterns)