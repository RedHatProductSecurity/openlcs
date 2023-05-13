from rest_framework.permissions import BasePermission


class ReadOnlyModelPermission(BasePermission):
    """
    Wrapper permission control class, to restrict the API create/update
    access only to admin/superuser.
    """
    def has_permission(self, request, view):
        if request.method == 'GET':
            return True
        else:
            return request.user.is_staff
