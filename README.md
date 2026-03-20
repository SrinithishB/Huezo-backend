# Huezo Backend

Django REST API for the Huezo B2B fashion manufacturing platform — White Label, Private Label, and Fabrics ordering with Razorpay payment integration.

---

## Project Structure

```
backend/
└── huezo_backend/             # Django project
    ├── accounts/              # Users, roles, customer profiles, auth
    ├── catalogue/             # WL prototypes + fabrics catalogue
    ├── enquiries/             # Public enquiry submissions
    ├── orders/                # Order placement, stages, history
    ├── payments/              # Razorpay integration
    ├── dashboard/             # Admin stats + Excel exports
    └── huezo_backend/         # Django settings, urls, wsgi
```

---

## Setup

```bash
# Clone
git clone https://github.com/SrinithishB/huezo_backend.git
cd huezo_backend/backend

# Virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r huezo_backend/requirements.txt

# Create .env file (see Environment Variables section)

# Run migrations
cd huezo_backend
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Start server
python manage.py runserver
```

---

## Environment Variables

Create a `.env` file inside `huezo_backend/` (same folder as `manage.py`):

```env
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your_razorpay_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

---

## Dependencies

```
Django==6.0.3
djangorestframework==3.16.1
djangorestframework-simplejwt==5.5.1
django-filter==25.2
django-cors-headers==4.9.0
django-environ
bcrypt==5.0.0
Pillow==12.1.1
razorpay
psycopg2-binary==2.9.11
openpyxl
```

---

## Apps & Responsibilities

| App | Description |
|---|---|
| `accounts` | Custom User model (UUID PK, email login), 3 roles: admin / staff / customer. Customer brand profile. Brute-force lockout (5 attempts → 30 min lock). JWT auth. |
| `catalogue` | WL Prototypes (garment designs with sizes, images, pre-booking). Fabrics Catalogue (regular / new / stock types with MOQ logic). |
| `enquiries` | Public enquiry form — no login required. Status tracking (new → accepted / rejected). Assignable to staff. Linkable to WL prototype or fabric. |
| `orders` | 3 order types: White Label, Private Label, Fabrics. Each has its own status pipeline. Auto-generates order numbers. Stage history timeline. |
| `payments` | Razorpay payment transactions. Generic FK — works for orders and any future payment type. Webhook handler for captured / failed / refunded events. |
| `dashboard` | Admin stats, Excel exports for orders and enquiries. |

---

## User Roles

| Role | Django Admin | API Access |
|---|---|---|
| `admin` | ✅ Full access | All endpoints |
| `staff` | ❌ | All read + update endpoints |
| `customer` | ❌ | Own orders, own profile, catalogue |

---

## API Reference

Base URL: `http://127.0.0.1:8000/api`

All protected routes require: `Authorization: Bearer <access_token>`

---

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register/` | ❌ | Register new customer + profile |
| POST | `/auth/login/` | ❌ | Login, returns JWT tokens |
| POST | `/auth/logout/` | ✅ | Blacklist refresh token |
| POST | `/auth/token/refresh/` | ❌ | Get new access token |
| POST | `/auth/change-password/` | ✅ | Change own password |
| GET | `/auth/me/` | ✅ | View own account |
| PATCH | `/auth/me/` | ✅ | Update own email |

---

### Customer Profile

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/customers/me/` | ✅ | View own brand profile |
| PATCH | `/customers/me/` | ✅ | Update own brand profile |

---

### WL Catalogue

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/catalogue/wl/` | ✅ | List prototypes |
| GET | `/catalogue/wl/<uuid>/` | ✅ | Prototype detail + images |

**Filters:**
```
?for_gender=women | men | kids
?garment_type=kurti
?is_prebooking=true
?search=WL-2025
?ordering=-created_at
?page=2
```

---

### Fabrics Catalogue

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/catalogue/fabrics/` | ✅ | List fabrics |
| GET | `/catalogue/fabrics/<uuid>/` | ✅ | Fabric detail + images |

**Filters:**
```
?fabric_type=regular | new | stock
?search=cotton
?ordering=-created_at
?page=2
```

