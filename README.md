# Django + n8n Payment Automation

This project is a **production-ready payment automation system** built with **Django**, **Mercado Pago**, **n8n**, and **Telegram**. It handles checkouts, PIX payments, subscriptions, one-time content sales, and exclusive content delivery in a **safe, idempotent, and scalable** way.

The architecture was designed to survive real-world issues such as:

* Duplicate webhooks
* Network retries
* Race conditions
* Multiple payments over time (subscriptions)

---

## 🧱 Architecture Overview

```
Telegram Bot
   ↓
Django API (Payments & Webhooks)
   ↓
Mercado Pago (Checkout / PIX)
   ↓
Mercado Pago Webhooks
   ↓
Django Webhook Processor
   ↓
n8n (Automation & Messaging)
   ↓
Telegram (Groups / Messages / Media)
```

---

## ✨ Key Features

* ✅ Mercado Pago Checkout (card / balance)
* ✅ Mercado Pago PIX payments
* ✅ Monthly subscriptions with automatic renewal logic
* ✅ One-time content delivery (images/media)
* ✅ Exclusive content access control
* ✅ Safe webhook processing (idempotent)
* ✅ n8n integration for automation and messaging
* ✅ Telegram bot integration
* ✅ Admin Dashboard for product & media management
* ✅ Image upload and controlled media delivery
* ✅ Docker-ready Django backend

---

## 📂 Project Structure (Relevant Parts)

```
Telegram
├── app/
│   ├──.env
│   │
│   ├── Dockerfile
│   │
│   ├── requirements.txt
│   │
│   ├── app/
│   │   └── settings.py
│   │
│   ├── payments/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── services/
│   │   │   └── mercado_pago.py
│   │   └── utils/
│   │       └── media_signer.py
│   │
│   ├── backend/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── templates/
│   │       └── dashboard/
│   │
│   └── manage.py
│
├── n8n/
│
├── n8n_data/
│
├── nginx/
│
├── docker-compose.yml
```

## 🧾 Payment Model Strategy

Each payment is represented by a `Payment` model and follows these rules:

- Only **one pending payment per user + product** is allowed
- Checkout and PIX **reuse the same payment record**
- Payments are identified using a stable `external_reference`

Example:
```

telegram_<telegram_id>_<product_type>

```

This guarantees:
- No duplicate charges
- Safe retries
- Correct webhook matching

---

## 🖥️ Backend Dashboard (Admin App)

The project includes a dedicated **backend Django app** responsible for **internal management and visualization**, separated from the public payment API.

This app provides:

- 📊 Dashboard views for administrators
- 🖼️ Image upload and media management
- 🔐 Control over which images are sent after payment
- 📦 Product-related media association
- 🧪 Safe preview of uploaded content

### Image Management Flow

1. Admin uploads images through the backend dashboard
2. Images are linked to a `Product`
3. Each image has a `send` flag
4. Only images marked with `send=True` are delivered after payment approval

Media delivery is **never public**. Images are accessed through **signed, temporary URLs** generated at payment time.

---

## 🔄 Payment Flow

### 1. Create Checkout or PIX

Endpoints:
- `POST /create-subscription/`
- `POST /create-content-checkout/`
- `POST /create-exclusive-checkout/`
- `POST /create-pix-checkout/`
- `POST /generate-qr/`
- `POST /webhook/`

Flow:
1. User is created or updated by `telegram_id`
2. A pending payment is reused or created
3. Mercado Pago checkout or PIX is generated
4. Checkout URL or PIX QR Code is returned

---

### 2. Mercado Pago Webhook

Endpoint:
```

POST /mercado-pago/webhook/

```

The webhook:
- Validates the event
- Fetches payment details from Mercado Pago
- Locks the payment row (`select_for_update`)
- Prevents duplicate processing
- Updates payment status

---

### 3. Approved Payment Processing

Handled by:
```

process_approved_payment(payment)

````

Supported product types:

#### 🔁 Subscription
- Extends expiration date by 1 month
- Prevents duplicate subscription application
- Triggers n8n action: `add_to_vip_group`

#### 🖼️ Content
- Generates signed temporary media URLs
- Sends media only once
- Triggers n8n action: `send_images`

#### 💎 Exclusive Content
- Grants permanent access
- Prevents duplicate delivery
- Triggers n8n action: `send_pv`

---

## 🔐 Idempotency & Safety

This system is hardened against:
- Duplicate Mercado Pago webhooks
- Multiple approval events
- Concurrent requests

Protection mechanisms:
- Database transactions
- `select_for_update`
- `payment.processed` flag
- `subscription_applied` and `content_sent` flags

---

## 🤖 n8n Integration

After a successful payment, Django sends a JSON payload to n8n:

```json
{
  "action": "send_images",
  "telegram_id": 123456789,
  "chat_id": 987654321,
  "product_type": "content",
  "payment_id": 42
}
````

n8n is responsible for:

* Sending Telegram messages
* Sending media
* Adding users to Telegram groups
* Handling messaging logic

---

## ⚙️ Environment Variables

Required settings:

```env
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

MERCADOPAGO_ACCESS_TOKEN=
MERCADO_PAGO_WEBHOOK=
N8N_WEBHOOK_URL=
MERCADOPAGO_SUCCESS_URL=
MERCADOPAGO_FAILURE_URL=
MERCADOPAGO_PENDING_URL=
DOMAIN_URL=
```

---

## 🚀 Deployment Notes

* Django runs inside Docker
* Webhooks must be publicly accessible
* HTTPS is required by Mercado Pago
* n8n should also run with HTTPS

Recommended flow:

* Develop locally
* Push to GitHub
* Pull on production VPS

---

## 🧠 Design Philosophy

This project was built with:

* Reliability-first mindset
* Real-world payment edge cases in mind
* Clean separation between payment logic and automation
* No duplicate side effects

---

## 📌 Status

✅ Production ready

---

## 📄 License

Private / Proprietary (adjust as needed)
