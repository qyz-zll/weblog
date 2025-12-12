# # user/views.py
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ErrorDetail
from django.db.models import Q
from django.shortcuts import get_object_or_404 # 你的自定义User模型
from .serializers import UserPublicSerializer  # 对应的序列化器
from .serializers import LoginSerializer, RegisterSerializer,  \
    ChatMessageSerializer, SendMessageSerializer, MarkAsReadSerializer
# # 导入统一响应函数
from utils.response import success_response, error_response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import UserInfoSerializer, UserInfoUpdateSerializer  # 导入修改后的序列化器
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, serializers
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import AvatarUploadSerializer
from .serializers import  FriendSerializer, HandleFriendRequestSerializer, \
    FriendRequestSerializer, SendFriendRequestSerializer  # 你的自定义用户模型
import logging
from .models import User
from django.db import models
# 配置日志（方便调试）
logger = logging.getLogger(__name__)
class LoginView(APIView):
    permission_classes = []  # 允许匿名访问

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = User.objects.get(username=serializer.validated_data['user']['username'])
            user.is_online = True  # 登录时标记为在线
            user.save(update_fields=["is_online"])
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
    """获取我的好友列表（已通过的双向好友）"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FriendSerializer

    def get_queryset(self):
        current_user = self.request.user
        # 双向查询：我加别人且通过 / 别人加我且通过（原逻辑不变）
        return Friend.objects.filter(
            models.Q(user=current_user, is_approved=True) |
            models.Q(friend=current_user, is_approved=True)
        ).order_by("-created_at")

    # 重写 list 方法：自定义返回格式（带 code 状态码）
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()  # 获取查询集（好友数据）
        serializer = self.get_serializer(queryset, many=True)  # 序列化数据

        # 构造统一响应格式：code=200（成功）+ message + data（好友列表数组）
        response_data = {
            "code": status.HTTP_200_OK,  # 200 表示成功（与 HTTP 状态码一致）
            "message": "好友列表获取成功" if queryset.exists() else "暂无好友",
            "data": serializer.data  # 好友数据数组（空数组/有数据数组）
        }

        # 返回自定义响应（HTTP 状态码仍为 200 OK）
        return Response(response_data, status=status.HTTP_200_OK)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ChatMessage, Friend, User  # 导入自定义模型
from django.utils import timezone

class ChatMessageView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    serializer_class = FriendSerializer

    # 需登录验证

    def get(self, request):
        # 1. 提取并验证 friend_id 参数
        friend_id = request.query_params.get('friend_id')
        if not friend_id:
            return Response({'error': 'friend_id 为必填参数'}, status=400)
        try:
            friend_id = int(friend_id)
        except ValueError:
            return Response({'error': 'friend_id 必须为整数'}, status=400)

        # 2. 验证「双向好友关系且已通过」
        try:
            # 条件：当前用户是申请人且好友是被申请人，或当前用户是被申请人且好友是申请人，且状态为已通过
            friend_relation = Friend.objects.get(
                (Q(user=request.user, friend_id=friend_id) | Q(friend=request.user, user_id=friend_id)),
                is_approved=True
            )
        except Friend.DoesNotExist:
            return Response({'error': '好友关系不存在或未通过'}, status=403)

        # 3. 查询历史消息（双向：当前用户→好友 / 好友→当前用户）
        messages = ChatMessage.objects.filter(
            (Q(sender=request.user, receiver_id=friend_id) |  # 当前用户发好友
             Q(sender_id=friend_id, receiver=request.user))   # 好友发当前用户
        ).order_by('send_time')  # 按时间升序

        # 4. 序列化消息
        message_list = []
        for msg in messages:
            message_list.append(
                {
                'id': msg.id,
                'sender_id': msg.sender.id,
                'sender_name': msg.sender.username,
                'receiver_id': msg.receiver.id,
                'content': msg.content,
                'send_time': msg.send_time.strftime('%Y-%m-%d %H:%M:%S'),
                'is_read': msg.is_read
            })

        return Response({
            "code": 200,  # 成功标识
            "message": "获取历史消息成功",
            "data": message_list  # 消息列表数据
        })

class SendMessageView(generics.CreateAPIView):
    """发送消息接口"""
    permission_classes = [IsAuthenticated]
    serializer_class = SendMessageSerializer
    authentication_classes = [JWTAuthentication]
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

from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated



# ---------------------- 好友申请相关视图 ----------------------
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from .models import Friend
from .serializers import SendFriendRequestSerializer



class SendFriendRequestView(generics.CreateAPIView):
    """发送好友申请（POST）：返回统一格式 + 200状态码"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = SendFriendRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        # 手动验证，不抛默认异常
        if not serializer.is_valid():
            # 验证失败：返回和博客列表一致的格式（code=400）
            error_data = serializer.errors
            return Response({
                "code": 400,
                "message": error_data.get("non_field_errors") or error_data["friend_id"]["message"],
                "data": {"friend_id": request.data.get("friend_id")}
            }, status=status.HTTP_200_OK)

        # 验证通过：创建好友申请
        friend_id = serializer.validated_data["friend_id"]
        friend = User.objects.get(id=friend_id)
        Friend.objects.create(
            user=request.user,
            friend=friend,
            is_approved=False
        )

        # 成功：返回统一格式（code=200）
        return Response(
            {
                "code": 200,
                "message": "好友申请发送成功，等待对方审核",
                "data": {"friend_id": friend_id}  # 携带被申请人ID
            },
            status=status.HTTP_200_OK
        )
