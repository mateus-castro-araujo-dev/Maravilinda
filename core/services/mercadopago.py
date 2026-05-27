"""
Cliente Mercado Pago — PIX automático com confirmação via webhook.

Fluxo:
  1. checkout_view chama create_pix() → retorna QR Code para exibir na tela
  2. Frontend faz polling em pix_status_view → chama check_status()
  3. Mercado Pago chama POST /webhook/mercadopago/ quando o pagamento é confirmado
"""
import requests
from django.conf import settings

BASE_URL = 'https://api.mercadopago.com'
TIMEOUT = 20


class MercadoPagoError(Exception):
    pass


def _headers(idempotency_key=None):
    token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
    if not token:
        raise MercadoPagoError('MERCADOPAGO_ACCESS_TOKEN não configurado.')
    h = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    if idempotency_key:
        h['X-Idempotency-Key'] = idempotency_key
    return h


def create_pix(order):
    """
    Cria cobrança PIX. Retorna dict com id, qr_code (copia-e-cola) e qr_code_base64.
    """
    user = order.user
    email = (user.email if user else '') or 'cliente@maravilinda.com.br'
    name = (user.name if user else '') or 'Cliente'

    headers = _headers(idempotency_key=order.order_number)

    payload = {
        'transaction_amount': round(float(order.total), 2),
        'description': f'Pedido {order.order_number} - Maravilinda',
        'payment_method_id': 'pix',
        'payer': {
            'email': email,
            'first_name': name.split()[0],
            'last_name': ' '.join(name.split()[1:]) or name.split()[0],
        },
        'external_reference': order.order_number,
    }

    r = requests.post(f'{BASE_URL}/v1/payments', json=payload, headers=headers, timeout=TIMEOUT)
    if not r.ok:
        raise MercadoPagoError(f'Mercado Pago {r.status_code}: {r.text}')

    data = r.json()
    tx = (data.get('point_of_interaction') or {}).get('transaction_data') or {}
    return {
        'id': str(data.get('id', '')),
        'qr_code': tx.get('qr_code', ''),
        'qr_code_base64': tx.get('qr_code_base64', ''),
        'status': data.get('status', ''),
    }


def create_card_payment(order, token, payment_method_id, installments=1, issuer_id=None):
    """
    Cria pagamento com cartão de crédito ou débito.
    Retorna dict com id, status ('approved'|'in_process'|'rejected') e status_detail.
    """
    user = order.user
    email = (user.email if user else '') or 'cliente@maravilinda.com.br'

    headers = _headers(idempotency_key=f'{order.order_number}-card')

    payload = {
        'transaction_amount': round(float(order.total), 2),
        'token': token,
        'description': f'Pedido {order.order_number} - Maravilinda',
        'installments': int(installments or 1),
        'payment_method_id': payment_method_id,
        'payer': {'email': email},
        'external_reference': order.order_number,
    }
    if issuer_id:
        payload['issuer_id'] = int(issuer_id)

    r = requests.post(f'{BASE_URL}/v1/payments', json=payload, headers=headers, timeout=TIMEOUT)
    if not r.ok:
        raise MercadoPagoError(f'Mercado Pago {r.status_code}: {r.text}')

    data = r.json()
    return {
        'id': str(data.get('id', '')),
        'status': data.get('status', ''),
        'status_detail': data.get('status_detail', ''),
    }


def check_status(payment_id):
    """
    Consulta status de um pagamento. Retorna 'PAID', 'PENDING' ou 'REJECTED'.
    """
    r = requests.get(f'{BASE_URL}/v1/payments/{payment_id}', headers=_headers(None), timeout=TIMEOUT)
    if not r.ok:
        raise MercadoPagoError(f'Mercado Pago {r.status_code}: {r.text}')
    status = r.json().get('status', '').lower()
    if status == 'approved':
        return 'PAID'
    if status in ('rejected', 'cancelled'):
        return 'REJECTED'
    return 'PENDING'
