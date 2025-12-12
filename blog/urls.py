# blog/urls.py（子路由）
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BlogViewSet,
    BlogLikeView,
    BlogShareView,
    AddBlogCommentView,
    BlogCommentListView
)

# 1. 保留BlogViewSet核心路由（注册到空路径，兼容原有功能）
router = DefaultRouter()
router.register('', BlogViewSet, basename='blog')

# 2. 匹配前端请求路径（主路由api/blogs/ + 子路由<blogId>/like/ = api/blogs/<blogId>/like/ → 前端api/blog/${blogId}/like/需微调，或主路由改api/blog/）
# 🌟 关键：子路由直接写 <blogId>/like/，匹配前端 api/blog/${blogId}/like/（主路由需改为 api/blog/）
urlpatterns = [
    # 点赞：主路由api/blog/ + 子路由<blogId>/like/ = api/blog/19/like/（匹配前端）
    path('<int:blogId>/like/', BlogLikeView.as_view({'post': 'create'}), name='blog-like'),
    # 转发：主路由api/blog/ + 子路由<blogId>/share/ = api/blog/19/share/（匹配前端）
    path('<int:blogId>/share/', BlogShareView.as_view({'post': 'create'}), name='blog-share'),
    # 评论列表：主路由api/blog/ + 子路由comment/list/ = api/blog/comment/list/（匹配前端）
    path('<int:pk>/comment/list/', BlogCommentListView.as_view({'get': 'list'}), name='blog-comment-list'),
    # 发布评论（补充）
    path('<int:blogId>/comment/add/', AddBlogCommentView.as_view({'post': 'create'}), name='blog-comment-add'),
    # 原有BlogViewSet路由
    path('', include(router.urls)),
]