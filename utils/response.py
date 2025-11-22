# weblog/utils/response.py
from rest_framework.response import Response

def success_response(data=None, message="操作成功"):
    """成功响应：统一格式"""
    return Response({
        'code': 200,
        'message': message,
        'data': data or {}  # data 可选，默认空字典
    })

def error_response(message="操作失败", code=400, errors=None):
    """失败响应：统一格式"""
    return Response({
        'code': code,
        'message': message,
        'errors': errors or {}  # errors 可选，存储具体错误信息（如表单验证错误）
    }, status=code)  # status 保持与 code 一致，符合 HTTP 规范