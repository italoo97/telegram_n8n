from django.urls import path
from .views import *
urlpatterns = [
    path("dashboard/", dashboard_view, name="dashboard"),
    path("photos/", imagens_view, name="dashboard_images"),
    path("images/", api_images),
    path('images/delete/<int:image_id>/', delete_image, name='delete_image'),
    path('images/upload/', upload_image, name='upload_image'),
    path('images/save-send/', save_images_send, name='save_images_send'),
]