class MyFriendRequestsView(generics.ListAPIView):
    """获取我收到的好友申请（GET）"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer

    def get_queryset(self):
        # 查询当前用户作为被申请人，且未通过的申请（按申请时间倒序）
        return Friend.objects.filter(
            friend=self.request.user,
            is_approved=False
        ).order_by("-created_at")

    def list(self, request, *args, **kwargs):
        """重写list方法，添加code编码"""
        try:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(
                {
                    "code": 200,  # 成功编码
                    "message": "获取好友申请列表成功",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            # 服务器内部错误
            return Response(
                {
                    "code": 500,
                    "message": f"获取好友申请列表失败：{str(e)}",
                    "data": []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HandleFriendRequestView(generics.CreateAPIView):
    """处理好友申请（同意/拒绝）（POST）"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = HandleFriendRequestSerializer

    def create(self, request, *args, **kwargs):
        """重写create方法，添加code编码"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)  # 验证失败会抛400异常

            request_id = serializer.validated_data["request_id"]
            agree = serializer.validated_data["agree"]

            # 查找申请记录（不存在则抛404）
            try:
                friend_request = Friend.objects.get(id=request_id, friend=request.user)
            except Friend.DoesNotExist:
                return Response(
                    {
                        "code": 404,
                        "message": "好友申请不存在或不属于当前用户"
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            if agree:
                # 同意：更新为已通过
                friend_request.is_approved = True
                friend_request.save()
                return Response(
                    {
                        "code": 200,
                        "message": "已同意好友申请，现在可以聊天啦！"
                    },
                    status=status.HTTP_200_OK
                )
            else:
                # 拒绝：删除申请记录
                friend_request.delete()
                return Response(
                    {
                        "code": 200,
                        "message": "已拒绝好友申请"
                    },
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            # 服务器内部错误
            return Response(
                {
                    "code": 500,
                    "message": f"处理好友申请失败：{str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CancelFriendRequestView(generics.DestroyAPIView):
    """取消我发送的好友申请（DELETE）"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # 获取当前用户发送的、未通过的申请
        try:
            return Friend.objects.get(
                user=self.request.user,
                friend_id=self.kwargs.get("friend_id"),
                is_approved=False
            )
        except Friend.DoesNotExist:
            raise serializers.ValidationError("申请不存在或已处理")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"message": "好友申请已取消"}, status=status.HTTP_204_NO_CONTENT)


class DeleteFriendView(generics.DestroyAPIView):
    """删除好友（双向删除，DELETE）"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # 查询当前用户与目标用户的已通过好友关系（双向匹配）
        friend_id = self.kwargs.get("friend_id")
        try:
            return Friend.objects.get(
                models.Q(user=self.request.user, friend_id=friend_id, is_approved=True) |
                models.Q(friend=self.request.user, user_id=friend_id, is_approved=True)
            )
        except Friend.DoesNotExist:
            raise serializers.ValidationError("好友关系不存在")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"message": "已成功删除好友"}, status=status.HTTP_204_NO_CONTENT)

class UserPublicDetailView(generics.RetrieveAPIView):
    """
    按ID查询用户公开信息（仅返回id、username、avatar）
    - 路径参数：id（好友ID）
    - 认证：需登录（JWT）
    - 统一返回格式：code+message+data
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = UserPublicSerializer
    lookup_field = 'id'

    def get_queryset(self):
        # 仅查询公开信息，无需额外过滤（序列化器已限制字段）
        return User.objects.all()

    def retrieve(self, request, *args, **kwargs):
        """重写retrieve方法，定制标准化响应"""
        try:
            # 获取路径参数中的好友ID，查询用户（不存在则抛404）
            user = get_object_or_404(User, id=kwargs[self.lookup_field])
            # 序列化数据（仅返回id、username、avatar）
            serializer = self.get_serializer(user)
            # 返回成功响应（code=200）
            return Response({
                "code": 200,
                "message": "查询用户公开信息成功",
                "data": serializer.data  # 公开信息：id、username、avatar
            }, status=status.HTTP_200_OK)
        except Exception as e:
            # 异常兜底（如用户不存在、数据库错误等）
            return Response({
                "code": 404,
                "message": f"查询失败：{str(e)}",
                "data": None
            }, status=status.HTTP_404_NOT_FOUND)

# views.py（心跳视图）
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

# chat/views.py

class HeartbeatView(APIView):
    """处理心跳请求，更新用户在线状态和最后活跃时间"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            user.is_online = True  # 标记为在线
            user.save(update_fields=["is_online", "last_active"])  # auto_now=True自动更新last_active
            return Response({"code": 200, "message": "心跳成功"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"code": 500, "message": f"心跳失败：{str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# chat/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import User  # 假设好友申请模型为FriendRequest

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from .models import Friend  # 导入Friend模型（核心！）


class PendingRequestCountView(APIView):
    """查询当前用户的未读好友申请数"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # 核心修正：
            # 1. 用Friend模型查询（而非User模型）
            # 2. friend=request.user 表示「当前用户是被申请人」
            # 3. is_approved=False 表示「未审核的申请」
            pending_count = Friend.objects.filter(
                friend=request.user,  # 当前用户是被申请人（收到申请）
                is_approved=False  # 未通过审核的申请（未处理）
            ).count()

            return Response({"count": pending_count}, status=status.HTTP_200_OK)
        except Exception as e:
            # 更友好的错误提示，便于调试
            return Response(
                {"error": f"查询未处理好友申请数失败：{str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

