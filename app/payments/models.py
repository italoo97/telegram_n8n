from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError

def validate_media_file(value):
    allowed_types = [
            "image/jpeg",
            "image/png",
            "image/webp",
            "video/mp4",
            "video/webm",
            "video/quicktime",
        ]

    if value.file.content_type not in allowed_types:
            raise ValidationError("Formato de arquivo não permitido.")

class User(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField()
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.username} ({self.telegram_id})"

class Product(models.Model):
    PRODUCT_TYPE_CHOICES = (
        ("subscription", "Subscription"),
        ("content", "Content"),
        ("exclusive", "Exclusive"),
    )

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES)

    def __str__(self):
        return self.name

class Payment(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    mercado_pago_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_url = models.URLField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    external_reference = models.CharField(max_length=255, blank=True, null=True)
    processed = models.BooleanField(default=False)
    content_sent = models.BooleanField(default=False)
    subscription_applied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.product} - {self.status}"

class Image(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    image = models.FileField(upload_to="images/",validators=[validate_media_file])
    send = models.BooleanField(default=False)

    def public_url(self):
        from urllib.parse import urljoin
        from django.conf import settings
        return urljoin(settings.DOMAIN_URL, self.image.url)

    def __str__(self):
        return f"Image for {self.product}"
    
class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    expiration_at = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.expiration_at:
            self.expiration_at = timezone.now() + relativedelta(months=1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} assigned to {self.product}"
    
class ExclusiveContentAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} has access to {self.product}"
