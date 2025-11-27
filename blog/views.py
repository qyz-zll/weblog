# blog/views.py
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.authentication import JWTAuthentication

from user.models import FriendSerializer
from .models import Blog
from .serializers import BlogSerializer, BlogListSerializer, BlogDetailSerializer

# ========== 直接在 views.py 内定义 success_response（无需外部导入）==========
def success_response(data=None, message="请求成功"):
    return Response({
        'code': status.HTTP_200_OK,
        'message': message,
        'data': data
    })

# ========== 自定义权限类 ==========
class IsAuthorOrReadOnly(permissions.BasePermission):
    """仅作者可编辑/删除，其他人只读"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user

# ========== 视图集核心逻辑 ==========
class BlogViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['author__username', 'is_public', 'status']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        """列表页：公开+已发布；我的文章：当前用户所有状态"""
        if self.action == 'my_blogs':
            return Blog.objects.filter(author=self.request.user)
        return Blog.objects.filter(is_public=True, status='published')

    def get_permissions(self):
        """权限控制：创建需登录，编辑/删除仅作者"""
        if self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        """动态序列化器：列表/我的文章用简化版，详情用完整版"""
        if self.action == 'list' or self.action == 'my_blogs':
            return BlogListSerializer
        elif self.action == 'retrieve':
            return BlogDetailSerializer
        else:
            return BlogSerializer

    @action(
        detail=False,
        authentication_classes=[JWTAuthentication],  # 单独指定JWT认证
        permission_classes=[permissions.IsAuthenticated]
    )
    def my_blogs(self, request):
        print("=" * 50)
        print("请求头Authorization：", request.META.get('HTTP_AUTHORIZATION', '无'))  # 看请求头是否传到后端
        print("用户是否认证：", request.user.is_authenticated)  # 关键：是否为True
        print("当前用户：", request.user)  # 应为user_id=6的用户名，而非AnonymousUser
        print("JWT认证结果：", request.auth)  # 应为<rest_framework_simplejwt.tokens.AccessToken object>
        print("=" * 50)
        """当前登录用户的所有文章（含草稿/已发布）"""
        # 增加防护：确保用户已认证
        if not request.user.is_authenticated:
            return Response({
                'code': 401,
                'message': '请先登录',
                'data': None
            }, status=status.HTTP_401_UNAUTHORIZED)

        blogs = self.get_queryset()
        serializer = self.get_serializer(blogs, many=True)
        return success_response(serializer.data, message="我的博客列表")