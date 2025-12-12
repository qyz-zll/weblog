# blog/models.py
from django.db import models
from django.conf import settings  # 新增：导入 settings
from django.utils import timezone

from user.models import User


class Blog(models.Model):
    """博客模型（修复 User 关联错误）"""
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('published', '已发布'),
    )
    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    cover_image = models.ImageField(upload_to='blog_covers/', null=True, blank=True, verbose_name="封面图")
    # 关键修复：用 settings.AUTH_USER_MODEL 替代 'auth.User'
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # 动态引用用户模型
        on_delete=models.CASCADE,
        related_name='blogs',
        verbose_name="作者"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="状态")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="发布时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    is_public = models.BooleanField(default=True, verbose_name="是否公开")
    like_count = models.IntegerField(default=0, verbose_name="点赞数")
    share_count = models.IntegerField(default=0, verbose_name="转发数")
    comment_count = models.IntegerField(default=0, verbose_name="评论数")

    class Meta:
        verbose_name = "博客"
        verbose_name_plural = "博客"
        ordering = ['-created_at']

    def __str__(self):
        return self.title
class BlogLike(models.Model):
    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name="关联博客"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="liked_blogs",
        verbose_name="点赞用户"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="点赞时间")

    class Meta:
        verbose_name = "博客点赞"
        verbose_name_plural = "博客点赞"
        unique_together = ("blog", "user")  # 唯一约束：一个用户只能给一篇博客点一次赞
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} 点赞 {self.blog.title}"
# ===================== 互动：转发模型 =====================
class BlogShare(models.Model):
    """博客转发记录"""
    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name="shares",
        verbose_name="关联博客"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shared_blogs",
        verbose_name="转发用户"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="转发时间")

    class Meta:
        verbose_name = "博客转发"
        verbose_name_plural = "博客转发"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} 转发 {self.blog.title}"
class BlogComment(models.Model):
    """博客评论模型"""
    blog = models.ForeignKey(
        Blog,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="关联博客"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blog_comments",
        verbose_name="评论作者"
    )
    content = models.TextField(verbose_name="评论内容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="评论时间")

    class Meta:
        verbose_name = "博客评论"
        verbose_name_plural = "博客评论"
        ordering = ["-created_at"]  # 按评论时间倒序

    def __str__(self):
        return f"{self.author.username} 评论 {self.blog.title}: {self.content[:20]}"