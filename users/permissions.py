from rest_framework.permissions import BasePermission


class IsNotGuest(BasePermission):
    """Allows authenticated non-guest users only.

    Use on endpoints that create persistent user content (e.g. custom recipes)
    so anonymous guest accounts are prompted to sign in with Google first.
    """

    message = 'Sign in with Google to use this feature.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and not getattr(user, 'is_guest', False))