**MOQ by type:**
| Type | MOQ |
|---|---|
| `regular` | 400m |
| `new` | 1000m |
| `stock` | No MOQ |

---

### Enquiries

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/enquiries/` | ❌ | Submit enquiry (multipart/form-data) |
| GET | `/enquiries/admin/` | ✅ Admin/Staff | List all enquiries |
| GET | `/enquiries/admin/unread-count/` | ✅ Admin/Staff | Unread counts by type |
| GET | `/enquiries/admin/<uuid>/` | ✅ Admin/Staff | Enquiry detail (auto-marks viewed) |
| PATCH | `/enquiries/admin/<uuid>/` | ✅ Admin/Staff | Update status / assignee / notes |

**Enquiry types:** `white_label` | `private_label` | `fabrics` | `others`

**Enquiry statuses:** `new` → `contacted` → `waiting_response` → `prospect` → `accepted` / `rejected` / `closed`

**Filters for** `GET /enquiries/admin/`:
```
?order_type=white_label | private_label | fabrics | others
?status=new | contacted | waiting_response | prospect | accepted | rejected | closed
?is_viewed=true | false
?source_page=general | white_label_page | private_label_page | fabrics_page
?assigned_to_user=<uuid>
?date_from=2026-01-01
?date_to=2026-03-15
?search=<name, email, phone, brand, enquiry number>
?ordering=-created_at
```

---

### Orders

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/orders/wl/` | ✅ Customer | Place White Label order |
| POST | `/orders/pl/` | ✅ Customer | Place Private Label order |
| POST | `/orders/fabrics/` | ✅ Customer | Place Fabrics order |
| GET | `/orders/` | ✅ | List orders (admin = all, customer = own) |
| GET | `/orders/<uuid>/` | ✅ | Order detail + timeline + payment info |
| PATCH | `/orders/<uuid>/status/` | ✅ Admin/Staff | Update order stage |
| GET | `/orders/<uuid>/notes/` | ✅ | List notes on an order |
| POST | `/orders/<uuid>/notes/` | ✅ | Add a note to an order |

**Filters for** `GET /orders/`:
```
?order_type=white_label | private_label | fabrics
?status=order_placed | cutting | production | packing | payment_pending | payment_done | dispatch | delivered
?date_from=2026-01-01
?date_to=2026-03-15
?search=<order number, email>
?ordering=-created_at
```

**Order number format:**
| Type | Format | Example |
|---|---|---|
| White Label | `WL-YYYY-NNNNN` | `WL-2026-00001` |
| Private Label | `PL-YYYY-NNNNN` | `PL-2026-00001` |
| Fabrics | `FB-YYYY-NNNNN` | `FB-2026-00001` |

**Order stages by type:**

White Label:
```
order_placed → cutting → production → packing → payment_pending → payment_done → dispatch → delivered
```

Private Label:
```
order_placed → sampling_fabric → sampling_style → sampling_fit →
sample_approval → sample_rework | sample_approved →
fabric_procurement → cutting → production →
packing → payment_pending → payment_done → dispatch → delivered
```

Fabrics:
```
order_placed → production → procurement → cutting → packing → payment_pending → payment_done → dispatch → delivered
```

---

### Payments

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/payments/orders/<uuid>/create/` | ✅ Admin/Staff | Create Razorpay order for payment |
| GET | `/payments/orders/<uuid>/status/` | ✅ | Check payment status |
| GET | `/payments/transactions/` | ✅ Admin/Staff | List all transactions |
| POST | `/payments/webhook/` | ❌ | Razorpay webhook receiver |

**Webhook events handled:**
```
payment.captured  → transaction = paid, order status → payment_done
payment.failed    → transaction = failed
order.paid        → acknowledged
refund.created    → transaction = refunded
refund.processed  → stage history note added
```

**Admin panel payment flow:**
```
1. Open order in Django admin
2. Set Payment Amount  (e.g. 5000.00)
3. Change Status → payment_pending  →  Save
4. Razorpay order auto-created, transaction record saved
5. Customer sees "Pay Now" button on order-detail.html
6. Customer completes payment via Razorpay checkout
7. Webhook fires → order status auto-updated to payment_done
```

---

## Key Request / Response Examples

**Login** `POST /auth/login/`
```json
// Request
{ "email": "customer@example.com", "password": "password123" }

