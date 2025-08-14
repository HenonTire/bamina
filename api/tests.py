from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Shop, Products, WhishList, CartItem, Order, OrderItem, Adress

User = get_user_model()

class APITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
        email='test@example.com', 
        password='pass123'
    )
        self.client.force_authenticate(user=self.user)

        # Create a shop
        self.shop = Shop.objects.create(name='Test Shop', shope_id='testshop123')

        # Create product for the shop
        self.product = Products.objects.create(
            shop=self.shop,
            name='Test Product',
            description='Description',
            price=10.00,
            category='popular_picks',
            size='medium',
            image='path/to/image.jpg'  # You might want to mock this for real tests
        )

    def test_list_products(self):
        url = reverse('listproducts', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 1)

    def test_product_detail(self):
        url = reverse('detailproduct', kwargs={'shop_id': self.shop.shope_id, 'pk': self.product.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['name'], self.product.name)

    def test_add_to_wishlist(self):
        url = reverse('add_whish', kwargs={'shop_id': self.shop.shope_id})
        data = {'product_id': self.product.id}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_add_duplicate_to_wishlist(self):
        url = reverse('add_whish', kwargs={'shop_id': self.shop.shope_id})
        data = {'product_id': self.product.id}
        # Add first time
        self.client.post(url, data)
        # Add second time - should fail
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_to_cart(self):
        url = reverse('add_to_cart', kwargs={'shop_id': self.shop.shope_id})
        data = {'product_id': self.product.id}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_place_order_with_empty_cart(self):
        url = reverse('place_order', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.post(url, {})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_place_order_success(self):
        self.client.force_authenticate(user=self.user)

        # Create a cart item for the user in the shop before placing order
        CartItem.objects.create(user=self.user, product=self.product, quantity=2)

        url = reverse('place_order', kwargs={'shop_id': self.shop.shope_id})

        data = {
            "shop_fcm_token": "fcmtoken_example123",
            "shipping_address": "123 Main St, City"
            
            }

        res = self.client.post(url, data, format='json')

        print("Response status:", res.status_code)
        print("Response data:", res.data)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)


        # Add more tests for search, feedback, wishlist list, cart list, order list, address create/list, etc.

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Shop, Products, WhishList, CartItem, Order, OrderItem, Adress, ProdyctFeedback, ShopFeedBack

User = get_user_model()
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Shop, Products, WhishList, CartItem, Order, OrderItem, Adress

User = get_user_model()

class APITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com', 
            password='pass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create a shop
        self.shop = Shop.objects.create(name='Test Shop', shope_id='testshop123')

        # Create product for the shop
        self.product = Products.objects.create(
            shop=self.shop,
            name='Test Product',
            description='Description',
            price=10.00,
            category='popular_picks',
            size='medium',
            image='path/to/image.jpg'  # Mock or dummy value
        )

    def test_list_products(self):
        url = reverse('listproducts', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 1)

    def test_product_detail(self):
        url = reverse('detailproduct', kwargs={'shop_id': self.shop.shope_id, 'pk': self.product.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['name'], self.product.name)

    def test_add_to_wishlist(self):
        url = reverse('add_whish', kwargs={'shop_id': self.shop.shope_id})
        data = {'product_id': self.product.id}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_add_duplicate_to_wishlist(self):
        url = reverse('add_whish', kwargs={'shop_id': self.shop.shope_id})
        data = {'product_id': self.product.id}
        # Add first time
        self.client.post(url, data)
        # Add second time - should fail
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wishlist_list(self):
        url = reverse('wishlistlist', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_add_to_cart(self):
        url = reverse('add_to_cart', kwargs={'shop_id': self.shop.shope_id})
        data = {'product_id': self.product.id}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_cart_list(self):
        url = reverse('cartlist', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_place_order_with_empty_cart(self):
        url = reverse('place_order', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.post(url, {})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_place_order_success(self):
        # Add cart item first
        CartItem.objects.create(user=self.user, product=self.product, quantity=2)
        url = reverse('place_order', kwargs={'shop_id': self.shop.shope_id})
        data = {
            "shop_fcm_token": "fcmtoken_example123",
            "shipping_address": "123 Main St, City"
        }
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_add_product_feedback(self):
        url = reverse('productfeedback', kwargs={'shop_id': self.shop.shope_id, 'product_id': self.product.id})
        data = {'rating': 5, 'comment': 'Great product!'}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_add_shop_feedback(self):
        url = reverse('shopfeedback', kwargs={'shop_id': self.shop.shope_id})
        data = {'rating': 4, 'comment': 'Good shop!'}
        res = self.client.post(url, data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_feedback_list(self):
        url = reverse('feedbacklist', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_address_create_and_list(self):
        url_create = reverse('create_address', kwargs={'shop_id': self.shop.shope_id})
        data = {
            "address": "123 Main St",   # required field based on error
            "city": "Test City",
            "state": "Test State",
            "postal_code": "12345",
            "country": "Test Country"
        }
        res_create = self.client.post(url_create, data, format='json')

        print("Create Address response status:", res_create.status_code)
        print("Create Address response data:", res_create.data)

        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)

        url_list = reverse('addresslist', kwargs={'shop_id': self.shop.shope_id})
        res_list = self.client.get(url_list)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)

    def test_search_product(self):
        url = reverse('searchproduct', kwargs={'shop_id': self.shop.shope_id, 'q': 'Test'})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(self.product.name in p['name'] for p in res.data))

    def test_list_products_by_category(self):
        url = reverse('listproductsbycategory', kwargs={'shop_id': self.shop.shope_id, 'category': 'popular_picks'})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res.data), 1)

    def test_feedback_detail_retrieve_update_delete(self):
        # create feedback first
        feedback = ShopFeedBack.objects.create(shop=self.shop, user=self.user, rating=5, comment='Nice')
        url = reverse('feedbackdetail', kwargs={'shop_id': self.shop.shope_id, 'pk': feedback.pk})

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.patch(url, {'comment': 'Updated comment'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_wishlist_detail_retrieve_update_delete(self):
        wishlist = WhishList.objects.create(user=self.user)
        wishlist.products.add(self.product)
        url = reverse('wishlistdetail', kwargs={'shop_id': self.shop.shope_id, 'pk': wishlist.pk})

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Update test (if allowed)
        res = self.client.patch(url, {}, format='json')  # Provide fields if needed
        self.assertIn(res.status_code, [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED])

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_order_detail_retrieve_update_delete(self):
        # Create an order
        order = Order.objects.create(user=self.user, shop=self.shop, total=20, status='IN_PROCESS')
        url = reverse('orderdetail', kwargs={'shop_id': self.shop.shope_id, 'pk': order.pk})

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.patch(url, {'status': 'COMPLETED'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_order_single_product_post(self):
        url = reverse('ordersingleproduct', kwargs={'shop_id': self.shop.shope_id})
        data = {
            'product_id': self.product.id,
            'shipping_address': '123 Main St',
            'shop_fcm_token': 'fcmtoken_example123',
        }
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_order_list(self):
        Order.objects.create(user=self.user, shop=self.shop, total=10, status='IN_PROCESS')
        url = reverse('orderlist', kwargs={'shop_id': self.shop.shope_id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_address_detail_retrieve_update_delete(self):
        address = Adress.objects.create(user=self.user, address="123 Main St")
        url = reverse('addressdetail', kwargs={'shop_id': self.shop.shope_id, 'pk': address.pk})

        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.patch(url, {'city': 'New City'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

