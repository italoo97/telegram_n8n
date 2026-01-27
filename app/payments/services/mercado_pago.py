from app.payments.utils.media_signer import generate_media_token
import mercadopago
from django.conf import settings
from payments.models import Image, Subscription, ExclusiveContentAccess
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import os

sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

def create_checkout(product, payment):
    preference = {
        "items": [
            {
                "title": product.name,
                "quantity": 1,
                "unit_price": float(product.price),
                "currency_id": "BRL",
            }
        ],
        "external_reference": str(payment.id),
        "notification_url": settings.MERCADO_PAGO_WEBHOOK,
    }
    
    if product.product_type == "subscription":
        preference.update({
            "auto_return": "approved",
            "back_urls": {
                "success": settings.MERCADOPAGO_SUCCESS_URL,
                "failure": settings.MERCADOPAGO_FAILURE_URL,
                "pending": settings.MERCADOPAGO_PENDING_URL,
            },
            "statement_descriptor": "Assinatura VIP",
            "metadata": {
                "product_type": "subscription",
                "user_telegram_id": payment.user.telegram_id,
                "payment_id": payment.id
            }
        })
    
    elif product.product_type == "content":
        preference.update({
            "metadata": {
                "product_type": "content",
                "user_telegram_id": payment.user.telegram_id,
                "payment_id": payment.id
            }
        })

    else:
        preference.update({
            "metadata": {
                "product_type": "exclusive",
                "user_telegram_id": payment.user.telegram_id,
                "payment_id": payment.id
            }
        })

    response = sdk.preference().create(preference)
    if response["status"] not in (200, 201):
        raise Exception(f"Erro ao criar checkout: {response}")
    
    mp_response = response.get("response", {})
    if response["status"] not in (200, 201):
        raise Exception(f"Erro ao criar checkout: {response}")
    init_point = mp_response.get("init_point")

    if not init_point:
        raise Exception(f"Erro: {mp_response}")
    return init_point

def create_pix_payment(product, payment):
    payment_data = {
        "transaction_amount": float(product.price),
        "description": product.name,
        "payment_method_id": "pix",
        "payer": {
            "email": f"{payment.user.telegram_id}@no-reply.me"
        },
        "external_reference": payment.external_reference,
        "notification_url": settings.MERCADO_PAGO_WEBHOOK,
        "metadata": {
            "product_type": product.product_type,
            "user_telegram_id": payment.user.telegram_id,
            "payment_id": payment.id
        }
    }

    result = sdk.payment().create(payment_data)

    if result["status"] not in (200, 201):
        raise Exception(f"Erro ao criar PIX: {result}")

    response = result["response"]

    return {
        "qr_code": response["point_of_interaction"]["transaction_data"]["qr_code"],
        "qr_code_base64": response["point_of_interaction"]["transaction_data"]["qr_code_base64"],
        "ticket_url": response["point_of_interaction"]["transaction_data"]["ticket_url"],
        "payment_id": response["id"]
    }

def process_approved_payment(payment):   
    if payment.processed:
        print(f"⚠️ Pagamento {payment.id} já foi processado anteriormente")
        return None
    
    if payment.product.product_type == "subscription":
        if payment.subscription_applied:
            print("⚠️ Assinatura já aplicada")
            return None
        
        subscription, created = Subscription.objects.get_or_create(
            user=payment.user,
            product=payment.product,
            defaults={
                "status": True
            }
        )


        if subscription.expiration_at and subscription.expiration_at > timezone.now():
            subscription.expiration_at += relativedelta(months=1)
        else:
            subscription.expiration_at = timezone.now() + relativedelta(months=1)

        subscription.status = True
        subscription.save()

        payment.subscription_applied = True
        payment.processed = True
        payment.save()
        
        return {
            "action": "add_to_vip_group",
            "message": "✅ Assinatura VIP confirmada! Você será adicionado ao grupo VIP em instantes.",
            "telegram_id": payment.user.telegram_id,
            "chat_id": payment.user.chat_id,
            "product_type": "subscription",
            "product_name": payment.product.name,
            "expiration_at": subscription.expiration_at.isoformat()
        }
    
    elif payment.product.product_type == "content":
        if payment.content_sent:
            print("⚠️ Conteúdo já enviado")
            return None
        
        images = Image.objects.filter(
            product=payment.product,
            send=True
        )

        image_data = []
        for img in images:
            token = generate_media_token(img.file.name)
            url = f"https://www.mybotbr.com/media-temp/{token}/"
            
            image_data.append({
                "id": img.id,
                "url": url,
                "token": token,
                "filename": os.path.basename(img.file.name)
            })

        payment.content_sent = True
        payment.processed = True
        payment.save()
        
        return {
            "action": "send_images",
            "message": f"✅ Conteúdo liberado! Você receberá {len(image_data)} imagem(ns).",
            "telegram_id": payment.user.telegram_id,
            "chat_id": payment.user.chat_id,
            "product_type": "content",
            "product_name": payment.product.name,
            "image_urls": image_data,
            "image_count": len(image_data)
        }
    
    elif payment.product.product_type == "exclusive":
        if payment.processed or payment.content_sent:
            print("⚠️ Conteúdo exclusivo já enviado")
            return None
        
        exclusive, created = ExclusiveContentAccess.objects.get_or_create(
            user=payment.user,
            product=payment.product,
            defaults={
                "granted_at": timezone.now()
            }
        )

        payment.content_sent = True
        payment.processed = True
        payment.save()
        
        return {
            "action": "send_pv",
            "message": f"✅ Vou Adorar fazer um conteudo exclusivamente para voce amor.",
            "telegram_id": payment.user.telegram_id,
            "chat_id": payment.user.chat_id,
            "product_type": "exclusive",
            "product_name": payment.product.name,
        }
    
    else:
        return {
            "action": "unknown",
            "message": "Pagamento aprovado, mas tipo de produto não reconhecido.",
            "telegram_id": payment.user.telegram_id,
            "chat_id": payment.user.chat_id,
            "product_type": "unknown"
        }