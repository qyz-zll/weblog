import json
from django.db.models import Q  # 直接导入Q，避免依赖本地models
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.exceptions import TokenError
# 导入模型（确保路径正确，适配你的项目结构）
from .models import User, ChatMessage, Friend

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """建立 WebSocket 连接：验证用户身份 + 加入聊天房间（带详细日志）"""
        try:
            # 1. 提取并验证好友ID（URL参数是字符串，转成int避免类型错误）
            self.friend_id = self.scope['url_route']['kwargs'].get('friend_id')
            if not self.friend_id:
                print(f"[WebSocket] 错误：未获取到好友ID")
                await self.close(code=1013)  # 1013=不符合政策（参数缺失）
                return
            # 转换为int（前端传递的是数字，URL中是字符串）
            self.friend_id = int(self.friend_id)
            print(f"[WebSocket] 提取好友ID：{self.friend_id}（类型：{type(self.friend_id)}）")

            # 2. 提取并验证Token（前端通过query参数传递：?token=xxx）
            query_string = self.scope['query_string'].decode()  # 格式：token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
            token = query_string.split('=')[-1] if '=' in query_string else ''
            print(f"[WebSocket] 提取Token：{'存在' if token else '不存在'}")
            if not token:
                print(f"[WebSocket] 错误：Token为空")
                await self.close(code=1013)
                return

            # 3. 验证Token并获取当前用户
            try:
                access_token = AccessToken(token)
                self.user_id = access_token['user_id']
                print(f"[WebSocket] Token解析成功，用户ID：{self.user_id}")
                self.user = await database_sync_to_async(User.objects.get)(id=self.user_id)
            except TokenError:  # 捕获所有 Token 相关错误（无效、过期、格式错误）
                print(f"[WebSocket] 错误：Token无效或已过期")
                await self.close(code=1013)
                return
            except User.DoesNotExist:
                print(f"[WebSocket] 错误：用户ID {self.user_id} 不存在")
                await self.close(code=1013)
                return

            # 4. 验证双向好友关系（必须已通过）
            try:
                is_friend = await database_sync_to_async(Friend.objects.filter(
                    # 双向好友条件：A是B的好友 或 B是A的好友，且都已通过
                    (Q(user=self.user, friend_id=self.friend_id, is_approved=True) |
                     Q(friend=self.user, user_id=self.friend_id, is_approved=True))
                ).exists)()
                if not is_friend:
                    print(f"[WebSocket] 错误：用户 {self.user_id} 与 {self.friend_id} 不是双向好友（或未通过）")
                    await self.close(code=1013)
                    return
                print(f"[WebSocket] 好友关系验证通过")
            except Exception as e:
                print(f"[WebSocket] 好友验证异常 - {str(e)}")
                await self.close(code=1013)
                return

            # 5. 创建唯一聊天房间（用户ID升序拼接，确保A-B和B-A是同一个房间）
            self.room_name = f"chat_{min(self.user_id, self.friend_id)}_{max(self.user_id, self.friend_id)}"
            self.room_group_name = f"chat_group_{self.room_name}"
            print(f"[WebSocket] 加入聊天房间：{self.room_group_name}")

            # 6. 加入房间并同意连接
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            print(f"[WebSocket] 连接成功！用户 {self.user_id} 已加入房间 {self.room_group_name}")

        except Exception as e:
            # 捕获所有未预期异常，避免服务崩溃
            print(f"[WebSocket] 连接总异常 - {str(e)}")
            await self.close(code=1006)  # 1006=连接意外关闭

    async def disconnect(self, close_code):
        """断开连接：退出房间（带日志）"""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            print(f"[WebSocket] 断开连接 - 用户 {self.user_id if hasattr(self, 'user_id') else '未知'} 退出房间 {self.room_group_name}，关闭码：{close_code}")
        else:
            print(f"[WebSocket] 断开连接 - 未加入房间，关闭码：{close_code}")

    async def receive(self, text_data):
        """接收前端消息：保存数据库 + 广播给房间内其他用户（带日志）"""
        try:
            text_data_json = json.loads(text_data)
            content = text_data_json.get('content', '').strip()
            print(f"[WebSocket] 收到消息 - 用户 {self.user_id}：{content}")

            # 验证消息内容非空
            if not content:
                print(f"[WebSocket] 忽略空消息 - 用户 {self.user_id}")
                return

            # 1. 异步保存消息到数据库
            chat_message = await database_sync_to_async(ChatMessage.objects.create)(
                sender=self.user,
                receiver_id=self.friend_id,
                content=content,
                is_read=False
            )
            print(f"[WebSocket] 消息保存成功 - 消息ID：{chat_message.id}")

            # 2. 构造前端需要的消息格式（时间格式化、字段完整）
            message_data = {
                'id': chat_message.id,  # 消息ID（前端可用于去重）
                'sender_id': self.user_id,
                'sender_name': self.user.username,
                'receiver_id': self.friend_id,
                'content': content,
                'send_time': chat_message.send_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_read': False
            }

            # 3. 广播消息到房间（所有在线用户都会收到）
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',  # 对应下方 chat_message 方法
                    'message': message_data
                }
            )
            print(f"[WebSocket] 消息广播成功 - 房间 {self.room_group_name}")

        except Exception as e:
            print(f"[WebSocket] 接收消息异常 - {str(e)}")

    async def chat_message(self, event):
        """发送广播消息给当前连接（前端接收）"""
        message = event['message']
        try:
            await self.send(text_data=json.dumps({
                'type': 'new_message',
                'message': message
            }))
            print(f"[WebSocket] 推送消息给用户 {self.user_id}：{message['content']}")
        except Exception as e:
            print(f"[WebSocket] 推送消息异常 - {str(e)}")