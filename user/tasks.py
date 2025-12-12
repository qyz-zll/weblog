# users/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import User  # 导入User模型

@shared_task
def update_user_online_status():
    """
    定时更新用户在线状态：
    - 超过5分钟未活跃的用户，标记为离线（is_online=False）
    """
    try:
        # 计算超时时间（当前时间往前推5分钟）
        timeout = timezone.now() - timezone.timedelta(minutes=5)
        # 批量更新：将超时未活跃且当前在线的用户标记为离线
        updated_count = User.objects.filter(
            last_active__lt=timeout,  # last_active早于超时时间
            is_online=True            # 当前标记为在线
        ).update(is_online=False)
        print(f"成功更新{updated_count}个用户的在线状态为离线")
        return f"更新完成，共处理{updated_count}个用户"
    except Exception as e:
        print(f"更新用户在线状态失败：{str(e)}")
        raise e  # 抛出异常，便于Celery记录错误日志