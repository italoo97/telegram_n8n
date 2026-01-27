from django.urls import path
from .views import *

urlpatterns = [
    path("create-subscription/", create_subscription, name="create_subscription"),
    path("create-content-checkout/", create_content_checkout, name="create_content_checkout"),
    path("create-exclusive-checkout/", create_exclusive_checkout, name="create_exclusive_checkout"),
    path("create-pix-subscription/", create_pix_checkout, name="create_pix_checkout"),
    path('generate-qr/', generate_qr_code, name='generate_qr'),
    path("webhook/", mercado_pago_webhook, name="mercado_pago_webhook"),
    path("health/", health, name="health"),
]
