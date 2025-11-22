# user/views.py
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ErrorDetail

from . import models
from .serializers import LoginSerializer, RegisterSerializer, UserInfoSerializer, FriendListSerializer, \
    ChatMessageSerializer, SendMessageSerializer, MarkAsReadSerializer
# 导入统一响应函数
from utils.response import success_response, error_response
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import UserInfoSerializer, UserInfoUpdateSerializer  # 导入修改后的序列化器
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import AvatarUploadSerializer
from .models import User, Friend, ChatMessage  # 你的自定义用户模型
import os
from django.conf import settings
import logging
# 配置日志（方便调试）
logger = logging.getLogger(__name__)
class LoginView(APIView):
    permission_classes = []  # 允许匿名访问

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            # 验证通过：返回统一成功格式
            return success_response(
                data=serializer.validated_data,  # 包含 token 和 user 信息
                message="登录成功"
            )
        # 验证失败：返回统一错误格式（errors 为序列化器的错误信息）
        return error_response(
            message="登录失败",
            code=status.HTTP_400_BAD_REQUEST,
            errors=serializer.errors
        )


def get_error_string(error_dict: dict, field: str) -> str:
    """
    从错误字典中提取指定字段的错误提示 string
    :param error_dict: 格式如 {'email': [ErrorDetail(...)]} 的错误字典
    :param field: 要提取错误的字段名（如 'email'）
    :return: 错误提示字符串（无错误则返回空字符串）
    """
    # 1. 安全获取字段对应的错误列表（无则返回空列表）
    field_errors = error_dict.get(field, [])
    # 2. 确保列表非空，且第一个元素是 ErrorDetail 实例
    if isinstance(field_errors, list) and len(field_errors) > 0 and isinstance(field_errors[0], ErrorDetail):
        return field_errors[0].string
    # 兜底：无错误时返回空字符串
    return ""


class RegisterView(APIView):
    permission_classes = []  # 允许匿名访问（注册无需登录）

    def post(self, request):
        # 接收前端提交的注册数据（username、password、password2、email、bio）
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            # 验证通过，创建用户（调用序列化器的 create 方法）
            user = serializer.save()
            # 为新用户生成 JWT 令牌（注册成功后自动登录，无需二次登录）
            refresh = RefreshToken.for_user(user)
            # 返回统一成功响应（包含令牌和用户信息）
            return success_response(
                data={
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'bio': user.bio
                    }
                },
                message="注册成功"
            )
        first_error = next(iter(serializer.errors.values()), ['注册信息验证失败'])[0]
        return error_response(
            message=first_error,  # 用户名重复时返回"用户名已被占用！"，邮箱错误时返回邮箱相关提示
            code=status.HTTP_400_BAD_REQUEST,
            errors=serializer.errors  # 同时返回所有错误，前端可按需处理字段级提示
        )
