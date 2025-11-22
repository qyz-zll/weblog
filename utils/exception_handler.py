# utils/exception_handler.py（无语法错误，直接复制）
from rest_framework.views import exception_handler
from rest_framework import status
# 导入统一响应函数（确保 response.py 存在且路径正确）
try:
    from weblog.utils.response import error_response
except ImportError:
    # 若 response.py 不存在，先创建一个简单版（避免导入失败）
    from rest_framework.response import Response
    def error_response(message="操作失败", code=400, errors=None):
        return Response({
            'code': code,
            'message': message,
            'errors': errors or {}
        }, status=code)

def custom_exception_handler(exc, context):
    # 调用 DRF 自带的异常处理器
    response = exception_handler(exc, context)

    # 处理认证错误（401）
    if response and response.status_code == status.HTTP_401_UNAUTHORIZED:
        return error_response(
            message="登录已过期，请重新登录",
            code=401,
            errors={"detail": "Token 无效或已过期"}
        )

    # 处理权限错误（403）
    if response and response.status_code == status.HTTP_403_FORBIDDEN:
        return error_response(
            message="权限不足，无法访问",
            code=403,
            errors={"detail": "无操作权限"}
        )

    # 处理限流错误（429）
    if response and response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return error_response(
            message="请求过于频繁，请稍后再试",
            code=429,
            errors={"detail": "超出限流限制"}
        )

    # 其他错误直接返回
    return response