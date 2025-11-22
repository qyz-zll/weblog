import os
import re

from django.db import transaction
from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from weblog import settings
from .models import User  # 仅导入自定义 User 主模型（删除内置 User 导入）

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, label="用户名")
    password = serializers.CharField(required=True, label="密码", write_only=True)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError({"detail": "用户名或密码错误！"})

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'avatar': user.avatar.url if user.avatar else None,
                'bio': user.bio
            }
        }

# 2. 注册序列化器（无错误，保留）
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(required=True, label="密码", write_only=True, min_length=6)
    password2 = serializers.CharField(required=True, label="确认密码", write_only=True)
    email = serializers.EmailField(required=True, label="邮箱")

    class Meta:
        model = User
        fields = ['username', 'password', 'password2', 'email', 'bio']
        extra_kwargs = {'bio': {'required': False}}

    def validate_password2(self, value):
        password = self.initial_data.get('password')
        if password != value:
            raise serializers.ValidationError("两次密码输入不一致！")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("用户名已被占用！")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("该邮箱已注册！")
        return value

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            bio=validated_data.get('bio', '')
        )
        return user

# 3. 用户信息序列化器（修正：删除重复定义，扩展统计字段，移除错误 source）
class UserInfoSerializer(serializers.ModelSerializer):
    """用户信息序列化器：包含基础信息+统计字段"""
    # 修正：直接映射 User 主模型字段，无需 source（User 本身有这些字段）
    create_time = serializers.DateTimeField(source='date_joined', read_only=True)  # 映射 User 的 date_joined
    last_login_time = serializers.DateTimeField(source='last_login', read_only=True)  # 映射 User 的 last_login
    # 统计字段：通过 SerializerMethodField 手动计算（关联模型需正确配置 related_name）
    article_count = serializers.SerializerMethodField(read_only=True)
    like_count = serializers.SerializerMethodField(read_only=True)
    comment_count = serializers.SerializerMethodField(read_only=True)
    view_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User  # 模型是自定义 User 主模型
        fields = [
            'id', 'username', 'email', 'bio', 'avatar',
            'create_time', 'last_login_time',
            'article_count', 'like_count', 'comment_count', 'view_count'
        ]
        read_only_fields = ['id', 'create_time', 'last_login_time']  # 仅可读字段
        extra_kwargs = {'avatar': {'read_only': True}}  # 头像通过单独接口上传

    # 统计字段：手动计算（需确保 User 模型关联了对应模型，且 related_name 正确）
    def get_article_count(self, obj):
        # 假设 User 关联 Article 模型，related_name='articles'
        return obj.articles.count() if hasattr(obj, 'articles') else 0

    def get_like_count(self, obj):
        # 假设 User 关联 Like 模型，related_name='likes'
        return obj.likes.count() if hasattr(obj, 'likes') else 0

    def get_comment_count(self, obj):
        # 假设 User 关联 Comment 模型，related_name='comments'
        return obj.comments.count() if hasattr(obj, 'comments') else 0

    def get_view_count(self, obj):
        # 计算所有文章的阅读量总和
        return sum(article.view_count for article in obj.articles.all()) if hasattr(obj, 'articles') else 0

# 4. 用户信息更新序列化器（修正：移除错误 source，简化更新逻辑）
class UserInfoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'bio', 'email']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': False},  # 邮箱可选，但不能是空字符串
            'bio': {'required': False, 'allow_blank': True},
            'username': {'required': True}
        }

    # 验证用户名：格式+唯一性
    def validate_username(self, value):
        cleaned_username = value.strip()
        if not cleaned_username:
            raise serializers.ValidationError("用户名不能为空（不能只包含空格）")
        if not re.match(r'^[\w.@+-]+$', cleaned_username):
            raise serializers.ValidationError("用户名只能包含字母、数字、@、.、+、-、_")
        current_user = self.context['request'].user
        if User.objects.filter(username=cleaned_username).exclude(id=current_user.id).exists():
            raise serializers.ValidationError("该用户名已被占用！")
        return cleaned_username

    # 验证邮箱：唯一性（模型 Meta 配置了 email 唯一，这里补充前端提示）
    def validate_email(self, value):
        if not value:
            return None  # 允许邮箱为空（若模型允许 null）
        cleaned_email = value.strip()
        current_user = self.context['request'].user
        if User.objects.filter(email=cleaned_email).exclude(id=current_user.id).exists():
            raise serializers.ValidationError("该邮箱已被注册！")
        return cleaned_email

    # 原子更新：确保数据一致性
    @transaction.atomic
    def update(self, instance, validated_data):
        print(f"更新用户 [{instance.id}]：{validated_data}")
        try:
            for key, value in validated_data.items():
                if key in self.Meta.fields:
                    setattr(instance, key, value)
            instance.save()  # 保存后，last_login_time 会自动更新（模型 auto_now）
            print(f"用户 [{instance.id}] 更新成功，新用户名：{instance.username}")
            return instance
        except Exception as e:
            print(f"更新失败：{str(e)}")
            raise serializers.ValidationError(f"更新失败：{str(e)}") from e

# 5. 头像上传序列化器（无错误，保留，确保模型是 User 主模型）
class AvatarUploadSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=True, write_only=True)

    class Meta:
        model = User
        fields = ['avatar']

    def validate_avatar(self, value):
        file_ext = os.path.splitext(value.name)[1][1:].lower()
        if file_ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise serializers.ValidationError(
                f'不支持的图片格式！仅支持 {", ".join(settings.ALLOWED_UPLOAD_EXTENSIONS)}'
            )
        if value.size > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(f'图片大小不能超过 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB')
        return value