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
```

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

**My Profile** `GET /customers/me/`
```json
// Output
{ "id", "email", "brand_name", "contact_name", "phone",
  "city", "state", "country", "full_address", "created_at" }
```

**Catalogue List** `GET /catalogue/wl/`
```json
// Output
{ "count", "next", "previous",
  "results": [{ "id", "prototype_code", "garment_type",
                "collection_name", "for_gender", "moq",
                "fit_sizes", "is_prebooking", "thumbnail_url" }] }
```

**Catalogue Detail** `GET /catalogue/wl/<uuid>/`
```json
// Output — same as list item plus:
{ "customization_available", "images": [{ "image_url", "sort_order" }],
  "created_by_admin", "updated_at" }
```

**Fabrics List** `GET /catalogue/fabrics/`
```json
// Output
{ "count", "next", "previous",
  "results": [{ "id", "fabric_type", "fabric_name", "composition",
                "width_cm", "price_per_meter", "stock_available_meters",
                "effective_moq", "thumbnail_url", "is_active" }] }
```

**Fabrics Detail** `GET /catalogue/fabrics/<uuid>/`
```json
// Output — same as list item plus:
{ "description", "moq_regular", "moq_new", "colour_options",
  "images": [{ "image_url", "is_thumbnail", "sort_order" }],
  "created_by", "created_at", "updated_at" }
```

**Submit Enquiry** `POST /enquiries/`
```json
// Input (multipart/form-data)
{ "order_type", "full_name", "phone", "email", "brand_name",
  "message", "source_page",
  "company_age_years"(opt), "total_pieces_required"(opt),
  "annual_revenue"(opt), "wl_prototype"(opt), "fabric"(opt),
  "images"(opt, multiple files) }

// Output
{ "message", "data": { "id", "enquiry_number", "order_type",
  "full_name", "phone", "email", "brand_name", "status",
  "wl_prototype", "fabric", "images", "created_at" } }
```

**List Enquiries** `GET /enquiries/admin/`
```json
// Output
{ "count", "next", "previous",
  "results": [{ "id", "enquiry_number", "order_type", "full_name",
                "phone", "email", "brand_name", "total_pieces_required",
                "status", "is_viewed", "assigned_to", "created_at" }] }
```

**Update Enquiry** `PATCH /enquiries/admin/<uuid>/`
```json
// Input
{ "status"(opt), "assigned_to_user"(opt), "admin_notes"(opt) }

// Output — full enquiry detail
```

**Unread Count** `GET /enquiries/admin/unread-count/`
```json
// Output
{ "total", "private_label", "white_label", "fabrics", "others" }
```