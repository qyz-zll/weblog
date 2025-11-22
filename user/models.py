from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
# ---------------------- 顶部导入补充（关键修正）----------------------
from rest_framework import generics, status, serializers  # 新增 serializers 导入
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework_simplejwt.authentication import JWTAuthentication

from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# 正确导入模型（
# 自定义User模型（替代Django内置User）
class User(AbstractUser):
    """
    自定义用户模型，适配注册、登录、JWT认证，扩展常用字段
    """
    # 扩展字段：头像
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/%d/',
        default='avatars/default.png',
        null=True,
        blank=True,
        verbose_name=_("用户头像"),
        help_text=_("支持 JPG、PNG 格式，建议尺寸 200x200px")
    )

    # 扩展字段：个人简介
    bio = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("个人简介"),
        help_text=_("一句话介绍自己，最多 500 字")
    )

    # 自动记录字段：注册时间
    create_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("注册时间")
    )

    # 自动更新字段：最后登录时间
    last_login_time = models.DateTimeField(
        auto_now=True,
        verbose_name=_("最后登录时间")
    )

    class Meta:
        verbose_name = _("用户")
        verbose_name_plural = _("用户")
        ordering = ["-create_time"]
        unique_together = [["username"], ["email"]]
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')):
            self.set_password(self.password)
        super().save(*args, **kwargs)

    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.last_name}{self.first_name}"
        return self.username


class Friend(models.Model):
    """好友关系模型（支持申请验证）"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_friend_requests"  # 发起申请的用户（申请人）
    )
    friend = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="received_friend_requests"  # 接收申请的用户（被申请人）
    )
    created_at = models.DateTimeField(auto_now_add=True)  # 申请时间
    is_approved = models.BooleanField(default=False)  # 默认为「待审核」，通过后改为True

    class Meta:
        unique_together = ("user", "friend")  # 避免重复申请（同一人不能多次申请同一用户）
        verbose_name = "好友关系"
        verbose_name_plural = "好友关系"

    def __str__(self):
        status = "已通过" if self.is_approved else "待审核"
        return f"{self.user.username} → {self.friend.username}（{status}）"

class ChatMessage(models.Model):
    """聊天消息模型"""
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"  # 关联自定义User
    )
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="received_messages"  # 关联自定义User
    )
    content = models.TextField()
    send_time = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["send_time"]
        verbose_name = "聊天消息"
        verbose_name_plural = "聊天消息"

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username}: {self.content[:20]}"

# ---------------------- 好友申请相关序列化器 ----------------------
class SendFriendRequestSerializer(serializers.Serializer):
    """发送好友申请：仅需被申请人ID"""
    friend_id = serializers.IntegerField(label="被申请人ID")

    def validate_friend_id(self, value):
        """验证：1. 不能添加自己 2. 不能重复申请"""
        current_user = self.context["request"].user
        # 不能添加自己
        if value == current_user.id:
            raise serializers.ValidationError("不能添加自己为好友")
        # 检查是否已发送过申请（无论是否通过）
        exists = Friend.objects.filter(user=current_user, friend_id=value).exists()
        if exists:
            raise serializers.ValidationError("已向该用户发送过好友申请，请勿重复发送")
        # 检查被申请人是否存在
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("被申请人不存在")
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

    def get_friend_info(self, obj):
        """返回好友信息（区分当前用户是申请人还是被申请人）"""
        current_user = self.context["request"].user
        friend = obj.friend if obj.user == current_user else obj.user
        return {
            "id": friend.id,
            "username": friend.username,
            "avatar": f"http://127.0.0.1:8000{friend.avatar.url}" if friend.avatar else "http://127.0.0.1:8000/media/avatars/default.png",
            "is_online": (timezone.now() - friend.last_login_time).total_seconds() < 180,
            "last_active_time": friend.last_login_time.strftime("%Y-%m-%d %H:%M:%S")
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