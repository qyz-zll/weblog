"""
URL configuration for weblog project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.blog, name='blog')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='blog')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import path, include
from user import views
from user.views import UserInfoView, UpdateUserInfoView, FriendListView, ChatMessageView, SendMessageView,MarkAsReadView, UnreadCountView
from django.conf import settings
from django.conf.urls.static import static
from user.views import AvatarUploadView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.LoginView.as_view(), name='api_login'),  # 新增：JWT登录接口
    path('register/', views.RegisterView.as_view(), name='api_register'),#注册接口
    path('userinfo/', views.UserInfoView.as_view(), name='api_userinfo'),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    # 2. 刷新 Token 接口（Token 过期时使用）
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # 3. 用户信息接口（需 Token 认证，前端请求此接口获取用户信息）
    # path('', include('user.urls')),  # 假设用户相关接口在user app下
    path('upload-avatar/', AvatarUploadView.as_view(), name='upload-avatar'),  # 头像上传接口
    path('UpdateUserInfo/',UpdateUserInfoView.as_view(), name='UpdateUserInfo'),#修改用户信息
    path("", include("user.urls")),
    path('api/blogs/', include('blog.urls')),
]
# # 容许直接访问资源
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)