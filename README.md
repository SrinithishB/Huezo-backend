# Huezo Backend

Django REST API for the Huezo White Label Catalogue platform.

---

## Setup

```bash
# Clone
git clone https://github.com/SrinithishB/huezo_backend.git

# Virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Enter
cd huezo_backend

# Install
pip install -r requirements.txt

# Migrate & create admin
python manage.py migrate
python manage.py createsuperuser

# Run
python manage.py runserver
```

**requirements.txt**
```
django
djangorestframework
djangorestframework-simplejwt
django-filter
django-cors-headers
bcrypt
psycopg2-binary
Pillow
razorpay
python-decouple
```

---

## Environment Variables

Create a `.env` file in the project root (same folder as `manage.py`):

```
SECRET_KEY=your_django_secret_key
DEBUG=True

RAZORPAY_KEY_ID=rzp_test_xxxx
RAZORPAY_KEY_SECRET=your_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

---

## Apps

| App | Description |
|---|---|
| `accounts` | Users, customer profiles, auth |
| `catalogue` | WL prototypes, fabrics catalogue |
| `enquiries` | Public enquiry forms |
| `orders` | Order placement and tracking |
| `payments` | Razorpay payment integration |

---

## Endpoints

Base URL: `http://127.0.0.1:8000/api`

All protected routes require: `Authorization: Bearer <access_token>`

---

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register/` | ❌ | Register new customer |
| POST | `/auth/login/` | ❌ | Login, returns tokens |
| POST | `/auth/logout/` | ✅ | Invalidate refresh token |
| POST | `/auth/token/refresh/` | ❌ | Get new access token |
| POST | `/auth/change-password/` | ✅ | Change password |
| GET | `/auth/me/` | ✅ | View my account |
| PATCH | `/auth/me/` | ✅ | Update my account |

---

### Customer Profile

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/customers/me/` | ✅ | View my profile |
| PATCH | `/customers/me/` | ✅ | Update my profile |

---

### WL Catalogue

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/catalogue/wl/` | ✅ | List all prototypes |
| GET | `/catalogue/wl/<uuid>/` | ✅ | Get prototype detail |

**Filters for** `GET /catalogue/wl/`
```
?for_gender=women
?garment_type=kurti
?collection_name=diwali
?is_prebooking=true
?moq_min=10&moq_max=50
?search=WL-2025
?ordering=-created_at
?page=2
```

---

### Fabrics Catalogue

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/catalogue/fabrics/` | ✅ | List all fabrics |
| GET | `/catalogue/fabrics/<uuid>/` | ✅ | Get fabric detail |

**Filters for** `GET /catalogue/fabrics/`
```
?fabric_type=regular | new | stock
?fabric_name=cotton
?composition=poly
?price_min=10&price_max=500
?width_min=100&width_max=200
?search=silk
?ordering=-price_per_meter
?page=2
```

**MOQ by fabric type**
| Type | MOQ |
|---|---|
| `regular` | 400m |
| `new` | 1000m |
| `stock` | No MOQ |

---

### Enquiries

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/enquiries/` | ❌ | Submit enquiry (public) |
| GET | `/enquiries/admin/` | ✅ Admin/Staff | List all enquiries |
| GET | `/enquiries/admin/unread-count/` | ✅ Admin/Staff | Unread counts by type |
| GET | `/enquiries/admin/<uuid>/` | ✅ Admin/Staff | Get enquiry detail |
| PATCH | `/enquiries/admin/<uuid>/` | ✅ Admin/Staff | Update status / assignee / notes |

**Filters for** `GET /enquiries/admin/`
```
?order_type=private_label | white_label | fabrics | others
?status=new | contacted | waiting_response | prospect | accepted | rejected | closed
?is_viewed=true | false
?source_page=general | private_label_page | white_label_page | fabrics_page
?assigned_to_user=<uuid>
?date_from=2026-01-01
?date_to=2026-03-15
?search=name, email, phone, brand, enquiry number
?ordering=-created_at
```

---

### Orders

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/orders/wl/` | ✅ Customer | Place White Label order |
| POST | `/orders/pl/` | ✅ Customer | Place Private Label order |
| POST | `/orders/fabrics/` | ✅ Customer | Place Fabrics order |
| GET | `/orders/` | ✅ Admin = all, Customer = own | List orders |
| GET | `/orders/<uuid>/` | ✅ | Get order detail + timeline |
| PATCH | `/orders/<uuid>/status/` | ✅ Admin/Staff | Update order stage |

**Filters for** `GET /orders/`
```
?order_type=private_label | white_label | fabrics
?status=order_placed | cutting | production | packing | payment_pending | payment_done | dispatch | delivered
?date_from=2026-01-01
?date_to=2026-03-15
?search=order number, email
?ordering=-created_at
```

