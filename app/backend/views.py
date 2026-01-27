from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from payments.models import Image, Product 
from .services import *
import json, os

@login_required
def dashboard_view(request):
    grafico = grafico_valores_por_dia()

    grafico_formatado = [
        {
            "day": item["day"].strftime("%d/%m"),
            "total": float(item["total"])
        }
        for item in grafico
    ]

    context = {
        "total_mes": total_recebido_mes(),
        "clientes_ativos": clientes_ativos(),
        "grafico": grafico_formatado
    }

    return render(request, "index.html", context)

@login_required
def imagens_view(request):
    if request.method == "POST":
        print("POST data:", request.POST)  # Debug
        
        for key, value in request.POST.items():
            if key.startswith("image_"):
                image_id = key.replace("image_", "")
                print(f"Processando imagem {image_id}: {value}")
                
                # value será "on" se checkbox marcado, ausente se desmarcado
                send_status = value == "on"
                
                # Chama sua função de atualização
                atualizar_status_imagem(
                    image_id=image_id,
                    send=send_status
                )
        
        return redirect("dashboard_images")

    context = {
        "images": listar_imagens()
    }
    return render(request, "images.html", context)

def get_media_type(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext in [".mp4", ".webm", ".mov"]:
        return "video"
    return "image"

def api_images(request):
    if request.headers.get("X-API-KEY") != settings.N8N_API_KEY:
        return JsonResponse({"error": "unauthorized"}, status=401)

    images = Image.objects.filter(send=True)

    data = [
        {
            "id": img.id,
            "image": request.build_absolute_uri(img.image.url),
            "type": get_media_type(img.image),
            "product": img.product.name
        }
        for img in images
    ]

    return JsonResponse(data, safe=False)

@csrf_exempt
def delete_image(request, image_id):
    if request.method == "POST":
        try:
            img = Image.objects.get(id=image_id)
            img.delete()
            return JsonResponse({"success": True})
        except Image.DoesNotExist:
            return JsonResponse({"success": False, "error": "Imagem não encontrada"}, status=404)
    return JsonResponse({"success": False, "error": "Método inválido"}, status=400)

@require_POST
def upload_image(request):
    image_file = request.FILES.get('image')

    if not image_file:
        return JsonResponse({'success': False, 'error': 'Imagem não enviada'}, status=400)

    product = get_object_or_404(Product, name="Conteúdo Premium")

    # Exemplo simples (ajuste conforme seu model)
    image = Image.objects.create(
        product=product,
        image=image_file,
        send=True  # padrão
    )

    return JsonResponse({
        'success': True,
        'image_id': image.id
    })

def save_images_send(request):
    data = json.loads(request.body)
    images_data = data.get('images', [])

    for item in images_data:
        Image.objects.filter(id=item['id']).update(send=item['send'])

    return JsonResponse({'success': True})