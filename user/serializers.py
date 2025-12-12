import os
import re
import pytz
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.db import models
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

from weblog import settings
from .models import User, Friend, ChatMessage


# ===================== 基础序列化器（登录/注册） =====================
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


# ===================== 用户信息序列化器 =====================
class UserInfoSerializer(serializers.ModelSerializer):
    """用户信息序列化器：包含基础信息+统计字段"""
    create_time = serializers.DateTimeField(source='date_joined', read_only=True)
    last_login_time = serializers.DateTimeField(source='last_login', read_only=True)
    article_count = serializers.SerializerMethodField(read_only=True)
    like_count = serializers.SerializerMethodField(read_only=True)
    comment_count = serializers.SerializerMethodField(read_only=True)
    view_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'bio', 'avatar',
            'create_time', 'last_login_time',
            'article_count', 'like_count', 'comment_count', 'view_count'
        ]
        read_only_fields = ['id', 'create_time', 'last_login_time']
        extra_kwargs = {'avatar': {'read_only': True}}

    def get_article_count(self, obj):
        return obj.articles.count() if hasattr(obj, 'articles') else 0

    def get_like_count(self, obj):
        return obj.likes.count() if hasattr(obj, 'likes') else 0

    def get_comment_count(self, obj):
        return obj.comments.count() if hasattr(obj, 'comments') else 0

    def get_view_count(self, obj):
        return sum(article.view_count for article in obj.articles.all()) if hasattr(obj, 'articles') else 0


class UserInfoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'bio', 'email']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': False},
            'bio': {'required': False, 'allow_blank': True},
            'username': {'required': True}
        }

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

    def validate_email(self, value):
        if not value:
            return None
        cleaned_email = value.strip()
        current_user = self.context['request'].user
        if User.objects.filter(email=cleaned_email).exclude(id=current_user.id).exists():
            raise serializers.ValidationError("该邮箱已被注册！")
        return cleaned_email

    @transaction.atomic
    def update(self, instance, validated_data):
        try:
            for key, value in validated_data.items():
                if key in self.Meta.fields:
                    setattr(instance, key, value)
            instance.save()
            return instance
        except Exception as e:
            raise serializers.ValidationError(f"更新失败：{str(e)}") from e


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


# ===================== 好友/聊天核心序列化器（重点修复） =====================
class UserBasicSerializer(serializers.ModelSerializer):
    """用户基础信息序列化器（用于好友列表）- 修复：北京时间+布尔值在线状态"""
    avatar = serializers.SerializerMethodField()
    is_online = serializers.SerializerMethodField()  # 返回布尔值（适配前端）
    last_active = serializers.SerializerMethodField()  # 北京时间格式化

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "is_online", "last_active"]

    def get_avatar(self, obj):
        """返回完整头像URL，兜底默认头像"""
        if obj.avatar and hasattr(obj.avatar, 'url'):
            return f"http://127.0.0.1:8000{obj.avatar.url}"
        return "http://127.0.0.1:8000/media/avatars/default.png"

    def get_is_online(self, obj):
        """
        在线状态：返回布尔值（true=在线，false=离线）
        逻辑：3分钟内last_active=在线，否则离线
        """
        if hasattr(obj, 'last_active') and obj.last_active:
            time_diff = timezone.now() - obj.last_active
            return time_diff.total_seconds() < 180  # 直接返回布尔值
        # 无last_active时，用last_login兜底
        elif obj.last_login:
            time_diff = timezone.now() - obj.last_login
            return time_diff.total_seconds() < 180
        return False  # 兜底离线

    def get_last_active(self, obj):
        """
        最后活跃时间：转换为北京时间（东8区）后格式化
        优先级：last_active > last_login > 未知
        """
        tz_beijing = pytz.timezone('Asia/Shanghai')

        # 优先用last_active
        if hasattr(obj, 'last_active') and obj.last_active:
            # UTC转北京时间
            if obj.last_active.tzinfo is None:
                last_active_utc = pytz.UTC.localize(obj.last_active)
            else:
                last_active_utc = obj.last_active
            last_active_bj = last_active_utc.astimezone(tz_beijing)
            return last_active_bj.strftime("%Y-%m-%d %H:%M:%S")

        # 降级用last_login
        elif obj.last_login:
            if obj.last_login.tzinfo is None:
                last_login_utc = pytz.UTC.localize(obj.last_login)
            else:
                last_login_utc = obj.last_login
            last_login_bj = last_login_utc.astimezone(tz_beijing)
            return last_login_bj.strftime("%Y-%m-%d %H:%M:%S")

        return "未知"


