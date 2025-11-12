from django.contrib import admin
from .models import Expense

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "item_name", "amount", "type", "category", "date")   # columns in admin list view
    list_filter = ("type", "category", "date")  # filters on right side
    search_fields = ("item_name", "category", "user__username")  # search bar
    ordering = ("-date",)  # newest expenses first
