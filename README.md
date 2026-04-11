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
    ├── notifications/         # FCM push notifications + in-app inbox
    ├── banners/               # Home screen banner images (admin CRUD)
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
firebase-admin
```

---

## Apps & Responsibilities

| App | Description |
|---|---|
| `accounts` | Custom User model (UUID PK, email login), 3 roles: admin / staff / customer. Customer brand profile. Brute-force lockout (5 attempts → 30 min lock). JWT auth. |
| `catalogue` | WL Prototypes (garment designs with sizes, images, pre-booking). Fabrics Catalogue (regular / new / stock types with MOQ logic). |
| `enquiries` | Public enquiry form — no login required. Status tracking (new → accepted / rejected). Assignable to staff. Linkable to WL prototype or fabric. |
| `orders` | 3 order types: White Label, Private Label, Fabrics. Each has its own status pipeline. Auto-generates order numbers. Stage history timeline. Staff assignment per order. |
| `payments` | Razorpay payment transactions. Generic FK — works for orders and any future payment type. Webhook handler for captured / failed / refunded events. |
| `dashboard` | Admin stats, Excel exports for orders and enquiries. |
| `notifications` | Firebase Cloud Messaging (FCM) push notifications. In-app notification inbox with read/unread tracking. |
| `banners` | Home screen banner images managed by admin. Sort order + active toggle. |

---

## User Roles

| Role | Django Admin | API Access |
|---|---|---|
| `admin` | ✅ Full access | All endpoints |
| `staff` | ✅ View-only | All read + update endpoints |
| `customer` | ❌ | Own orders, own profile, catalogue, banners |

---

## API Reference

**Base URL:** `http://127.0.0.1:8000/api`

All protected routes require:
```
Authorization: Bearer <access_token>
```

---

## 1. Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register/` | ❌ | Register new customer + profile |
| POST | `/auth/login/` | ❌ | Login, returns JWT tokens |
| POST | `/auth/logout/` | ✅ | Blacklist refresh token |
| POST | `/auth/token/refresh/` | ❌ | Exchange refresh token for new access token |
| POST | `/auth/change-password/` | ✅ | Change own password |
| GET | `/auth/me/` | ✅ | View own account |
| PATCH | `/auth/me/` | ✅ | Update own email |

### Request Bodies

**Register** `POST /auth/register/`
```json
{
  "email": "brand@example.com",
  "password": "strongpassword",
  "confirm_password": "strongpassword",
  "brand_name": "FashionBrand",
  "contact_name": "Jane Doe",
  "phone": "+919876543210",
  "alternate_phone": "+919876543211",
  "address_line1": "123 MG Road",
  "address_line2": "Near Central Mall",
  "city": "Bengaluru",
  "state": "Karnataka",
  "pin_code": "560001",
  "country": "India"
}
```

**Login** `POST /auth/login/`
```json
{ "email": "brand@example.com", "password": "strongpassword" }
```
Response:
```json
{
  "message": "Login successful.",
  "user": { "id": "<uuid>", "email": "brand@example.com", "role": "customer" },
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>"
}
```

**Logout** `POST /auth/logout/`
```json
{ "refresh": "<jwt_refresh_token>" }
```

**Change Password** `POST /auth/change-password/`
```json
{ "old_password": "old", "new_password": "newpass", "confirm_password": "newpass" }
```

---

## 2. Customer Profile

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/customers/me/` | ✅ | View own brand profile |
| PATCH | `/customers/me/` | ✅ | Update own brand profile + profile picture |
| POST | `/customers/me/profile-picture-url/` | ✅ | Upload / replace profile picture |
| DELETE | `/customers/me/profile-picture-url/` | ✅ | Remove profile picture |

**Update Profile** `PATCH /customers/me/`
```
Content-Type: multipart/form-data

brand_name, contact_name, phone, alternate_phone,
address_line1, address_line2, city, state, pin_code, country,
profile_picture  (file, optional)
```

---

## 3. Catalogue — WL Prototypes

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/catalogue/wl/` | ✅ | List active WL prototypes (paginated) |
| GET | `/catalogue/wl/<uuid>/` | ✅ | Prototype detail + gallery images |