class FriendListSerializer(serializers.ModelSerializer):
    """好友列表序列化器 - 修复：字段兼容+时间格式化"""
    friend_info = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    last_message_time = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Friend
        fields = ["friend_info", "last_message", "last_message_time", "unread_count"]

    def get_friend_info(self, obj):
        """返回好友基础信息（含北京时间/布尔值在线状态）"""
        current_user = self.context.get("request").user
        friend_user = obj.friend if obj.user == current_user else obj.user
        return UserBasicSerializer(friend_user, context=self.context).data

    def get_last_message(self, obj):
        """获取与该好友的最后一条消息"""
        current_user = self.context.get("request").user
        friend_user = obj.friend if obj.user == current_user else obj.user
        last_msg = ChatMessage.objects.filter(
            models.Q(sender=current_user, receiver=friend_user) |
            models.Q(sender=friend_user, receiver=current_user)
        ).order_by("-send_time").first()
        return last_msg.content if last_msg else ""

    def get_last_message_time(self, obj):
        """最后消息时间：转换为北京时间"""
        current_user = self.context.get("request").user
        friend_user = obj.friend if obj.user == current_user else obj.user
        last_msg = ChatMessage.objects.filter(
            models.Q(sender=current_user, receiver=friend_user) |
            models.Q(sender=friend_user, receiver=current_user)
        ).order_by("-send_time").first()

        if last_msg and last_msg.send_time:
            tz_beijing = pytz.timezone('Asia/Shanghai')
            if last_msg.send_time.tzinfo is None:
                send_time_utc = pytz.UTC.localize(last_msg.send_time)
            else:
                send_time_utc = last_msg.send_time
            send_time_bj = send_time_utc.astimezone(tz_beijing)
            return send_time_bj.strftime("%Y-%m-%d %H:%M:%S")
        return ""

    def get_unread_count(self, obj):
        """统计未读消息数（修复：字段存在性校验）"""
        current_user = self.context.get("request").user
        friend_user = obj.friend if obj.user == current_user else obj.user
        # 确保ChatMessage有is_read字段
        if hasattr(ChatMessage, 'is_read'):
            return ChatMessage.objects.filter(
                sender=friend_user, receiver=current_user, is_read=False
            ).count()
        return 0  # 无is_read字段时兜底0

    @classmethod
    def setup_eager_loading(cls, queryset):
        return queryset.filter(is_approved=True)


class ChatMessageSerializer(serializers.ModelSerializer):
    """聊天消息序列化器 - 修复：头像URL+北京时间"""
    sender_avatar = serializers.SerializerMethodField()
    receiver_avatar = serializers.SerializerMethodField()
    send_time = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = ["id", "sender", "receiver", "content", "send_time", "sender_avatar", "receiver_avatar", "is_read"]
        read_only_fields = ["sender", "send_time", "is_read"]

    def get_sender_avatar(self, obj):
        if obj.sender.avatar and hasattr(obj.sender.avatar, 'url'):
            return f"http://127.0.0.1:8000{obj.sender.avatar.url}"
        return "http://127.0.0.1:8000/media/avatars/default.png"

    def get_receiver_avatar(self, obj):
        if obj.receiver.avatar and hasattr(obj.receiver.avatar, 'url'):
            return f"http://127.0.0.1:8000{obj.receiver.avatar.url}"
        return "http://127.0.0.1:8000/media/avatars/default.png"

    def get_send_time(self, obj):
        """消息发送时间：转换为北京时间"""
        tz_beijing = pytz.timezone('Asia/Shanghai')
        if obj.send_time.tzinfo is None:
            send_time_utc = pytz.UTC.localize(obj.send_time)
        else:
            send_time_utc = obj.send_time
        send_time_bj = send_time_utc.astimezone(tz_beijing)
        return send_time_bj.strftime("%Y-%m-%d %H:%M:%S")


# ===================== 辅助序列化器 =====================
class SendMessageSerializer(serializers.Serializer):
    friend_id = serializers.IntegerField()
    content = serializers.CharField(max_length=500)


class MarkAsReadSerializer(serializers.Serializer):
    friend_id = serializers.IntegerField()


class UserPublicSerializer(serializers.ModelSerializer):
    """仅返回公开字段：id、username、avatar"""

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar']
        read_only_fields = fields


from rest_framework import serializers
from .models import User, Friend

# 完全恢复你最初的Serializer（不是ModelSerializer）+ 仅加code，无其他改动
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Friend


class SendFriendRequestSerializer(serializers.Serializer):
    """发送好友申请：仅需被申请人ID（返回统一格式错误）"""
    friend_id = serializers.IntegerField(label="被申请人ID")

    def validate_friend_id(self, value):
        """验证：1. 不能添加自己 2. 不能重复申请 3. 被申请人存在"""
        current_user = self.context["request"].user
        # 不能添加自己
        if value == current_user.id:
            # 抛出包含friend_id的统一格式错误
            raise serializers.ValidationError({
                "code": 400,
                "message": "不能添加自己为好友",
                "data": {"friend_id": value}  # 携带被申请人ID
            })
        # 检查是否已发送过申请（无论是否通过）
        exists = Friend.objects.filter(user=current_user, friend_id=value).exists()
        if exists:
            raise serializers.ValidationError({
                "code": 400,
                "message": "已向该用户发送过好友申请，请勿重复发送",
                "data": {"friend_id": value}
            })
        # 检查被申请人是否存在
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError({
                "code": 400,
                "message": "被申请人不存在",
                "data": {"friend_id": value}
            })
        return value
