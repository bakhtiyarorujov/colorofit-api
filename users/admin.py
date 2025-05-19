from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, LifeStyle
# Register your models here.

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_display_links = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email')

@admin.register(LifeStyle)
class LifeStyleAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_display_links = ('name',)
    search_fields = ('name',)