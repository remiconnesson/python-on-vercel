from django.contrib import admin
from django.urls import path

from mysite import views

urlpatterns = [
    path("", views.index),
    path("api/info", views.api_info),
    path("admin/", admin.site.urls),
]
