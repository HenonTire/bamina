from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from catalog.models import Product
from orders import services
from orders.models import DeliveryZone, Order
from user.models import Customer, SellerProfile, User

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class OrderFlowTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        seller_user = User.objects.create_user("0933333333", "pw12345")
        self.seller = SellerProfile.objects.create(
            user=seller_user, business_name="Test Shop", status=SellerProfile.Status.APPROVED,
        )
        self.product = Product.objects.create(
            seller=self.seller, name="Red Shoes", price=Decimal("1500"),
            stock=5, status=Product.Status.ACTIVE,
        )
        self.zone = DeliveryZone.objects.create(name="Center", fee=Decimal("50"))

    def payload(self, phone="0911111111", qty=2, **extra):
        data = {
            "name": "Abebe",
            "phone": phone,
            "landmark": "Behind the Mosque",
            "zone_id": self.zone.id,
            "items": [{"product_id": str(self.product.id), "quantity": qty}],
        }
        data.update(extra)
        return data

    def place(self, **kw):
        return self.client.post("/orders", self.payload(**kw), format="json")

    # ---- guest checkout ----

    def test_guest_order_uses_db_prices_and_returns_token(self):
        r = self.place()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Decimal(str(r.data["total"])), Decimal("3050.00"))  # 2*1500 + 50
        self.assertTrue(r.data["needs_confirmation_call"])
        self.assertTrue(r.data["tracking_token"])

        order = Order.objects.get(code=r.data["code"])
        self.assertIsNone(order.placed_by)
        self.assertEqual(order.customer_phone, "+251911111111")
        self.assertNotEqual(order.tracking_token_hash, r.data["tracking_token"])  # only hash stored

    def test_stock_decrements_and_oversell_blocked(self):
        self.assertEqual(self.place(qty=4).status_code, 201)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.place(phone="0922222222", qty=2).status_code, 409)

    def test_unapproved_seller_product_unavailable(self):
        self.seller.status = SellerProfile.Status.SUSPENDED
        self.seller.save()
        self.assertEqual(self.place().status_code, 400)

    def test_blocked_customer_rejected(self):
        Customer.objects.create(phone="+251944444444", is_blocked=True)
        self.assertEqual(self.place(phone="0944444444").status_code, 403)

    def test_pending_limit_per_phone(self):
        for _ in range(services.LIMIT_PHONE_PENDING):
            self.assertEqual(self.place(qty=1).status_code, 201)
        self.assertEqual(self.place(qty=1).status_code, 429)

    def test_bad_token_still_works_as_guest(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer garbage.token.value")
        self.assertEqual(self.place().status_code, 201)

    # ---- tracking ----

    def test_tracking_needs_secret_token(self):
        r = self.place()
        code, token = r.data["code"], r.data["tracking_token"]

        ok = self.client.get(f"/orders/track/{code}?t={token}")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["code"], code)
        self.assertNotIn("customer_phone", ok.data)

        self.assertEqual(self.client.get(f"/orders/track/{code}").status_code, 404)
        self.assertEqual(self.client.get(f"/orders/track/{code}?t=wrong").status_code, 404)
        self.assertEqual(self.client.get("/orders/track/BM-NOPE12?t=x").status_code, 404)

    # ---- history isolation ----

    def test_unverified_account_cannot_see_guest_orders_on_its_phone(self):
        guest = self.place(phone="0955555555")
        self.assertEqual(guest.status_code, 201)

        # attacker registers the victim's phone (no verification needed)
        reg = self.client.post(
            "/auth/register", {"phone": "0955555555", "password": "attack99"}, format="json"
        )
        self.assertEqual(reg.status_code, 201, reg.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {reg.data['access']}")

        self.assertEqual(self.client.get("/orders/mine").data["count"], 0)

        # once the phone is verified (Telegram link), history appears
        Customer.objects.filter(phone="+251955555555").update(is_verified=True)
        self.assertEqual(self.client.get("/orders/mine").data["count"], 1)

    def test_logged_in_order_visible_and_cancellable(self):
        reg = self.client.post(
            "/auth/register", {"phone": "0966666666", "password": "mypass12"}, format="json"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {reg.data['access']}")

        r = self.place(phone="0966666666", qty=3)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get("/orders/mine").data["count"], 1)

        c = self.client.post(f"/orders/mine/{r.data['code']}/cancel")
        self.assertEqual(c.status_code, 200, c.data)
        self.assertEqual(c.data["status"], "cancelled")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)  # restocked

    # ---- status flow, trust, seller view ----

    def test_status_flow_trust_and_seller_visibility(self):
        r = self.place(qty=1)
        order = Order.objects.get(code=r.data["code"])
        staff = User.objects.create_superuser("0977777777", "adminpass1")

        # seller cannot see unconfirmed orders
        self.client.force_authenticate(self.seller.user)
        self.assertEqual(self.client.get("/orders/seller/items").data["count"], 0)

        # invalid jump rejected
        with self.assertRaises(services.OrderError):
            services.change_status(order, Order.Status.DELIVERED, by=staff)

        services.change_status(order, Order.Status.CONFIRMED, by=staff)

        items = self.client.get("/orders/seller/items")
        self.assertEqual(items.data["count"], 1)
        self.assertNotIn("customer_phone", items.data["results"][0])

        ready = self.client.post(f"/orders/seller/items/{items.data['results'][0]['id']}/ready")
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.data["status"], "ready")

        for st in (Order.Status.PREPARING, Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED):
            services.change_status(order, st, by=staff)

        customer = Customer.objects.get(phone="+251911111111")
        self.assertEqual(customer.trust_level, Customer.TrustLevel.VERIFIED)

        # next order from the trusted customer needs no confirmation call
        second = self.place(qty=1)
        self.assertFalse(second.data["needs_confirmation_call"])

    def test_unapproved_seller_blocked_from_seller_endpoints(self):
        pending_user = User.objects.create_user("0988888888", "pw12345")
        SellerProfile.objects.create(user=pending_user, business_name="New")
        self.client.force_authenticate(pending_user)
        self.assertEqual(self.client.get("/orders/seller/items").status_code, 403)

    # ---- public catalog ----

    def test_public_catalog_hides_drafts_and_unapproved(self):
        Product.objects.create(seller=self.seller, name="Draft thing", price=1)
        r = self.client.get("/products")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p["name"] for p in r.data["results"]], ["Red Shoes"])

        self.seller.status = SellerProfile.Status.PENDING
        self.seller.save()
        self.assertEqual(self.client.get("/products").data["count"], 0)