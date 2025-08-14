from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from manager.models import Shop
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class UserViewsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(
            shope_id="testshop",
            name="Test Shop"
        )
        self.user_password = "password123"
        self.user = User.objects.create_user(
            email="user@example.com",
            password=self.user_password,
            username="testuser",
            shop=self.shop
        )

    def get_tokens(self):
        """Helper to log in and get response with tokens (access + refresh in cookies)."""
        url = reverse('token-obtain-pair', kwargs={'shope_id': self.shop.shope_id})
        res = self.client.post(url, {
            "email": self.user.email,
            "password": self.user_password
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return res

    def test_register_valid_shop(self):
        url = reverse('register', kwargs={'shope_id': self.shop.shope_id})
        payload = {
            "email": "new@example.com",
            "username": "newuser",
            "password": "newpass123"
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_register_invalid_shop(self):
        url = reverse('register', kwargs={'shope_id': 'invalidshop'})
        payload = {
            "email": "fail@example.com",
            "username": "failuser",
            "password": "failpass"
        }
        res = self.client.post(url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        res = self.get_tokens()
        self.assertIn('access', res.data)
        self.assertIn('refresh_token', res.cookies)

    def test_login_wrong_password(self):
        url = reverse('token-obtain-pair', kwargs={'shope_id': self.shop.shope_id})
        res = self.client.post(url, {
            "email": self.user.email,
            "password": "wrongpass"
        })
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_success(self):
        login_res = self.get_tokens()
        refresh_cookie = login_res.cookies.get('refresh_token').value
        self.client.cookies['refresh_token'] = refresh_cookie

        url = reverse('token-refresh', kwargs={'shope_id': self.shop.shope_id})
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('access', res.data)

    def test_update_user_same_shop(self):
        login_res = self.get_tokens()
        access = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        url = reverse('update_user', kwargs={
            'shope_id': self.shop.shope_id,
            'pk': self.user.id
        })
        res = self.client.patch(url, {"username": "updateduser"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "updateduser")

    # def test_logout_clears_cookie(self):
    #     from rest_framework_simplejwt.tokens import RefreshToken
    #     refresh = RefreshToken.for_user(self.user)

    #     # ✅ match the cookie name used by your view
    #     self.client.cookies['refresh_token'] = str(refresh)

    #     url = reverse('logout', kwargs={'shope_id': self.shop.shope_id})
    #     res = self.client.post(url)

    #     self.assertEqual(res.status_code, status.HTTP_200_OK)
    #     self.assertNotIn('refresh_token', res.cookies)