**Filters for** `GET /catalogue/wl/`
```
?for_gender=women | men | kids
?garment_type=kurti            (partial match)
?collection_name=diwali        (partial match)
?is_prebooking=true | false
?moq_min=10
?moq_max=50
?search=WL-2025
?ordering=created_at | -created_at | moq | prototype_code
?page=2
```

**Response fields:**
```json
{
  "id", "prototype_code", "collection_name",
  "for_gender", "garment_type",
  "thumbnail_url", "moq", "fit_sizes",
  "is_prebooking", "prebooking_close_date", "is_active",
  "images": [{ "id", "image_url", "sort_order", "uploaded_at" }]
}
```

---

## 4. Catalogue — Fabrics

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/catalogue/fabrics/` | ✅ | List active fabrics (paginated) |
| GET | `/catalogue/fabrics/<uuid>/` | ✅ | Fabric detail + all images |

**Filters for** `GET /catalogue/fabrics/`
```
?fabric_type=regular | new | stock
?fabric_name=cotton              (partial match)
?composition=polyester           (partial match)
?price_min=100
?price_max=500
?width_min=90
?width_max=150
?search=<fabric name, description, composition>
?ordering=fabric_name | price_per_meter | created_at
?page=2
```

**MOQ by fabric type:**

| Type | MOQ |
|---|---|
| `regular` | 400m |
| `new` | 1000m |
| `stock` | No MOQ |

---

## 5. Enquiries

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/enquiries/` | ❌ | Submit enquiry (multipart/form-data) |
| GET | `/enquiries/admin/` | ✅ Admin/Staff | List all enquiries |
| GET | `/enquiries/admin/unread-count/` | ✅ Admin/Staff | Unread count grouped by order type |
| GET | `/enquiries/admin/<uuid>/` | ✅ Admin/Staff | Enquiry detail (auto-marks as viewed) |
| PATCH | `/enquiries/admin/<uuid>/` | ✅ Admin/Staff | Update status / assignee / notes |

**Submit Enquiry** `POST /enquiries/`
```
Content-Type: multipart/form-data

Required:
  order_type    white_label | private_label | fabrics | others
  full_name
  phone
  email
  brand_name
  message

Optional:
  source_page           general | white_label_page | private_label_page | fabrics_page
  company_age_years
  total_pieces_required
  annual_revenue
  wl_prototype          <uuid>  (when coming from a prototype page)
  fabric                <uuid>  (when coming from a fabric page)
  images                (multiple files)
```

**Update Enquiry** `PATCH /enquiries/admin/<uuid>/`
```json
{
  "status": "contacted",
  "assigned_to_user": "<staff-uuid>",
  "admin_notes": "Followed up via phone"
}
```

**Enquiry statuses:** `new` → `contacted` → `waiting_response` → `prospect` → `accepted` / `rejected` / `closed`

**Filters for** `GET /enquiries/admin/`
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

## 6. Orders

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/orders/wl/` | ✅ Customer | Place White Label order |
| POST | `/orders/pl/` | ✅ Customer | Place Private Label order |
| POST | `/orders/fabrics/` | ✅ Customer | Place Fabrics order |
| GET | `/orders/` | ✅ | List orders (admin = all, customer = own) |
| GET | `/orders/<uuid>/` | ✅ | Order detail + stage history + payment info |
| PATCH | `/orders/<uuid>/status/` | ✅ Admin/Staff | Update order stage |
| GET | `/orders/<uuid>/notes/` | ✅ | List notes on order |
| POST | `/orders/<uuid>/notes/` | ✅ | Add note to order |
| GET | `/orders/<uuid>/invoice/` | ✅ | Download PDF invoice |

### Place Order

**White Label** `POST /orders/wl/`
```
Content-Type: multipart/form-data

white_label_catalogue    <uuid>  (required)
size_breakdown           JSON string  e.g. [{"size":"S","quantity":24},{"size":"M","quantity":36}]
customization_notes      (optional)
images                   (files, optional)
```

**Private Label** `POST /orders/pl/`
```
Content-Type: multipart/form-data