**Order number format**
| Type | Format | Example |
|---|---|---|
| White Label | `WL-YYYY-NNNNN` | `WL-2026-00001` |
| Private Label | `PL-YYYY-NNNNN` | `PL-2026-00001` |
| Fabrics | `FB-YYYY-NNNNN` | `FB-2026-00001` |

**Order stages**

All types (WL, PL, Fabrics):
```
order_placed → ... → packing → payment_pending → payment_done → dispatch → delivered
```

Private Label (additional sampling stages):
```
order_placed → sampling_fabric → sampling_style → sampling_fit →
sample_approval → sample_rework / sample_approved →
fabric_procurement → cutting → production →
packing → payment_pending → payment_done → dispatch → delivered
```

---

### Payments

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/payments/orders/<uuid>/create/` | ✅ Admin/Staff | Create Razorpay payment |
| GET | `/payments/orders/<uuid>/status/` | ✅ Any | Check payment status |
| GET | `/payments/transactions/` | ✅ Admin/Staff | List all transactions |
| POST | `/payments/webhook/` | ❌ | Razorpay webhook (auto-called) |

**Razorpay webhook events handled:**
```
payment.captured  → status = payment_done, transaction = paid
payment.failed    → transaction = failed
order.paid        → acknowledged
refund.created    → transaction = refunded
refund.processed  → stage history note added
```

**Admin panel payment flow:**
```
1. Open order in admin panel
2. Set Payment Amount field  e.g. 5000.00
3. Change Status → payment_pending
4. Save → Razorpay payment auto-created
5. Customer pays via Flutter app
6. Webhook auto-updates → payment_done
```

---

## Key Inputs & Outputs

**Register** `POST /auth/register/`
```json
// Input
{ "email", "password", "confirm_password", "brand_name", "contact_name", "phone" }

// Output
{ "message", "user": { "id", "email", "role" }, "access", "refresh" }
```

**Login** `POST /auth/login/`
```json
// Input
{ "email", "password" }

// Output
{ "message", "user": { "id", "email", "role" }, "access", "refresh" }
```

**Submit Enquiry** `POST /enquiries/`
```json
// Input (multipart/form-data)
{ "order_type", "full_name", "phone", "email", "brand_name", "message",
  "source_page"(opt), "company_age_years"(opt), "total_pieces_required"(opt),
  "annual_revenue"(opt), "wl_prototype"(opt), "fabric"(opt),
  "images"(opt, multiple files) }

// Output
{ "message", "data": { "id", "enquiry_number", "order_type",
  "full_name", "phone", "email", "brand_name", "status",
  "wl_prototype", "fabric", "images", "created_at" } }
```

**Place WL Order** `POST /orders/wl/`
```json
// Input
{ "white_label_catalogue": "uuid",
  "size_breakdown": "[{\"size\":\"S\",\"quantity\":24}]",
  "customization_notes"(opt) }

// Output
{ "message", "data": { full order detail } }
```

**Place PL Order** `POST /orders/pl/`
```json
// Input
{ "style_name", "for_category", "garment_type",
  "size_breakdown": "[{\"size\":\"S\",\"quantity\":60}]",
  "pl_fabric_1"(opt uuid), "pl_fabric_2"(opt uuid), "pl_fabric_3"(opt uuid),
  "notes"(opt) }

// Output
{ "message", "data": { full order detail } }
```

**Place Fabrics Order** `POST /orders/fabrics/`
```json
// Input
{ "fabric_catalogue": "uuid", "total_quantity": 500, "message": "..." }

// Output
{ "message", "data": { full order detail } }
```

**Get Order Detail** `GET /orders/<uuid>/`
```json
// Output
{ "id", "order_number", "order_type",
  "customer", "created_by", "enquiry",
  "wl_prototype", "fabric", "pl_fabrics",
  "style_name", "for_category", "garment_type",
  "fit_sizes", "size_breakdown", "total_quantity", "moq",
  "customization_notes", "message", "fabric_type",
  "status", "valid_stages", "notes",
  "images", "stage_history",
  "created_at", "updated_at" }
```

**Update Order Status** `PATCH /orders/<uuid>/status/`
```json
// Input (Admin/Staff only)
{ "status": "cutting", "notes"(opt): "Started cutting today" }

// Output — full order detail with updated stage_history
```

**Create Payment** `POST /payments/orders/<uuid>/create/`
```json
// Input (Admin/Staff only)
{ "amount": 5000.00, "notes"(opt): "Payment for WL-2026-00001" }

// Output
{ "transaction_id", "razorpay_order_id", "amount_paise",
  "amount_inr", "currency", "key_id" }
```

**Payment Status** `GET /payments/orders/<uuid>/status/`
```json
// Output
{ "order_number", "order_status",
  "payment_type", "amount", "currency",
  "status", "razorpay_order_id",
  "payment_reference", "paid_at" }
```