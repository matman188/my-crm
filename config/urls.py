"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from crm.views import (
    change_user_password,
    create_customer,
    create_user,
    customers,
    delete_customer,
    delete_user,
    edit_profile,
    edit_customer,
    edit_user,
    home,
    users,
)

urlpatterns = [
    path("", home, name="home"),
    path("customers/", customers, name="customers"),
    path("customers/create/", create_customer, name="create_customer"),
    path("customers/<int:customer_id>/edit/", edit_customer, name="edit_customer"),
    path("customers/<int:customer_id>/delete/", delete_customer, name="delete_customer"),
    path("profile/", edit_profile, name="edit_profile"),
    path("users/", users, name="users"),
    path("users/create/", create_user, name="create_user"),
    path("users/<int:user_id>/edit/", edit_user, name="edit_user"),
    path("users/<int:user_id>/change-password/", change_user_password, name="change_user_password"),
    path("users/<int:user_id>/delete/", delete_user, name="delete_user"),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
