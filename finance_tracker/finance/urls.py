from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path("", views.login_view, name="home"),   # 👈 now default route shows login
    path("dashboard/", views.dashboard, name="dashboard"),  # 👈 dashboard moved here
    path("add_expense/", views.add_expense, name="add_expense"),
    path("upload/", views.upload_image, name="upload_image"),
    path("delete-expense/<int:id>/", views.delete_expense, name="delete_expense"),
    path("edit-expense/<int:expense_id>/", views.edit_expense, name="edit_expense"),
    path("get_totals/", views.get_totals, name="get_totals"),
    path("get_chart_data/", views.get_chart_data, name="get_chart_data"),
]
