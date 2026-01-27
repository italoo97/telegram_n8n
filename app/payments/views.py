from datetime import datetime
import mercadopago
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from .utils.media_signer import unsign_media_token
from django.core.signing import BadSignature, SignatureExpired
from .models import User, Product, Payment, Image
from .services.mercado_pago import *
import json
import requests
import os
import qrcode
import hashlib
import mimetypes
from django.db import transaction

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

def get_or_create_payment(user, product):
    external_reference = f"telegram_{user.telegram_id}_{product.product_type}"

    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(
            external_reference=external_reference,
            status="pending"
        ).order_by("-created_at").first()

        if payment:
            return payment, False

        payment = Payment.objects.create(
            user=user,
            product=product,
            status="pending",
            checkout_url="pending",
            external_reference=external_reference
        )

        return payment, True



@csrf_exempt
def create_subscription(request):
    return _create_payment_checkout(request, "subscription")

@csrf_exempt  
def create_content_checkout(request):
    return _create_payment_checkout(request, "content")

@csrf_exempt  
def create_exclusive_checkout(request):
    return _create_payment_checkout(request, "exclusive")

def _create_payment_checkout(request, product_type):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    
    data = get_json_body(request)
    if not data:
        return JsonResponse({"error": "Invalid or empty JSON"}, status=400)

    required_fields = ["telegram_id", "chat_id"]
    for field in required_fields:
        if field not in data:
            return JsonResponse({"error": f"Missing field: {field}"}, status=400)
    
    telegram_id = data["telegram_id"]
    chat_id = data["chat_id"]
    username = data.get("username", "")
    first_name = data.get("first_name", "")
    
    user, created = User.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
        }
    )

    try:
        product = Product.objects.get(product_type=product_type)
    except Product.DoesNotExist:
        return JsonResponse(
            {"error": f"{product_type.capitalize()} product not found"}, 
            status=500
        )

    payment, created = get_or_create_payment(user, product)
    try:
        if not payment.checkout_url or payment.checkout_url == "pending":
            checkout_url = create_checkout(product, payment)
            payment.checkout_url = checkout_url
            payment.save()

            return JsonResponse({
                "success": True,
                "checkout_url": checkout_url,
                "chat_id": user.chat_id,
                "payment_id": payment.id,
                "product_type": product_type
            })
        
    except Exception as e:
        return JsonResponse({
            "error": f"Erro ao criar checkout: {str(e)}"
        }, status=500)

