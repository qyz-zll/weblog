from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

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
    """好友关系模型（双向好友）"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="friends"  # 关联自定义User
    )
    friend = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="be_friended"  # 关联自定义User
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "friend")
        verbose_name = "好友"
        verbose_name_plural = "好友"

    def __str__(self):
        return f"{self.user.username} ↔ {self.friend.username}"


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