style_name       (required)
for_category     women | men | kids  (required)
garment_type     kurti | frock | maxi etc.  (required)
size_breakdown   JSON string  (required)
pl_fabric_1      <uuid>  (optional)
pl_fabric_2      <uuid>  (optional)
pl_fabric_3      <uuid>  (optional)
notes            (optional)
images           (files, optional)
```

**Fabrics** `POST /orders/fabrics/`
```
Content-Type: multipart/form-data

fabric_catalogue    <uuid>   (required)
total_quantity      meters   (required)
message                      (required)
swatch_required     true | false  (optional, default false)
images              (files, optional)
```

### Filters for `GET /orders/`
```
?order_type=white_label | private_label | fabrics
?status=order_placed | cutting | production | packing | payment_pending | payment_done | dispatch | delivered
?fabric_type=regular | new | stock
?for_category=women | men | kids
?date_from=2026-01-01
?date_to=2026-03-15
?search=<order number, email, style name>
?ordering=-created_at | created_at | status | order_type
?page=2
```

### Update Order Stage

**`PATCH /orders/<uuid>/status/`** (Admin / Staff only)
```json
{ "status": "cutting", "notes": "Started cutting today" }
```

### Add Note

**`POST /orders/<uuid>/notes/`**
```json
{ "note": "Customer requested early dispatch" }
```

### Invoice

**`GET /orders/<uuid>/invoice/`**

Returns a branded PDF. Available only when order status is `payment_done`, `dispatch`, or `delivered`.

### Order Detail Response

```json
{
  "id": "<uuid>",
  "order_number": "WL-2026-00001",
  "order_type": "white_label",
  "status": "cutting",
  "assigned_to": { "id": "<uuid>", "email": "staff@huezo.com" },
  "customer": { "id", "email", "brand_name", "contact_name", "phone" },
  "wl_prototype": { "id", "prototype_code", "garment_type", "thumbnail_url" },
  "fabric": null,
  "pl_fabrics": [
    { "choice": 1, "id", "fabric_name", "fabric_type", "composition" }
  ],
  "size_breakdown": [{ "size": "S", "quantity": 24 }],
  "total_quantity": 60,
  "moq": 15,
  "valid_stages": ["order_placed", "cutting", "production", "..."],
  "stage_history": [
    { "stage": "order_placed", "changed_by", "notes", "changed_at" }
  ],
  "payment_amount": "5000.00",
  "payment": {
    "transaction_id", "razorpay_order_id",
    "amount", "currency", "status",
    "payment_reference", "paid_at", "key_id"
  }
}
```

### Order Number Format

| Type | Format | Example |
|---|---|---|
| White Label | `WL-YYYY-NNNNN` | `WL-2026-00001` |
| Private Label | `PL-YYYY-NNNNN` | `PL-2026-00001` |
| Fabrics | `FB-YYYY-NNNNN` | `FB-2026-00001` |

### Order Stages by Type

**White Label:**
```
order_placed → cutting → production → packing → payment_pending → payment_done → dispatch → delivered
```

**Private Label:**
```
order_placed → sampling_fabric → sampling_style → sampling_fit →
sample_approval → sample_rework | sample_approved →
fabric_procurement → cutting → production →
packing → payment_pending → payment_done → dispatch → delivered
```

**Fabrics (with swatch):**
```
order_placed → swatch_sent → swatch_received → swatch_approved | swatch_rework →
procurement → packing → payment_pending → payment_done → dispatch → delivered
```

**Fabrics (no swatch / direct bulk):**
```
order_placed → procurement → packing → payment_pending → payment_done → dispatch → delivered
```

---

## 7. Payments

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/payments/orders/<uuid>/create/` | ✅ Admin/Staff | Create Razorpay order for payment |
| GET | `/payments/orders/<uuid>/status/` | ✅ | Check payment status for an order |
| POST | `/payments/orders/<uuid>/verify/` | ✅ | Verify Razorpay payment after checkout |
| GET | `/payments/transactions/` | ✅ Admin/Staff | List all payment transactions |
| POST | `/payments/webhook/` | ❌ | Razorpay webhook receiver |

**Create Payment** `POST /payments/orders/<uuid>/create/`
```json
{ "amount": 5000.00, "notes": "Payment for WL-2026-00001" }
```

