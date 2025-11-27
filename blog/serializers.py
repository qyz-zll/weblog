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