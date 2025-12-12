# blog/serializers.py
from rest_framework import serializers
from .models import Blog
from django.conf import settings  # 新增：动态引用用户模型
from django.contrib.auth import get_user_model  # 新增：获取实际用户模型

User = get_user_model()  # 动态获取用户模型（兼容默认/自定义）

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User  # 用动态获取的User模型，而非硬编码
        fields = ['id', 'username', 'email']

class BlogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'title', 'content', 'cover_image', 'is_public', 'status']
        read_only_fields = ['author', 'created_at', 'updated_at']

    def create(self, validated_data):
        # 增加request存在性判断
        if 'request' in self.context:
            validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

class BlogListSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = ['id', 'title', 'author', 'created_at', 'cover_image_url', 'is_public', 'status']

    def get_cover_image_url(self, obj):
        # 关键修复：先判断request是否存在，避免KeyError
        request = self.context.get('request')
        if obj.cover_image and request:
            return request.build_absolute_uri(obj.cover_image.url)
        return None

class BlogDetailSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Blog
        fields = ['id', 'title', 'content', 'author', 'created_at', 'updated_at', 'cover_image_url', 'is_public', 'status']

    def get_cover_image_url(self, obj):
        # 同样增加request存在性判断
        request = self.context.get('request')
        if obj.cover_image and request:
            return request.build_absolute_uri(obj.cover_image.url)
        return None

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

class BlogCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['title', 'content', 'cover_image', 'is_public', 'status']
        extra_kwargs = {
            'title': {'required': True, 'max_length': 200},
            'content': {'required': True},
            'status': {'default': 'draft', 'choices': Blog.STATUS_CHOICES}
        }


from rest_framework import serializers
from .models import Blog, BlogComment

# 评论序列化器（列表/发布）
class BlogCommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source="author.username", read_only=True)  # 嵌套作者用户名

    class Meta:
        model = BlogComment
        fields = ["id", "author_username", "content", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

# 发布评论的入参序列化器
class AddBlogCommentSerializer(serializers.Serializer):
    blog_id = serializers.IntegerField(label="博客ID")
    content = serializers.CharField(label="评论内容", min_length=1, max_length=500)

    def validate_blog_id(self, value):
        """验证博客存在且公开"""
        try:
            blog = Blog.objects.get(id=value, is_public=True, status="published")
            self.context["blog"] = blog  # 缓存博客对象，供后续使用
        except Blog.DoesNotExist:
            raise serializers.ValidationError({"code": 400, "message": "博客不存在或未公开"})
        return value