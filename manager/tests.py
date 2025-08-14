from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from manager.models import Shop, ShopOwner
from api.models import Products, Order, OrderStatus
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

User = get_user_model()

class ManagerViewsTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        # Create shop
        self.shop = Shop.objects.create(name="Test Shop", shope_id="test-shop")

        # Create a user and assign as shop owner
        self.user_password = "pass1234"
        self.user = User.objects.create_user(email="admin@example.com", username="adminuser", password=self.user_password)
        self.shop_owner = ShopOwner.objects.create(user=self.user, shop=self.shop)

        # Create a product for revenue tests
        self.product = Products.objects.create(
            name="Test Product", price=100, shop=self.shop
        )
        
        # Create an order
        self.order = Order.objects.create(shop=self.shop, user=self.user, total=100, status=OrderStatus.IN_PROCESS)

    def authenticate(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        return refresh.access_token

    def test_register_shope(self):
        # Register shop usually allowed without auth, if not, call authenticate() first
        url = reverse('register_shope')
        data = {"name": "New Shop"}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Shop.objects.filter(name="New Shop").exists())


    def test_create_product_success(self):
        self.authenticate()  # make sure user is authenticated

        url = reverse('create_product', kwargs={'shop_id': self.shop.shope_id})

        dummy_image = SimpleUploadedFile(
            name='test_image.gif',
            content=(
                b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
                b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
                b'\x00\x02\x02D\x01\x00;'
            ),
            content_type='image/gif'
        )


        data = {
            "name": "New Product",
            "description": "This is a new test product",
            "price": "50.00",
            "category": "popular_picks",
            "image": dummy_image,
            "size": "medium",
        }

        res = self.client.post(url, data, format='multipart')

        print('Response status:', res.status_code)
        print('Response data:', res.data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['name'], "New Product")
        self.assertEqual(res.data['price'], "50.00")
        self.assertEqual(res.data['category'], "popular_picks")


    def test_create_product_shop_not_exist(self):
        self.authenticate()
        url = reverse('create_product', kwargs={'shop_id': 'no-such-shop'})
        data = {"name": "Fail Prod", "price": 10}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_total_revenue_view(self):
        self.authenticate()
        url = reverse('total_revenue', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(float(res.data['total_revenue']), 100)

    def test_total_orders_view(self):
        self.authenticate()
        url = reverse('total_orders', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['total_orders'], 1)

    def test_list_shop_products(self):
        self.authenticate()
        url = reverse('list_shop_products', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data) > 0)

    def test_product_detail_update(self):
        self.authenticate()
        url = reverse('product_detail', kwargs={'shop_id': self.shop.shope_id, 'pk': self.product.pk})
        data = {"price": 150}
        res = self.client.patch(url, data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(float(self.product.price), 150)

    def test_list_shop_users(self):
        self.authenticate()
        url = reverse('list_shop_users', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Assuming response includes a list of users with 'email' keys
        self.assertTrue(any(u['email'] == self.user.email for u in res.data.get('users', [])))

    def test_shop_product_num_by_category(self):
        self.authenticate()
        url = reverse('shop_product_num_by_category', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('category_counts', res.data)

    def test_admin_login_success(self):
        url = reverse('admin_login')
        data = {
            'email': self.user.email,
            'password': self.user_password
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)
        self.assertEqual(res.data['username'], self.user.username)
        self.assertEqual(res.data['shop_id'], self.shop.shope_id)

    def test_admin_login_fail(self):
        url = reverse('admin_login')
        data = {
            'email': self.user.email,
            'password': 'wrongpass'
        }
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
