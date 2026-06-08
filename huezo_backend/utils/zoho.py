import logging
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("orders.zoho")

class ZohoBooksClient:
    def __init__(self):
        self.base_url = settings.ZOHO_BOOKS_API_BASE_URL.rstrip('/')
        self.client_id = settings.ZOHO_CLIENT_ID
        self.client_secret = settings.ZOHO_CLIENT_SECRET
        self.refresh_token = settings.ZOHO_REFRESH_TOKEN
        self.org_id = settings.ZOHO_ORGANIZATION_ID
        
        # Determine OAuth domain based on API Base URL
        if ".in" in self.base_url:
            self.oauth_url = "https://accounts.zoho.in/oauth/v2/token"
        else:
            self.oauth_url = "https://accounts.zoho.com/oauth/v2/token"

    def get_access_token(self):
        """Exchange the refresh token for a short-lived access token."""
        data = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }
        try:
            response = requests.post(self.oauth_url, data=data)
            res_data = response.json()
            if response.status_code == 200 and "access_token" in res_data:
                return res_data["access_token"]
            else:
                logger.error(f"Zoho token refresh failed: {res_data}")
                raise Exception(f"Failed to refresh Zoho access token: {res_data.get('error')}")
        except Exception as e:
            logger.error(f"Error fetching Zoho token: {e}")
            raise

    def get_headers(self, accept_pdf=False):
        """Generate standard headers for Zoho Books API requests."""
        token = self.get_access_token()
        headers = {
            "Authorization": f"Zoho-oauthtoken {token}",
            "X-com-zoho-books-organizationid": self.org_id,
        }
        if not accept_pdf:
            headers["Content-Type"] = "application/json"
        return headers

    def get_or_create_contact(self, customer):
        """Find contact by email in Zoho Books or create a new one."""
        # Step 1: Check if already stored in Django DB
        if customer.zoho_contact_id:
            return customer.zoho_contact_id

        headers = self.get_headers()
        email = customer.user.email

        # Step 2: Search contact by email
        search_url = f"{self.base_url}/contacts"
        try:
            response = requests.get(search_url, headers=headers, params={"email": email})
            res_data = response.json()
            if response.status_code == 0 or (response.status_code == 200 and res_data.get("code") == 0):
                contacts = res_data.get("contacts", [])
                if contacts:
                    # Contact found, save ID to local model
                    contact_id = contacts[0]["contact_id"]
                    customer.zoho_contact_id = contact_id
                    customer.save(update_fields=["zoho_contact_id"])
                    return contact_id
            else:
                logger.warning(f"Zoho contact search returned code: {res_data.get('code')}, msg: {res_data.get('message')}")
        except Exception as e:
            logger.error(f"Error searching Zoho contact: {e}")

        # Step 3: Create contact if not found
        create_url = f"{self.base_url}/contacts"
        contact_payload = {
            "contact_name": customer.contact_name or customer.brand_name,
            "company_name": customer.brand_name,
            "contact_type": "customer",
            "contact_persons": [
                {
                    "first_name": customer.contact_name,
                    "email": email,
                    "phone": customer.phone,
                    "is_primary_contact": True
                }
            ],
            "billing_address": {
                "address": customer.address_line1 or "",
                "street2": customer.address_line2 or "",
                "city": customer.city or "",
                "state": customer.state or "",
                "zip": customer.pin_code or "",
                "country": customer.country or "India"
            },
            "shipping_address": {
                "address": customer.address_line1 or "",
                "street2": customer.address_line2 or "",
                "city": customer.city or "",
                "state": customer.state or "",
                "zip": customer.pin_code or "",
                "country": customer.country or "India"
            }
        }
        try:
            response = requests.post(create_url, headers=headers, json=contact_payload)
            res_data = response.json()
            if response.status_code == 201 or (response.status_code == 200 and res_data.get("code") == 0):
                contact_id = res_data["contact"]["contact_id"]
                customer.zoho_contact_id = contact_id
                customer.save(update_fields=["zoho_contact_id"])
                return contact_id
            else:
                logger.error(f"Zoho contact creation failed: {res_data}")
                raise Exception(f"Failed to create Zoho contact: {res_data.get('message')}")
        except Exception as e:
            logger.error(f"Error creating Zoho contact: {e}")
            raise

    def _build_description(self, order, prefix="", transaction=None):
        desc_parts = [prefix] if prefix else []
        
        # Style details
        if order.style_name:
            desc_parts.append(f"Style: {order.style_name}")
        if order.garment_type:
            desc_parts.append(f"Garment: {order.garment_type}")
            
        # Collection / Prototype info
        if order.white_label_catalogue:
            wl = order.white_label_catalogue
            coll_name = wl.collection_name or "N/A"
            desc_parts.append(f"Collection: {coll_name} (Code: {wl.prototype_code})")
            
        # Fabric info
        if order.fabric_catalogue:
            desc_parts.append(f"Fabric: {order.fabric_catalogue.fabric_name}")
            
        # Alternate PL fabric selections
        pl_fabrics = []
        if hasattr(order, 'pl_fabric_1') and order.pl_fabric_1:
            pl_fabrics.append(order.pl_fabric_1.fabric_name)
        if hasattr(order, 'pl_fabric_2') and order.pl_fabric_2:
            pl_fabrics.append(order.pl_fabric_2.fabric_name)
        if hasattr(order, 'pl_fabric_3') and order.pl_fabric_3:
            pl_fabrics.append(order.pl_fabric_3.fabric_name)
        if pl_fabrics:
            desc_parts.append(f"Selected Fabrics: {', '.join(pl_fabrics)}")

        # Order Placed Date
        if order.created_at:
            order_date_str = timezone.localtime(order.created_at).strftime("%d/%m/%Y")
            desc_parts.append(f"Order Placed: {order_date_str}")

        # Payment Done Date (if transaction is paid)
        if transaction and transaction.paid_at:
            pay_done_str = timezone.localtime(transaction.paid_at).strftime("%d/%m/%Y")
            desc_parts.append(f"Payment Done Date: {pay_done_str}")

        # Size Breakdown
        if order.size_breakdown:
            try:
                import json
                sizes = order.size_breakdown
                if isinstance(sizes, str):
                    sizes = json.loads(sizes)
                unit = "meters" if order.order_type == "fabrics" else "pcs"
                size_strs = [f"{sb.get('size', '?')}: {sb.get('quantity', '?')} {unit}" for sb in sizes]
                desc_parts.append(f"Size Breakdown: {', '.join(size_strs)}")
            except Exception:
                pass
                
        return "\n".join(desc_parts)

    def create_invoice(self, order, invoice_type="final"):
        """Create an invoice in Zoho Books."""
        headers = self.get_headers()
        customer = order.customer_user.customer_profile
        contact_id = self.get_or_create_contact(customer)

        gst_pct = float(order.gst_percentage or 5.0)
        
        # Use local timezone order placement date
        order_date_str = timezone.localtime(order.created_at).strftime("%Y-%m-%d")

        # ── Fetch payment transaction for this invoice type ──
        from payments.models import PaymentTransaction
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(order)
        
        transaction = None
        if invoice_type == "advance":
            transaction = PaymentTransaction.objects.filter(
                content_type=ct,
                object_id=order.id,
                status="paid",
                notes__icontains="advance",
            ).order_by("-paid_at").first()
        else:
            transaction = PaymentTransaction.objects.filter(
                content_type=ct,
                object_id=order.id,
                status="paid",
            ).exclude(notes__icontains="advance").order_by("-paid_at").first()

        # ── Item Details & Calculations ──
        if invoice_type == "advance":
            # For advance, subtotal = total_round / (1 + gst_pct / 100)
            total_amt = float(order.advance_amount or 0.0)
            subtotal = total_amt / (1.0 + gst_pct / 100.0)
            
            desc = self._build_description(order, prefix=f"Advance Payment (50%) for Order {order.order_number}", transaction=transaction)
            
            line_items = [{
                "name": f"Advance Invoice - {order.order_number}",
                "description": desc,
                "rate": round(subtotal, 2),
                "quantity": 1,
                "hsn_or_sac": order.hsn_code or "",
                "tax_percentage": gst_pct
            }]
            inv_number = f"INV-ADV-{order.order_number}"
        else:
            # For final, subtotal = unit_price * total_quantity
            qty = float(order.total_quantity or 1)
            unit_price = float(order.unit_price or 0.0)
            
            desc = self._build_description(order, prefix=f"Final Invoice for Order {order.order_number}", transaction=transaction)
            
            line_items = [{
                "name": f"Order Invoice - {order.order_number}",
                "description": desc,
                "rate": round(unit_price, 2),
                "quantity": qty,
                "hsn_or_sac": order.hsn_code or "",
                "tax_percentage": gst_pct
            }]
            inv_number = f"INV-FIN-{order.order_number}"

        invoice_payload = {
            "customer_id": contact_id,
            "reference_number": inv_number,
            "date": order_date_str,
            "due_date": order_date_str,
            "line_items": line_items,
            "hsn_or_sac": order.hsn_code or ""
        }

        # Check if invoice already exists in Zoho to avoid duplicates
        check_url = f"{self.base_url}/invoices"
        try:
            response = requests.get(check_url, headers=headers, params={"reference_number": inv_number})
            res_data = response.json()
            if response.status_code == 200 and res_data.get("code") == 0:
                invoices = res_data.get("invoices", [])
                if invoices:
                    invoice_id = invoices[0]["invoice_id"]
                    if invoice_type == "advance":
                        order.zoho_advance_invoice_id = invoice_id
                        order.save(update_fields=["zoho_advance_invoice_id"])
                    else:
                        order.zoho_final_invoice_id = invoice_id
                        order.save(update_fields=["zoho_final_invoice_id"])
                    return invoice_id
        except Exception as e:
            logger.error(f"Error checking Zoho invoice duplicate: {e}")

        # Post creation to Zoho Books
        create_url = f"{self.base_url}/invoices"
        try:
            response = requests.post(create_url, headers=headers, json=invoice_payload)
            res_data = response.json()
            if response.status_code == 201 or (response.status_code == 200 and res_data.get("code") == 0):
                invoice_id = res_data["invoice"]["invoice_id"]
                if invoice_type == "advance":
                    order.zoho_advance_invoice_id = invoice_id
                    order.save(update_fields=["zoho_advance_invoice_id"])
                else:
                    order.zoho_final_invoice_id = invoice_id
                    order.save(update_fields=["zoho_final_invoice_id"])
                
                # Automatically mark invoice as sent in Zoho so it accepts payments
                # API: POST /invoices/{invoice_id}/status/sent
                requests.post(f"{create_url}/{invoice_id}/status/sent", headers=headers)
                
                return invoice_id
            else:
                logger.error(f"Zoho invoice creation failed: {res_data}")
                raise Exception(f"Failed to create Zoho Invoice: {res_data.get('message')}")
        except Exception as e:
            logger.error(f"Error creating Zoho Invoice: {e}")
            raise

    def record_payment(self, order, transaction, invoice_type="final"):
        """Record customer payment against Zoho invoice."""
        headers = self.get_headers()
        customer = order.customer_user.customer_profile
        contact_id = self.get_or_create_contact(customer)

        if invoice_type == "advance":
            invoice_id = order.zoho_advance_invoice_id or self.create_invoice(order, "advance")
            amount = float(order.advance_amount or 0.0)
        else:
            invoice_id = order.zoho_final_invoice_id or self.create_invoice(order, "final")
            amount = float(order.total_amount or 0.0) - float(order.advance_amount or 0.0)
            
        pay_date_str = timezone.localtime(transaction.paid_at).strftime("%Y-%m-%d") if transaction.paid_at else timezone.localtime(timezone.now()).strftime("%Y-%m-%d")

        payment_payload = {
            "customer_id": contact_id,
            "payment_mode": "Razorpay",
            "amount": round(amount, 2),
            "date": pay_date_str,
            "reference_number": transaction.payment_reference or "",
            "description": f"Razorpay payment ref: {transaction.payment_reference}",
            "invoices": [
                {
                    "invoice_id": invoice_id,
                    "amount_applied": round(amount, 2)
                }
            ]
        }

        pay_url = f"{self.base_url}/customerpayments"
        try:
            response = requests.post(pay_url, headers=headers, json=payment_payload)
            res_data = response.json()
            if response.status_code == 201 or (response.status_code == 200 and res_data.get("code") == 0):
                logger.info(f"Payment recorded successfully in Zoho Books for order {order.order_number}")
                return res_data["payment"]["payment_id"]
            else:
                logger.error(f"Zoho record payment failed: {res_data}")
        except Exception as e:
            logger.error(f"Error recording payment in Zoho: {e}")

    def create_sales_order(self, order):
        """Create a Sales Order in Zoho Books for confirmed orders (Huezo as Vendor)."""
        headers = self.get_headers()
        customer = order.customer_user.customer_profile
        contact_id = self.get_or_create_contact(customer)

        # Build description
        desc_str = self._build_description(order)
        rate = float(order.unit_price or 0.0)
        qty = float(order.total_quantity or 1)
        
        # Use local timezone order placement date
        order_date_str = timezone.localtime(order.created_at).strftime("%Y-%m-%d")

        so_number = f"SO-{order.order_number}"

        so_payload = {
            "customer_id": contact_id,
            "reference_number": so_number,
            "date": order_date_str,
            "line_items": [
                {
                    "name": f"Sales Order - {order.order_number}",
                    "description": desc_str,
                    "rate": round(rate, 2),
                    "quantity": qty,
                    "tax_percentage": float(order.gst_percentage or 5.0)
                }
            ]
        }

        # Check duplicate
        check_url = f"{self.base_url}/salesorders"
        try:
            response = requests.get(check_url, headers=headers, params={"reference_number": so_number})
            res_data = response.json()
            if response.status_code == 200 and res_data.get("code") == 0:
                salesorders = res_data.get("salesorders", [])
                if salesorders:
                    so_id = salesorders[0]["salesorder_id"]
                    order.zoho_po_id = so_id
                    order.save(update_fields=["zoho_po_id"])
                    return so_id
        except Exception as e:
            logger.error(f"Error checking Zoho sales order duplicate: {e}")

        # Post creation to Zoho Books
        create_url = f"{self.base_url}/salesorders"
        try:
            response = requests.post(create_url, headers=headers, json=so_payload)
            res_data = response.json()
            if response.status_code == 201 or (response.status_code == 200 and res_data.get("code") == 0):
                so_id = res_data["salesorder"]["salesorder_id"]
                order.zoho_po_id = so_id
                order.save(update_fields=["zoho_po_id"])
                return so_id
            else:
                logger.error(f"Zoho Sales Order creation failed: {res_data}")
                raise Exception(f"Failed to create Zoho Sales Order: {res_data.get('message')}")
        except Exception as e:
            logger.error(f"Error creating Zoho Sales Order: {e}")
            raise

    def get_invoice_pdf(self, invoice_id):
        """Fetch the PDF bytes of an invoice from Zoho Books API."""
        headers = self.get_headers(accept_pdf=True)
        url = f"{self.base_url}/invoices/{invoice_id}"
        try:
            response = requests.get(url, headers=headers, params={"accept": "pdf"})
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to download Zoho invoice PDF. Status: {response.status_code}, Body: {response.text[:200]}")
                raise Exception(f"Failed to download Zoho invoice PDF: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching Zoho invoice PDF: {e}")
            raise

    def get_sales_order_pdf(self, so_id):
        """Fetch the PDF bytes of a Sales Order from Zoho Books API."""
        headers = self.get_headers(accept_pdf=True)
        url = f"{self.base_url}/salesorders/{so_id}"
        try:
            response = requests.get(url, headers=headers, params={"accept": "pdf"})
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Failed to download Zoho Sales Order PDF. Status: {response.status_code}, Body: {response.text[:200]}")
                raise Exception(f"Failed to download Zoho Sales Order PDF: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching Zoho Sales Order PDF: {e}")
            raise
