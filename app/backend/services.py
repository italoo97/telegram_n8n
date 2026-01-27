from django.utils.timezone import now
from django.db.models import Sum
from django.db.models.functions import TruncDay
from payments.models import Image
from payments.models import Payment, Subscription


def total_recebido_mes():
    today = now()

    return (
        Payment.objects
        .filter(
            status="approved",
            created_at__year=today.year,
            created_at__month=today.month
        )
        .aggregate(total=Sum("amount"))
        .get("total") or 0
    )


def clientes_ativos():
    return (
        Subscription.objects
        .filter(status="True")
        .values("user")
        .distinct()
        .count()
    )


def grafico_valores_por_dia():
    return (
        Payment.objects
        .filter(status="approved")
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )

def listar_imagens():
    return Image.objects.select_related("product").all()


def atualizar_status_imagem(image_id, send):
    Image.objects.filter(id=image_id).update(send=send)
