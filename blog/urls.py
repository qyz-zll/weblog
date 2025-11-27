# blog/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BlogViewSet

# 1. 用DefaultRouter注册ViewSet（自动生成所有路由，包括自定义action）
router = DefaultRouter()
router.register('', BlogViewSet, basename='blog')

# 2. 直接include router生成的urls（包含list/retrieve/create/update/destroy/my_blogs等所有接口）
urlpatterns = [
    path('', include(router.urls)),  # 关键：启用DefaultRouter的自动路由
]