// Response
{ "message": "Login successful.", "user": { "id", "email", "role" }, "access", "refresh" }
```

**Submit Enquiry** `POST /enquiries/`
```
Content-Type: multipart/form-data

order_type, full_name, phone, email, brand_name, message  (required)
source_page, company_age_years, total_pieces_required, annual_revenue  (optional)
wl_prototype, fabric  (optional — UUID, set when coming from catalogue page)
images  (optional — multiple files)
```

**Place WL Order** `POST /orders/wl/`
```json
{
  "white_label_catalogue": "<prototype-uuid>",
  "size_breakdown": "[{\"size\":\"S\",\"quantity\":24},{\"size\":\"M\",\"quantity\":36}]",
  "customization_notes": "Add brand label on collar"
}
```

**Place PL Order** `POST /orders/pl/`
```json
{
  "style_name": "Summer Kurti 001",
  "for_category": "women",
  "garment_type": "kurti",
  "size_breakdown": "[{\"size\":\"M\",\"quantity\":60}]",
  "pl_fabric_1": "<fabric-uuid>",
  "notes": "Refer to attached design sketch"
}
```

**Place Fabrics Order** `POST /orders/fabrics/`
```json
{
  "fabric_catalogue": "<fabric-uuid>",
  "total_quantity": 500,
  "message": "Need in red and blue colourways, deliver by March"
}
```

**Get Order Detail** `GET /orders/<uuid>/`
```json
// Response includes:
{
  "id", "order_number", "order_type", "status",
  "customer", "wl_prototype", "fabric",
  "pl_fabrics": [{"choice", "id", "fabric_name", "fabric_type", "composition"}],
  "size_breakdown", "total_quantity", "moq",
  "valid_stages", "stage_history",
  "payment_amount",
  "payment": {
    "transaction_id", "razorpay_order_id",
    "amount", "currency", "status",
    "payment_reference", "paid_at", "key_id"
  }
}
```

**Update Order Status** `PATCH /orders/<uuid>/status/`
```json
// Request (Admin/Staff only)
{ "status": "cutting", "notes": "Started cutting today" }
```

**Add Order Note** `POST /orders/<uuid>/notes/`
```json
// Request
{ "note": "Customer requested early dispatch" }
```

---

### Dashboard / Exports

| Method | Endpoint | Auth | Description |
|---|---|---|
| GET | `/dashboard/summary/` | ✅ Admin/Staff | Counts for orders and enquiries |
| GET | `/dashboard/export/orders/` | ✅ Admin/Staff | Download orders as Excel (3 sheets) |
| GET | `/dashboard/export/enquiries/` | ✅ Admin/Staff | Download enquiries as Excel (2 sheets) |

**Filters for exports:**
```
?order_type=white_label | private_label | fabrics
?status=<status>
?date_from=2026-01-01
?date_to=2026-03-31
```

---

## Admin Panel

Access at: `http://127.0.0.1:8000/admin/`

Key features:
- **Orders** — view all orders, update status, set payment amount (auto-creates Razorpay payment), export to Excel, bulk status actions
- **Enquiries** — view submissions, assign to staff, update status
- **Catalogue** — manage WL prototypes and fabrics with image uploads
- **Payments** — view all transactions with Razorpay order IDs
- **Users / Customers** — manage accounts and brand profiles

---

## Recent Changes

- `orders/serializers.py` — `pl_fabrics` field added to `OrderDetailSerializer` so Private Label fabric selections are returned in the order detail response
- `payments/views.py` — `PaymentStatusView` now returns `payment_status`, `payment_amount`, and `key_id` explicitly for consistent frontend consumption
- `frontend/order-detail.html` — Razorpay checkout.js integrated; "Pay Now" button opens the real Razorpay checkout modal instead of an alert
- `dashboard` app — Excel export endpoints for orders (3 sheets: All Orders, Summary by Type, Stage History) and enquiries (2 sheets: All Enquiries, Summary by Type)
- `orders` app — `OrderNote` model + `GET/POST /orders/<uuid>/notes/` endpoints added
