# blog/views.py
from rest_framework import viewsets, permissions, filters

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
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from .serializers import BlogSerializer, BlogListSerializer, BlogDetailSerializer
from .permissions import IsAuthorOrReadOnly  # 确保导入自定义权限类
from rest_framework import viewsets, status, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from .models import Blog, BlogLike, BlogShare, BlogComment
from .serializers import BlogCommentSerializer, AddBlogCommentSerializer

class BlogViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['author__username', 'is_public', 'status']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'updated_at']

    def get_queryset(self):
        """
        修正逻辑：
        - my_blogs/list：原有逻辑不变
        - destroy/update/partial_update：返回当前用户的所有博客（允许删除自己的草稿/未公开博客）
        """
        user = self.request.user
        # 编辑/删除动作：查询当前用户的所有博客（不受公开/状态限制）
        if self.action in ['destroy', 'update', 'partial_update', 'publish', 'unpublish']:
            return Blog.objects.filter(author=user) if user.is_authenticated else Blog.objects.none()
        # 我的博客列表：当前用户所有博客
        elif self.action == 'my_blogs':
            return Blog.objects.filter(author=user)
        # 公开列表：仅公开+已发布
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

    # ========== 重写默认方法，添加统一响应格式 + 状态码 ==========
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            'code': status.HTTP_200_OK,
            'message': '博客创建成功',
            'data': serializer.data
        }, status=status.HTTP_200_OK, headers=headers)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'code': status.HTTP_200_OK,
            'message': '获取博客详情成功',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response({
            'code': status.HTTP_200_OK,
            'message': '博客更新成功',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'code': status.HTTP_200_OK,
            'message': '博客删除成功',
            'data': None
        }, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'code': status.HTTP_200_OK,
                'message': '获取博客列表成功',
                'data': serializer.data
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'code': status.HTTP_200_OK,
            'message': '获取博客列表成功',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    # ========== 自定义action保持并优化状态码 ==========
    @action(
        detail=False,
        authentication_classes=[JWTAuthentication],
        permission_classes=[permissions.IsAuthenticated]
    )
    def my_blogs(self, request):
        print("=" * 50)
        print("请求头Authorization：", request.META.get('HTTP_AUTHORIZATION', '无'))
        print("用户是否认证：", request.user.is_authenticated)
        print("当前用户：", request.user)
        print("JWT认证结果：", request.auth)
        print("=" * 50)

        if not request.user.is_authenticated:
            return Response({
                'code': status.HTTP_401_UNAUTHORIZED,
                'message': '请先登录',
                'data': None
            }, status=status.HTTP_401_UNAUTHORIZED)

        blogs = self.get_queryset()
        serializer = self.get_serializer(blogs, many=True)
        return Response({
            'code': status.HTTP_200_OK,
            'message': '我的博客列表获取成功',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated], authentication_classes=[JWTAuthentication])
    def publish(self, request, pk=None):
        blog = self.get_object()
        if blog.author != request.user:
            return Response({
                'code': status.HTTP_403_FORBIDDEN,
                'message': '无权限发布他人博客',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)
        blog.status = 'published'
        blog.save()
        serializer = BlogSerializer(blog, context={'request': request})
        return Response({
            'code': status.HTTP_200_OK,
            'message': '博客发布成功',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated], authentication_classes=[JWTAuthentication])
    def unpublish(self, request, pk=None):
        blog = self.get_object()
        if blog.author != request.user:
            return Response({
                'code': status.HTTP_403_FORBIDDEN,
                'message': '无权限操作他人博客',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)
        blog.status = 'draft'
        blog.save()
        serializer = BlogSerializer(blog, context={'request': request})
        return Response({
            'code': status.HTTP_200_OK,
            'message': '博客已撤回为草稿',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


# 1. 博客点赞接口
class BlogLikeView(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        blog_id = kwargs.get("pk")
        blog = get_object_or_404(Blog, id=blog_id, is_public=True, status="published")
        user = request.user

        # 判断是否已点赞：已点赞则取消，未点赞则添加
        like, created = BlogLike.objects.get_or_create(blog=blog, user=user)
        if not created:
            # 取消点赞
            like.delete()
            blog.like_count = max(0, blog.like_count - 1)
            blog.save()
            return Response({
                "code": 200,
                "message": "取消点赞成功",
                "data": {"is_liked": False, "like_count": blog.like_count}
            }, status=status.HTTP_200_OK)
        else:
            # 新增点赞
            blog.like_count += 1
            blog.save()
            return Response({
                "code": 200,
                "message": "点赞成功",
                "data": {"is_liked": True, "like_count": blog.like_count}
            }, status=status.HTTP_200_OK)

# 2. 博客转发接口
class BlogShareView(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        blog_id = kwargs.get("pk")
        blog = get_object_or_404(Blog, id=blog_id, is_public=True, status="published")
        user = request.user

        # 记录转发行为（允许重复转发）
        BlogShare.objects.create(blog=blog, user=user)
        blog.share_count += 1
        blog.save()

        return Response({
            "code": 200,
            "message": "转发成功",
            "data": {"share_count": blog.share_count}
        }, status=status.HTTP_200_OK)

# 3. 发布评论接口
class AddBlogCommentView(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = AddBlogCommentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        blog = serializer.context["blog"]
        content = serializer.validated_data["content"]

        # 创建评论
        comment = BlogComment.objects.create(
            blog=blog,
            author=request.user,
            content=content
        )

        # 更新博客评论数
        blog.comment_count += 1
        blog.save()

        return Response({
            "code": 200,
            "message": "评论发布成功",
            "data": BlogCommentSerializer(comment).data
        }, status=status.HTTP_200_OK)

# 4. 评论列表接口（分页）
# blog/views.py（修改BlogCommentListView，支持分页）
from rest_framework.pagination import PageNumberPagination


class BlogCommentListView(viewsets.ModelViewSet):
    serializer_class = BlogCommentSerializer
    pagination_class = PageNumberPagination  # 启用分页
    queryset = Blog.objects.all()

    def list(self, request, *args, **kwargs):
        try:
            blog = self.get_object()  # 通过pk=19获取博客（详情页ID）
        except Blog.DoesNotExist:
            return Response({
                "code": 404,
                "message": f"博客ID {kwargs.get('pk')} 不存在",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

        queryset = BlogComment.objects.filter(
            blog=blog,
            blog__is_public=True,
            blog__status='published'
        ).order_by("-created_at")

        # 分页处理
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "code": 200,
                "message": "获取评论列表成功",
                "data": serializer.data,
                "total": queryset.count()
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "code": 200,
            "message": "获取评论列表成功",
            "data": serializer.data,
            "total": queryset.count()
        }, status=status.HTTP_200_OK)