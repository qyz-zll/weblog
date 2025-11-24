import os
import importlib  # 导入动态导入模块
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

# 1. 先配置 Django 环境（必须在最前面）
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weblog.settings')

# 2. 定义延迟导入函数（有请求时才导入 Consumer）
def get_chat_consumer():
    # 动态导入 ChatConsumer，此时 Apps 已就绪
    module = importlib.import_module('user.consumers')
    return module.ChatConsumer.as_asgi()

# 3. ASGI 核心路由（用函数延迟导入，而非直接导入）
application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # HTTP 请求正常处理
    "websocket": AuthMiddlewareStack(
        URLRouter([
            # 路由中调用函数，动态获取 Consumer
            path('ws/chat/<int:friend_id>/', get_chat_consumer()),
        ])
    ),
})