class UserInfoView(APIView):
    """通过 JWT Token 自动解析用户，返回当前登录用户信息"""
    # 显式指定 JWT 认证类（确保认证生效）
    authentication_classes = [JWTAuthentication]
    # 必须登录才能访问（IsAuthenticated 依赖认证类）
    permission_classes = [IsAuthenticated]
    print(11)
    def get(self, request):
        # 调试打印：辅助排查认证问题（终端输出）
        try:
            # JWT 已自动通过 Token 解析出当前用户，直接从 request.user 获取
            user = request.user
            serializer = UserInfoSerializer(user)  # 序列化用户信息
            return Response({
                "code": 200,
                "message": "获取用户信息成功",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print("获取用户信息失败:", str(e))
            return Response({
                "code": 500,
                "message": f"获取失败：{str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




# 🌟 1. 导入 JWT 认证类（关键：导入类对象，而非用字符串）
from rest_framework_simplejwt.authentication import JWTAuthentication

@method_decorator(csrf_exempt, name='dispatch')
class AvatarUploadView(APIView):
    # 🌟 2. 修正：传类对象，不是字符串（之前的错误根源）
    authentication_classes = [JWTAuthentication]  # 去掉引号，直接用导入的类
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 调试打印
        print("="*50)
        print("请求头中的Authorization：", request.headers.get('Authorization', '无'))
        print("当前登录用户：", request.user)
        print("用户是否认证：", request.user.is_authenticated)
        print("请求体中的文件：", request.FILES.get('avatar', '无'))
        print("="*50)

        if not request.user.is_authenticated:
            return Response({
                'code': 401,
                'message': '身份验证失败，请重新登录',
            }, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        serializer = AvatarUploadSerializer(
            instance=user,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                'code': 200,
                'message': '头像修改成功',
                'data': {
                    'avatar': request.build_absolute_uri(user.avatar.url)
                }
            }, status=status.HTTP_200_OK)

        return Response({
            'code': 400,
            'message': '头像上传失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)




class UpdateUserInfoView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # GET：获取用户详情（直接返回模型字段）
    def get(self, request):
        user = request.user  # 当前登录的 User 实例
        serializer = UserInfoSerializer(user)
        return Response({
            'code': 200,
            'message': '获取用户信息成功',
            'data': serializer.data
        }, status=HTTP_200_OK)

    # PUT：更新用户信息（调用修正后的序列化器）
    def put(self, request):
        user = request.user
        serializer = UserInfoUpdateSerializer(
            instance=user,
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            updated_user = serializer.save()
            return Response({
                'code': 200,
                'message': '用户信息更新成功',
                'data': UserInfoSerializer(updated_user).data  # 返回更新后的完整信息
            }, status=HTTP_200_OK)
        # 序列化器验证失败（如用户名重复、邮箱格式错误）
        return Response({
            'code': 400,
            'message': '更新失败',
            'errors': serializer.errors  # 返回具体错误信息，方便前端显示
        }, status=HTTP_400_BAD_REQUEST)


class FriendListView(generics.ListAPIView):
    """获取好友列表接口"""
    permission_classes = [IsAuthenticated]
    serializer_class = FriendListSerializer

    def get_queryset(self):
        return Friend.objects.filter(
            user=self.request.user, is_approved=True
        )

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            # 传递request到序列化器context（必须！）
            serializer = self.get_serializer(queryset, many=True, context={"request": request})

            # 格式化响应（适配前端）
            friend_list = [item["friend_info"] for item in serializer.data]
            for i, item in enumerate(serializer.data):
                friend_list[i].update({
                    "last_message": item["last_message"],
                    "last_message_time": item["last_message_time"],
                    "unread_count": item["unread_count"]
                })

            logger.info(f"好友列表响应数据：{friend_list}")
            return Response(friend_list, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"好友列表接口异常：{str(e)}", exc_info=True)
            return Response(
                {"detail": f"获取好友列表失败：{str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatMessageView(generics.ListAPIView):
    """获取聊天记录接口"""
    permission_classes = [IsAuthenticated]
    serializer_class = ChatMessageSerializer

    def get_queryset(self):
        friend_id = self.kwargs.get("friend_id")
        current_user = self.request.user
        # 验证好友关系
        is_friend = Friend.objects.filter(
            user=current_user, friend_id=friend_id, is_approved=True
        ).exists()
        if not is_friend:
            return ChatMessage.objects.none()
        # 获取双方聊天记录
        return ChatMessage.objects.filter(
            (models.Q(sender=current_user, receiver_id=friend_id) |
             models.Q(sender_id=friend_id, receiver=current_user))
        ).order_by("send_time")


class SendMessageView(generics.CreateAPIView):
    """发送消息接口"""
    permission_classes = [IsAuthenticated]
    serializer_class = SendMessageSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        friend_id = serializer.validated_data["friend_id"]
        content = serializer.validated_data["content"]
        current_user = request.user

        try:
            friend = Friend.objects.get(
                user=current_user, friend_id=friend_id, is_approved=True
            )
        except Friend.DoesNotExist:
            return Response(
                {"message": "不是好友，无法发送消息"},
                status=status.HTTP_403_FORBIDDEN
            )

        chat_message = ChatMessage.objects.create(
            sender=current_user,
            receiver=friend.friend,
            content=content
        )

        return Response(
            ChatMessageSerializer(chat_message).data,
            status=status.HTTP_201_CREATED
        )


class MarkAsReadView(generics.CreateAPIView):
    """标记消息为已读接口"""
    permission_classes = [IsAuthenticated]
    serializer_class = MarkAsReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        friend_id = serializer.validated_data["friend_id"]
        current_user = request.user

        ChatMessage.objects.filter(
            sender_id=friend_id,
            receiver=current_user,
            is_read=False
        ).update(is_read=True)

        return Response({"message": "标记已读成功"})


class UnreadCountView(generics.RetrieveAPIView):
    """获取未读消息总数接口"""
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        total_unread = ChatMessage.objects.filter(
            receiver=request.user, is_read=False
        ).count()
        return Response({"total_unread": total_unread})