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

#Enter
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
                "fit_sizes", "is_prebooking", "thumbnail_storage_path" }] }
```

**Catalogue Detail** `GET /catalogue/wl/<uuid>/`
```json
// Output — same as list item plus:
{ "customization_available", "images": [{ "storage_path", "sort_order" }],
  "created_by_admin", "updated_at" }
```
