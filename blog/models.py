# blog/models.py
from django.db import models
from django.conf import settings  # 新增：导入 settings
from django.utils import timezone

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

    class Meta:
        verbose_name = "博客"
        verbose_name_plural = "博客"
        ordering = ['-created_at']

    def __str__(self):
        return self.title