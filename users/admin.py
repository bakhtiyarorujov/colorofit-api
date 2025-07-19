from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, LifeStyle
from django.utils.translation import gettext_lazy as _

# Register your models here.

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_display_links = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')
    fieldsets = (
    (None, {"fields": ("username", "password")}),
    (_("Personal info"), {"fields": ("first_name", "last_name", "email", "gender", "height", "weight", "aimed_weight", "aimed_date", "age", "life_style", "profile_picture", "bio")}),
    (
        _("Permissions"),
        {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            ),
        },
    ),
    (_("Important dates"), {"fields": ("last_login", "date_joined")}),
)


@admin.register(LifeStyle)
class LifeStyleAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_display_links = ('name',)
    search_fields = ('name',)