**Verify Payment** `POST /payments/orders/<uuid>/verify/`
```json
{
  "razorpay_payment_id": "pay_xxxxx",
  "razorpay_order_id": "order_xxxxx",
  "razorpay_signature": "signature_string"
}
```

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
5. Customer sees "Pay Now" on the app
6. Customer completes payment via Razorpay checkout
7. Webhook fires → order status auto-updated to payment_done
```

---

## 8. Dashboard

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/dashboard/summary/` | ✅ Admin/Staff | Counts for orders and enquiries |
| GET | `/dashboard/export/orders/` | ✅ Admin/Staff | Download orders as Excel |
| GET | `/dashboard/export/enquiries/` | ✅ Admin/Staff | Download enquiries as Excel |

**Filters for exports:**
```
?order_type=white_label | private_label | fabrics
?status=<status>
?date_from=2026-01-01
?date_to=2026-03-31
```

---

## 9. Notifications

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/notifications/register-token/` | ✅ | Register / update FCM device token |
| GET | `/notifications/` | ✅ | Get last 50 in-app notifications |
| GET | `/notifications/unread-count/` | ✅ | Count of unread notifications |
| POST | `/notifications/mark-read/` | ✅ | Mark notifications as read |
| GET | `/notifications/<uuid>/` | ✅ | Get single notification (auto-marks read) |
| DELETE | `/notifications/<uuid>/` | ✅ | Delete single notification |
| DELETE | `/notifications/` | ✅ | Delete all (or specific) notifications |

**Register FCM Token** `POST /notifications/register-token/`
```json
{ "fcm_token": "firebase_device_token_string", "device_id": "device-uuid" }
```

**List Notifications** `GET /notifications/`
```
?unread_only=true | false
```

**Mark as Read** `POST /notifications/mark-read/`
```json
{ "ids": ["<uuid>", "<uuid>"] }
```
Omit `ids` (or pass empty array) to mark all as read.

**Delete Notifications** `DELETE /notifications/`
```json
{ "ids": ["<uuid>", "<uuid>"] }
```
Omit `ids` to delete all notifications.

**Push notification triggers:**
- Order stage updated
- Any stage history change via admin or API

---

## 10. Banners

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/banners/` | ✅ | Get all active banners (no pagination) |

**Response:**
```json
[
  {
    "id": "<uuid>",
    "title": "Summer Collection",
    "image_url": "http://127.0.0.1:8000/media/banners/summer.jpg",
    "link_url": "https://huezo.com/summer",
    "sort_order": 1
  }
]
```

Banners are managed entirely from Django admin (create / edit / delete / reorder / toggle active).

---

## Admin Panel

Access at: `http://127.0.0.1:8000/admin/`

| Section | Capabilities |
|---|---|
| **Orders** | View all orders, update status, assign staff, set payment amount (auto-creates Razorpay payment), export to Excel, bulk stage actions |
| **Enquiries** | View submissions, assign to staff, update status, mark viewed |
| **Catalogue** | Manage WL prototypes and fabrics with image uploads and gallery management |
| **Banners** | Create / edit / delete banners, set sort order, toggle active, image preview |
| **Payments** | View all transactions with Razorpay order IDs and payment references |
| **Users / Customers** | Manage accounts and brand profiles |
| **Notifications** | View all in-app notification records |

---

## Endpoint Summary

| # | App | Count | Notes |
|---|---|---|---|
| 1 | Auth | 7 | Login, register, JWT refresh, change password |
| 2 | Customer Profile | 4 | Profile + profile picture |
| 3 | WL Catalogue | 2 | List + detail |
| 4 | Fabrics Catalogue | 2 | List + detail |
| 5 | Enquiries | 5 | Public submit + admin management |
| 6 | Orders | 9 | 3 creation types + list/detail/status/notes/invoice |
| 7 | Payments | 5 | Create, verify, status, transactions, webhook |
| 8 | Dashboard | 3 | Summary + 2 Excel exports |
| 9 | Notifications | 7 | FCM token, inbox, read/delete |
| 10 | Banners | 1 | Active banners list |
| **Total** | | **45** | |
