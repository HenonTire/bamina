from django.shortcuts import render
from django.shortcuts import render
from .models import PaymentTransaction
import uuid
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import redirect
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
import os
from dotenv import load_dotenv
from api.models import Order  # Ensure this is your model

  # Ensure this is your model

# Replace with your actual secret key in environment for production
load_dotenv()
CHAPA_API_KEY = os.getenv("CHAPA_API_KEY")
CHAPA_BASE_URL = "https://api.chapa.co/v1"

class ChapaPaymentInitView(APIView):
    """
    Initializes a payment with Chapa and returns a checkout URL
    """
    def post(self, request):
        data = request.data
        tx_ref = str(uuid.uuid4())

        callback_url = "https://dd91e8c58cd3.ngrok-free.app/payment/payment/callback/"
        return_url = f"https://dd91e8c58cd3.ngrok-free.app/payment/payment/verify/?tx_ref={tx_ref}"

        payload = {
            "amount": data.get("amount"),
            "currency": "ETB",
            "email": data.get("email"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "tx_ref": tx_ref,
            "callback_url": callback_url,
            "return_url": return_url,
            "customization[title]": "Bamina Order Payment",
            "customization[description]": "Pay for your order.",
            "custom_data[order_id]": data.get("order_id"), 
        }

        headers = {
            "Authorization": f"Bearer {CHAPA_API_KEY}"
        }

        chapa_response = requests.post(f"{CHAPA_BASE_URL}/transaction/initialize", data=payload, headers=headers)
        print("CHAPA INIT RESPONSE:", chapa_response.status_code, chapa_response.text)

        if chapa_response.status_code == 200:
            checkout_url = chapa_response.json()["data"]["checkout_url"]
            return Response({"checkout_url": checkout_url})
        else:
            return Response({"error": "Failed to initialize payment"}, status=400)


class ChapaCallbackView(APIView):
    """
    Handles Chapa callback after payment (POST or GET)
    """
    def get(self, request):
        print("Callback received via GET:", request.GET)
        return self.handle_callback(request.GET, request)

    def post(self, request):
        print("Callback received via POST:", request.data)
        return self.handle_callback(request.data, request)

    def handle_callback(self, params, request):
        tx_ref = (
            params.get("tx_ref") or
            (params.get("data", {}).get("tx_ref") if isinstance(params.get("data"), dict) else None)
        )
        print("Extracted tx_ref:", tx_ref)

        if not tx_ref:
            return Response({"message": "Missing tx_ref parameter"}, status=400)

        verify_url = f"{CHAPA_BASE_URL}/transaction/verify/{tx_ref}"
        headers = {"Authorization": f"Bearer {CHAPA_API_KEY}"}
        res = requests.get(verify_url, headers=headers)
        data = res.json()
        print("Chapa Verification:", data)

        if data.get("status") == "success":
            d = data["data"]
            user = request.user if request.user.is_authenticated else None

            PaymentTransaction.objects.create(
                user=user,
                chapa_tx_ref=d.get("tx_ref"),
                chapa_transaction_id=d.get("transaction_id"),
                amount=d.get("amount"),
                currency='ETB',
                email=d.get("email"),
                phone_number=d.get("phone_number", ""),
                status='success',
                reason=''
            )
            # If you have an Order model and want to update its status to 'paid'
            order_id = d.get("custom_data", {}).get("order_id") if d.get("custom_data") else None
            if order_id:
              # Adjust import if needed
                try:
                    order = Order.objects.get(id=order_id)
                    order.status = 'paid'
                    order.save()  # <-- ADD THIS LINE
                except Order.DoesNotExist:
                    print("Order not found")
            return Response({"message": "Payment successful"}, status=200)

        return Response({"message": "Payment verification failed"}, status=400)

        """
        examole
        """