"""
Cliente AbacatePay — PIX e Cartão.

Docs: https://docs.abacatepay.com

Fluxos:
  - PIX inline (QR Code no nosso site): create_pix_qrcode() + check_pix_status()
  - Cartão (checkout hospedado AbacatePay): create_billing() retorna URL pra redirect
  - Confirmação automática: webhook POST em /webhook/abacatepay/
"""
import requests
from django.conf import settings

BASE_URL = getattr(settings, 'ABACATEPAY_BASE_URL', 'https://api.abacatepay.com')
TIMEOUT = 20


class AbacatePayError(Exception):
    pass


def _headers():
    key = getattr(settings, 'ABACATEPAY_API_KEY', '')
    if not key:
        raise AbacatePayError('ABACATEPAY_API_KEY não configurada em settings.')
    return {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def _post(path, payload):
    r = requests.post(f'{BASE_URL}{path}', json=payload, headers=_headers(), timeout=TIMEOUT)
    if not r.ok:
        raise AbacatePayError(f'AbacatePay {r.status_code}: {r.text}')
    return r.json()


def _get(path, params=None):
    r = requests.get(f'{BASE_URL}{path}', params=params, headers=_headers(), timeout=TIMEOUT)
    if not r.ok:
        raise AbacatePayError(f'AbacatePay {r.status_code}: {r.text}')
    return r.json()


def _amount_cents(value):
    return int(round(float(value) * 100))


def _customer_payload(order):
    user = order.user
    name = (user.name if user else '') or 'Cliente'
    email = (user.email if user else '') or 'cliente@exemplo.com'
    phone = ''.join(filter(str.isdigit, (user.phone if user else '') or ''))
    return {
        'name': name,
        'email': email,
        'cellphone': phone or '11999999999',
        'taxId': '00000000000',
    }


def create_pix_qrcode(order, expires_in_seconds=1800):
    """Cria cobrança PIX dinâmica. Retorna dict com id, brCode, brCodeBase64."""
    payload = {
        'amount': _amount_cents(order.total),
        'expiresIn': expires_in_seconds,
        'description': f'Pedido {order.order_number} - Maravilinda',
        'customer': _customer_payload(order),
        'externalId': order.order_number,
    }
    resp = _post('/v1/pixQrCode/create', payload)
    data = resp.get('data') or resp
    return {
        'id': data.get('id'),
        'br_code': data.get('brCode'),
        'br_code_base64': data.get('brCodeBase64'),
        'status': data.get('status'),
        'expires_at': data.get('expiresAt'),
    }


def check_pix_status(pix_id):
    """Consulta status de um PIX. Retorna status string (PAID, PENDING, EXPIRED...)."""
    resp = _get('/v1/pixQrCode/check', params={'id': pix_id})
    data = resp.get('data') or resp
    return (data.get('status') or '').upper()


def create_billing(order, return_url, completion_url, methods=None):
    """
    Cria cobrança via checkout hospedado (suporta CREDIT_CARD).
    Retorna dict com id e url (redirecionar usuário pra essa URL).
    """
    methods = methods or ['CREDIT_CARD']
    products = []
    for item in order.items.all():
        products.append({
            'externalId': f'prod-{item.product_id or item.id}',
            'name': item.product_name[:120],
            'description': (f'{item.color or ""} {item.size or ""}').strip() or item.product_name[:120],
            'quantity': item.quantity,
            'price': _amount_cents(item.unit_price),
        })
    if order.freight and order.freight > 0:
        products.append({
            'externalId': 'frete',
            'name': f'Frete {order.freight_type or ""}'.strip(),
            'description': 'Envio',
            'quantity': 1,
            'price': _amount_cents(order.freight),
        })

    payload = {
        'frequency': 'ONE_TIME',
        'methods': methods,
        'products': products,
        'returnUrl': return_url,
        'completionUrl': completion_url,
        'customer': _customer_payload(order),
        'externalId': order.order_number,
    }
    resp = _post('/v1/billing/create', payload)
    data = resp.get('data') or resp
    return {
        'id': data.get('id'),
        'url': data.get('url'),
        'status': data.get('status'),
    }
