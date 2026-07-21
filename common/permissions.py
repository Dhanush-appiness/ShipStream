from rest_framework.permissions import BasePermission

class HasRole(BasePermission):
    allowed_roles=[]
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )

class IsAdmin(HasRole):
    allowed_roles=["ADMIN"]

class IsManagerOrAdmin(HasRole):
    allowed_roles=["ADMIN","MANAGER"]

class IsAnyAuthenticatedRole(HasRole):
    allowed_roles=["ADMIN","MANAGER","MEMBER"]