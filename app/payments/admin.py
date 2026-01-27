from django.contrib import admin
from .models import ExclusiveContentAccess, User, Product, Payment, Image, Subscription

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "chat_id", "username")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "product_type")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "status", "created_at")
    list_filter = ("status", "product")

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ("product",)
    
@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "assigned_at", "expiration_at")
    list_filter = ("status", "assigned_at", "expiration_at")

@admin.register(ExclusiveContentAccess)
class ExclusiveContentAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "granted_at")
    list_filter = ("granted_at",)
