from rest_framework import permissions

class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    仅博客作者可修改/删除，其他用户仅可查看公开博客
    """
    def has_object_permission(self, request, view, obj):
        # 读权限允许所有请求（GET/HEAD/OPTIONS）
        if request.method in permissions.SAFE_METHODS:
            # 公开博客可被所有人查看，私有博客仅作者可看
            return obj.is_public or obj.author == request.user
        # 写权限仅作者可操作
        return obj.author == request.user