class FriendRequestSerializer(serializers.ModelSerializer):
    """好友申请列表：展示申请人信息+申请时间"""
    applicant_info = serializers.SerializerMethodField(label="申请人信息")

    class Meta:
        model = Friend
        fields = ["id", "applicant_info", "created_at", "is_approved"]
        read_only_fields = fields  # 所有字段仅可读

    def get_applicant_info(self, obj):
        """返回申请人的基础信息（ID、用户名、头像）"""
        applicant = obj.user
        return {
            "id": applicant.id,
            "username": applicant.username,
            "avatar": f"http://127.0.0.1:8000{applicant.avatar.url}" if applicant.avatar else "http://127.0.0.1:8000/media/avatars/default.png"
        }

class HandleFriendRequestSerializer(serializers.Serializer):
    """处理好友申请：需申请ID+处理结果（同意/拒绝）"""
    request_id = serializers.IntegerField(label="申请ID")
    agree = serializers.BooleanField(label="是否同意（True=同意，False=拒绝）")

    def validate_request_id(self, value):
        """验证：申请是否存在，且是发给当前用户的未处理申请"""
        current_user = self.context["request"].user
        try:
            friend_request = Friend.objects.get(id=value, friend=current_user, is_approved=False)
        except Friend.DoesNotExist:
            raise serializers.ValidationError("申请不存在或已处理")
        return value

class FriendSerializer(serializers.ModelSerializer):
    """好友列表序列化器（双向好友）"""
    friend_info = serializers.SerializerMethodField(label="好友信息")
    last_message = serializers.SerializerMethodField(label="最后一条消息")
    last_message_time = serializers.SerializerMethodField(label="最后消息时间")
    unread_count = serializers.SerializerMethodField(label="未读消息数")

    class Meta:
        model = Friend
        fields = ["friend_info", "last_message", "last_message_time", "unread_count"]

    import pytz

    def get_friend_info(self, obj):
        """返回好友信息（区分当前用户是申请人还是被申请人）- 适配北京时间"""
        current_user = self.context["request"].user
        friend = obj.friend if obj.user == current_user else obj.user

        # 1. 处理最后活跃时间：转换为北京时间（东8区）
        last_active_str = "未知"
        if hasattr(friend, 'last_active') and friend.last_active:
            # 定义东8区时区
            tz_beijing = pytz.timezone('Asia/Shanghai')
            # 步骤1：如果last_active不带时区，先标记为UTC时区（Django默认存储UTC）
            if friend.last_active.tzinfo is None:
                last_active_utc = pytz.UTC.localize(friend.last_active)
            else:
                last_active_utc = friend.last_active
            # 步骤2：UTC时间转换为北京时间
            last_active_beijing = last_active_utc.astimezone(tz_beijing)
            # 步骤3：格式化为指定字符串
            last_active_str = last_active_beijing.strftime("%Y-%m-%d %H:%M:%S")

        # 2. 在线状态判定（3分钟内活跃=在线，用last_active更精准）
        is_online = False
        if hasattr(friend, 'last_active') and friend.last_active:
            time_diff = timezone.now() - friend.last_active
            if time_diff.total_seconds() < 180:  # 3分钟内
                is_online = True
        # 降级：如果没有last_active，用last_login_time判定
        elif hasattr(friend, 'last_login_time') and friend.last_login_time:
            time_diff = timezone.now() - friend.last_login_time
            if time_diff.total_seconds() < 180:
                is_online = True

        return {
            "id": friend.id,
            "username": friend.username,
            "avatar": f"http://127.0.0.1:8000{friend.avatar.url}" if friend.avatar else "http://127.0.0.1:8000/media/avatars/default.png",
            "is_online": is_online,
            "last_active": last_active_str  # 返回北京时间
        }
    def get_last_message(self, obj):
        current_user = self.context["request"].user
        friend = obj.friend if obj.user == current_user else obj.user
        last_msg = ChatMessage.objects.filter(
            (models.Q(sender=current_user, receiver=friend) |
             models.Q(sender=friend, receiver=current_user))
        ).order_by("-send_time").first()
        return last_msg.content if last_msg else ""

    def get_last_message_time(self, obj):
        current_user = self.context["request"].user
        friend = obj.friend if obj.user == current_user else obj.user
        last_msg = ChatMessage.objects.filter(
            (models.Q(sender=current_user, receiver=friend) |
             models.Q(sender=friend, receiver=current_user))
        ).order_by("-send_time").first()
        return last_msg.send_time.strftime("%Y-%m-%d %H:%M:%S") if last_msg else ""

    def get_unread_count(self, obj):
        current_user = self.context["request"].user
        friend = obj.friend if obj.user == current_user else obj.user
        return ChatMessage.objects.filter(
            sender=friend, receiver=current_user, is_read=False
        ).count()