"""
Cálculo de frete via Melhor Envio API (retorna PAC e SEDEX dos Correios).

Para usar:
  1. Crie conta gratuita em https://melhorenvio.com.br
  2. Vá em Tokens > Criar Token (permissão: shipping-calculate)
  3. Adicione em settings.py:
       MELHOR_ENVIO_TOKEN = 'seu_token_aqui'
       MELHOR_ENVIO_SANDBOX = False  # True para testes

Serviços: 1 = PAC, 2 = SEDEX
"""
import requests
from django.conf import settings

SANDBOX_URL    = 'https://sandbox.melhorenvio.com.br/api/v2/me/shipment/calculate'
PRODUCTION_URL = 'https://melhorenvio.com.br/api/v2/me/shipment/calculate'
TIMEOUT = 10

PAC_ID   = 1
SEDEX_ID = 2


def calcular(cep_destino, weight_grams, length_cm, width_cm, height_cm):
    """
    Retorna {'pac': {'price': float, 'days': str}, 'sedex': {...}}
    Lança Exception se não conseguir calcular.
    """
    token = getattr(settings, 'MELHOR_ENVIO_TOKEN', '')
    if not token:
        raise ValueError('MELHOR_ENVIO_TOKEN não configurado em settings.py')

    sandbox   = getattr(settings, 'MELHOR_ENVIO_SANDBOX', False)
    url       = SANDBOX_URL if sandbox else PRODUCTION_URL
    cep_orig  = getattr(settings, 'CORREIOS_CEP_ORIGEM', '01310100').replace('-', '')
    cep_dest  = cep_destino.replace('-', '')
    peso_kg   = max(weight_grams, 300) / 1000

    payload = {
        'from': {'postal_code': cep_orig},
        'to':   {'postal_code': cep_dest},
        'package': {
            'height': max(height_cm, 2),
            'width':  max(width_cm, 11),
            'length': max(length_cm, 16),
            'weight': round(peso_kg, 3),
        },
        'options': {'receipt': False, 'own_hand': False},
        'services': f'{PAC_ID},{SEDEX_ID}',
    }

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept':        'application/json',
        'Content-Type':  'application/json',
        'User-Agent':    'Maravilinda (contato@maravilinda.com.br)',
    }

    r = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()

    result = {}
    for item in data:
        sid  = item.get('id')
        erro = item.get('error')
        if erro:
            continue
        preco = float(item.get('price', 0) or 0)
        prazo = int(item.get('delivery_time', 0) or 0)
        if preco <= 0:
            continue
        if sid == PAC_ID:
            result['pac'] = {
                'price': preco,
                'days': f'{prazo} a {prazo + 2} dias úteis' if prazo else '8 a 12 dias úteis',
            }
        elif sid == SEDEX_ID:
            result['sedex'] = {
                'price': preco,
                'days': f'{prazo} a {prazo + 1} dias úteis' if prazo else '1 a 3 dias úteis',
            }

    if not result:
        raise ValueError('Melhor Envio não retornou valores válidos para este CEP.')

    return result
