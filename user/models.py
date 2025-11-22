# models.py（修正后）
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    自定义用户模型（替代 Django 内置 User）
    适配注册、登录、JWT 认证，扩展常用字段
    """
    # 基础字段（继承 AbstractUser 已包含：username、password、email、is_active、is_staff 等）

    # 扩展字段：头像（合并重复定义，保留一个正确配置）
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/%d/',  # 按年月日分文件夹存储，避免文件名冲突
        default='avatars/default.png',  # 默认头像路径（需手动在 media/avatars 下放 default.png）
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

    # 自动记录字段：注册时间（无需前端传递，创建时自动生成）
    create_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("注册时间")
    )

    # 自动更新字段：最后登录时间（每次登录/保存时自动更新）
    last_login_time = models.DateTimeField(
        auto_now=True,
        verbose_name=_("最后登录时间")
    )

    class Meta:
        """模型元数据配置（Admin 后台显示 + 数据库约束）"""
        verbose_name = _("用户")  # Admin 后台单数名称
        verbose_name_plural = _("用户")  # Admin 后台复数名称
        ordering = ["-create_time"]  # 默认排序：按注册时间倒序（新用户在前）
        unique_together = [
            ["username"],  # 用户名唯一（注册时校验重复）
            ["email"]  # 邮箱唯一（注册时校验重复，可根据需求删除）
        ]
        indexes = [
            models.Index(fields=["username"]),  # 用户名索引，提升查询效率
            models.Index(fields=["email"]),  # 邮箱索引，提升查询效率
        ]

    def __str__(self):
        """打印用户对象时显示用户名（方便调试和 Admin 后台查看）"""
        return self.username

    def save(self, *args, **kwargs):
        """重写保存方法：确保密码始终加密存储（双重保障）"""
        # 若密码未经过加密（如手动创建用户、修改密码时），自动加密
        if self.password and not self.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2')):
            self.set_password(self.password)  # Django 内置加密方法，安全可靠
        super().save(*args, **kwargs)

    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.last_name}{self.first_name}"
        return self.username