import os
from celery import Celery
from celery.schedules import crontab

# 设置Django环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weblog.settings')  # 替换为你的项目名

# 初始化Celery
app = Celery('weblog')  # 替换为你的项目名

# 加载Django配置（使用namespace避免冲突）
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现所有app中的tasks.py文件
app.autodiscover_tasks()

# 配置定时任务调度器（可选，也可通过Django admin配置）
app.conf.beat_schedule = {
    'update-user-online-status-every-1-minute': {
        'task': 'user.tasks.update_user_online_status',  # 任务路径（app名.任务文件名.任务函数名）
        'schedule': crontab(minute='*/1'),  # 每1分钟执行一次
    },
}