@csrf_exempt
def mercado_pago_webhook(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        try:
            data = json.loads(request.body.decode("utf-8")) if request.body else {}
        except Exception:
            data = {}

        print("Webhook recebido:", data)

        notification_type = (
            data.get("type")
            or data.get("topic")
            or request.GET.get("type")
            or request.GET.get("topic")
        )

        if notification_type != "payment":
            return JsonResponse({"status": "ignored", "reason": "not a payment event"})

        payment_id = (
            data.get("data", {}).get("id")
            or data.get("id")
            or request.GET.get("data.id")
            or request.GET.get("id")
        )
        if not payment_id:
            return JsonResponse({"status": "ignored", "reason": "missing payment id"})

        sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
        payment_info = sdk.payment().get(payment_id)
        payment_data = payment_info.get("response")
        status_mp = payment_data.get("status")
        external_reference = payment_data.get("external_reference")
        transaction_amount = payment_data.get("transaction_amount")
        net_amount = payment_data.get("net_amount")
        currency = payment_data.get("currency_id", "BRL")

        fee_details = payment_data.get("fee_details", [])
        mp_fee = sum(
            fee.get("amount", 0)
            for fee in fee_details
            if fee.get("type") == "mercadopago_fee"
        )

        metadata = payment_data.get("metadata", {})
        telegram_id_from_meta = metadata.get("user_telegram_id")

        if not payment_data:
            return JsonResponse({"status": "ignored", "reason": "payment not found on MP"})

        print(f"MP Payment {payment_id} | Status: {status_mp} | Ref: {external_reference}")

        payment = None

        if external_reference:
            payment = Payment.objects.filter(
                external_reference=external_reference,
                status="pending"
            ).order_by("-created_at").first()

        if not payment:
            payment = Payment.objects.filter(
                mercado_pago_id=payment_id
            ).first()

        if not payment and telegram_id_from_meta:
            try:
                user = User.objects.get(telegram_id=telegram_id_from_meta)
                payment = Payment.objects.filter(
                    user=user,
                    status="pending"
                ).order_by('-created_at').first()
            except User.DoesNotExist:
                pass
        if not payment:
            print(f"Pagamento não encontrado para external_reference: {external_reference}")
            return JsonResponse({
                "status": "ignored",
                "reason": "payment not registered in system"
            })
        
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment.id)

            if payment.status == status_mp:
                return JsonResponse({
                    "status": "ignored",
                    "reason": "no_state_change"
                })
            
            if payment.processed:
                return JsonResponse({
                    "status": "ignored",
                    "reason": "already_processed"
                })

            payment.status = status_mp
            payment.mercado_pago_id = payment_id
            if transaction_amount:
                payment.amount = transaction_amount
            payment.net_amount = net_amount
            payment.currency = currency
            payment.mercado_pago_fee = mp_fee
            payment.save()

            print(
                f"Pagamento {payment.id} atualizado para {status_mp} "
                f"({payment.product.product_type})"
            )

            if status_mp in ["approved", "authorized"]:
                payload_data = process_approved_payment(payment)

                if not payload_data:
                    return JsonResponse({
                        "status": "ignored",
                        "reason": "already_processed"
                    })

                payload_data.update({
                    "success": "success",
                    "status": status_mp,
                    "payment_id": payment.id,
                    "mercado_pago_id": payment_id
                })

                print(f"Enviando para n8n: {payload_data}")
                response = requests.post(
                    N8N_WEBHOOK_URL,
                    json=payload_data,
                    timeout=10
                )

                print(f"Resposta do n8n: {response.status_code}")

                return JsonResponse({
                    "status": "ok",
                    "action": payload_data.get("action"),
                    "message": "Processado com sucesso"
                })

            if status_mp in ["cancelled", "rejected", "refunded"]:
                payload = {
                    "success": False,
                    "action": "payment_failed",
                    "telegram_id": payment.user.telegram_id,
                    "chat_id": payment.user.chat_id,
                    "status": status_mp,
                    "message": f"Pagamento {status_mp}",
                    "product_type": payment.product.product_type,
                    "payment_id": payment.id
                }

                try:
                    requests.post(
                        N8N_WEBHOOK_URL,
                        json=payload,
                        timeout=10
                    )
                except Exception as e:
                    print(f"Erro ao enviar para n8n: {str(e)}")

                return JsonResponse({"status": "payment_failed"})

        return JsonResponse({"status": "ignored", "reason": "unhandled status"})

    except Exception as e:
        print("Erro no webhook:", str(e))
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def health(request):
    return _create_payment_checkout(request, "subscription")

def get_json_body(request):
    if not request.body:
        return None
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None
    
@csrf_exempt
def create_pix_checkout(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        data = get_json_body(request)
        if not data:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        telegram_id = int(data.get("telegram_id"))
        chat_id = int(data.get("chat_id"))
        product_type = data.get("product_type")

        if not telegram_id or not chat_id or not product_type:
            return JsonResponse(
                {"error": "telegram_id, chat_id and product_type are required"},
                status=400
            )

        user = User.objects.get(telegram_id=telegram_id)
        product = Product.objects.get(product_type=product_type)

        payment, created = get_or_create_payment(user, product)

        pix_data = create_pix_payment(product, payment)

        payment.mercado_pago_id = pix_data["payment_id"]
        payment.save()

        return JsonResponse({
            "success": True,
            "chat_id": chat_id,
            "qr_code": pix_data["qr_code"],
            "qr_code_base64": pix_data["qr_code_base64"],
            "ticket_url": pix_data["ticket_url"],
            "product_type": product_type,
            "payment_id": payment.id
        })

    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    except Product.DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=404)

    except Exception as e:
        print("PIX ERROR:", str(e))
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def generate_qr_code(request):
    qr_data = request.GET.get('data')
    if not qr_data:
        return HttpResponse('Missing data parameter', status=400)
    
    try:
        if len(qr_data) > 100:
            import base64
            qr_data = base64.b64decode(qr_data).decode('utf-8')
    except:
        pass
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    response = HttpResponse(content_type='image/png')
    img.save(response, 'PNG')
    
    response['Cache-Control'] = 'public, max-age=86400'
    response['Content-Disposition'] = 'inline; filename="qrcode.png"'
    
    return response

def serve_private_media(request, token):
    try:
        path = unsign_media_token(token, max_age=300)
    except (BadSignature, SignatureExpired):
        raise Http404("Link inválido ou expirado")

    full_path = os.path.join(settings.MEDIA_ROOT, path)

    if not os.path.exists(full_path):
        raise Http404("Arquivo não encontrado")

    content_type, _ = mimetypes.guess_type(full_path)
    content_type = content_type or "application/octet-stream"

    response = FileResponse(
        open(full_path, "rb"),
        content_type=content_type
    )

    response["Content-Disposition"] = "inline"

    return response
