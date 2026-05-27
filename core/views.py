import base64
import hashlib
import hmac as _hmac
import json
import logging
import os
import threading
import uuid
from functools import wraps
from io import BytesIO

logger = logging.getLogger(__name__)

import requests as http_req
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth.views import PasswordResetView
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


class AsyncPasswordResetView(PasswordResetView):
    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        args = (subject_template_name, email_template_name, context,
                from_email, to_email, html_email_template_name)
        threading.Thread(
            target=super().send_mail, args=args, daemon=True
        ).start()

from .services import mercadopago as mp

from .models import Category, Order, OrderItem, PendingOrder, Product, User, Wishlist

# ── Taxas Mercado Pago por número de parcelas ──────────────────────────────────
MP_FEE_RATES = {
    1: 0.0499, 2: 0.0699, 3: 0.0699, 4: 0.0899,
    5: 0.0899, 6: 0.0899, 7: 0.0999, 8: 0.0999,
    9: 0.0999, 10: 0.0999, 11: 0.0999, 12: 0.0999,
}


def _verify_mp_signature(request, payment_id):
    """Verifica assinatura HMAC do webhook do Mercado Pago."""
    secret = getattr(django_settings, 'MERCADOPAGO_WEBHOOK_SECRET', '')
    if not secret:
        return True  # se não configurado, aceita (log de aviso)
    x_signature = request.headers.get('x-signature', '')
    x_request_id = request.headers.get('x-request-id', '')
    ts = v1 = ''
    for part in x_signature.split(','):
        k, _, val = part.partition('=')
        if k.strip() == 'ts':
            ts = val.strip()
        elif k.strip() == 'v1':
            v1 = val.strip()
    if not ts or not v1:
        return False
    manifest = f"id:{payment_id};request-id:{x_request_id};ts:{ts};"
    expected = _hmac.new(secret.encode('utf-8'), manifest.encode('utf-8'), hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, v1)


# ── Helpers ────────────────────────────────────────────────────────────────────

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin:
            return render(request, 'errors/403.html', status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


def get_cart(request):
    return request.session.get('cart', [])


def cart_total(request):
    return sum(i['price'] * i['qty'] for i in get_cart(request))


def cart_dimensions(request):
    """Retorna (peso_g, comprimento, largura, altura) considerando todos os itens do carrinho."""
    weight = 0
    max_l = max_w = max_h = 0
    for item in get_cart(request):
        try:
            p = Product.objects.get(pk=item['product_id'])
            weight += p.weight_grams * item['qty']
            max_l = max(max_l, p.length_cm)
            max_w = max(max_w, p.width_cm)
            max_h = max(max_h, p.height_cm * item['qty'])
        except Product.DoesNotExist:
            pass
    return weight or 300, max_l or 28, max_w or 19, max_h or 5


def cart_weight(request):
    return cart_dimensions(request)[0]


def calculate_freight(cep, weight_grams, length_cm=28, width_cm=19, height_cm=5):
    from .services import correios as correios_svc
    try:
        return correios_svc.calcular(cep, weight_grams, length_cm, width_cm, height_cm)
    except Exception:
        # Fallback à tabela simplificada se a API dos Correios estiver fora
        weight_grams = max(weight_grams, 300)
        extra = max(0, (weight_grams - 300) / 100)
        pac   = round(min(15.0 + extra * 2.0, 85.0), 2)
        sedex = round(min(25.0 + extra * 3.5, 130.0), 2)
        return {
            'pac':   {'price': pac,   'days': '8 a 12 dias úteis'},
            'sedex': {'price': sedex, 'days': '1 a 3 dias úteis'},
        }


def slugify_br(text):
    replacements = {
        'ç': 'c', 'ã': 'a', 'â': 'a', 'á': 'a', 'à': 'a',
        'ê': 'e', 'é': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o',
        'ú': 'u', 'ü': 'u', 'ñ': 'n', ' ': '-',
    }
    t = text.lower()
    for k, v in replacements.items():
        t = t.replace(k, v)
    return ''.join(c for c in t if c.isalnum() or c == '-')


def generate_pix_payload(amount, order_number):
    def tlv(tag, value):
        return f"{tag:02d}{len(value):02d}{value}"

    key = django_settings.PIX_KEY
    name = django_settings.PIX_NAME[:25]
    city = django_settings.PIX_CITY[:15]

    merchant_account = tlv(0, "BR.GOV.BCB.PIX") + tlv(1, key)
    txid = tlv(5, order_number[:25])
    additional = tlv(62, txid)
    payload = (
        tlv(0, "01") + tlv(26, merchant_account) + tlv(52, "0000") +
        tlv(53, "986") + tlv(54, f"{amount:.2f}") + tlv(58, "BR") +
        tlv(59, name) + tlv(60, city) + additional + "6304"
    )
    crc = 0xFFFF
    for byte in payload.encode('utf-8'):
        crc ^= byte << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
        crc &= 0xFFFF
    return payload + f"{crc:04X}"


def generate_pix_qr(amount, order_number):
    import qrcode
    payload = generate_pix_payload(amount, order_number)
    qr = qrcode.QRCode(version=1, box_size=8, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1A1A1A", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode(), payload


# ── Auth ───────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)
            messages.success(request, 'Bem-vinda de volta! 💕')
            return redirect(request.GET.get('next') or 'index')
        messages.error(request, 'E-mail ou senha incorretos.')
    return render(request, 'login.html')


def cadastro_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')

        errors = []
        if len(name) < 2:
            errors.append('Nome muito curto.')
        if len(password) < 8:
            errors.append('Senha deve ter pelo menos 8 caracteres.')
        if password != confirm:
            errors.append('As senhas não coincidem.')
        if User.objects.filter(email=email).exists():
            errors.append('Este e-mail já está cadastrado.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'cadastro.html')

        user = User.objects.create_user(email=email, name=name, phone=phone, password=password)
        login(request, user)
        messages.success(request, 'Conta criada! Seja bem-vinda à Maravilinda 🌸')
        return redirect('index')
    return render(request, 'cadastro.html')


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'Até logo! 👋')
    return redirect('index')


# ── Loja ───────────────────────────────────────────────────────────────────────

def index_view(request):
    featured = Product.objects.filter(is_featured=True, is_active=True)[:8]
    dois_dias_atras = timezone.now() - timezone.timedelta(days=2)
    recent = Product.objects.filter(is_active=True, created_at__gte=dois_dias_atras).order_by('-created_at')[:8]
    all_products = list(Product.objects.filter(is_active=True).order_by('-created_at'))
    return render(request, 'index.html', {
        'featured': featured,
        'recent': recent,
        'all_products': all_products,
    })


def produtos_view(request):
    cat_slug = request.GET.get('categoria', '')
    search = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)

    qs = Product.objects.filter(is_active=True)
    cat = None
    if cat_slug:
        cat = get_object_or_404(Category, slug=cat_slug)
        qs = qs.filter(category=cat)
    if search:
        qs = qs.filter(name__icontains=search)
    qs = qs.order_by('-created_at')

    paginator = Paginator(qs, 12)
    products = paginator.get_page(page_num)
    return render(request, 'produtos.html', {
        'products': products,
        'current_cat': cat,
        'search': search,
        'cat_slug': cat_slug,
    })


def produto_view(request, pid):
    product = get_object_or_404(Product, pk=pid, is_active=True)
    related = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(pk=pid)[:4]
    return render(request, 'produto.html', {'product': product, 'related': related})


# ── Carrinho API ───────────────────────────────────────────────────────────────

def api_cart(request):
    cart = get_cart(request)
    return JsonResponse({
        'cart': cart,
        'total': cart_total(request),
        'count': sum(i['qty'] for i in cart),
    })


@require_POST
def api_cart_add(request):
    data = json.loads(request.body)
    try:
        p = Product.objects.get(pk=data.get('product_id'), is_active=True)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Produto não encontrado'}, status=404)

    cart = get_cart(request)
    key = f"{p.id}|{data.get('color', '')}|{data.get('size', '')}"
    qty = int(data.get('qty', 1))

    for item in cart:
        if item.get('key') == key:
            item['qty'] += qty
            request.session['cart'] = cart
            request.session.modified = True
            return JsonResponse({'success': True, 'count': sum(i['qty'] for i in cart)})

    cart.append({
        'key': key,
        'product_id': p.id,
        'name': p.name,
        'price': p.price,
        'image': p.first_image,
        'color': data.get('color', ''),
        'size': data.get('size', ''),
        'qty': qty,
    })
    request.session['cart'] = cart
    request.session.modified = True
    return JsonResponse({'success': True, 'count': sum(i['qty'] for i in cart)})


@require_POST
def api_cart_update(request):
    data = json.loads(request.body)
    key = data.get('key')
    qty = int(data.get('qty', 1))
    cart = get_cart(request)
    for item in cart:
        if item.get('key') == key:
            if qty <= 0:
                cart.remove(item)
            else:
                item['qty'] = qty
            break
    request.session['cart'] = cart
    request.session.modified = True
    return JsonResponse({
        'success': True,
        'total': cart_total(request),
        'count': sum(i['qty'] for i in cart),
    })


@require_POST
def api_cart_remove(request):
    data = json.loads(request.body)
    cart = [i for i in get_cart(request) if i.get('key') != data.get('key')]
    request.session['cart'] = cart
    request.session.modified = True
    return JsonResponse({
        'success': True,
        'total': sum(i['price'] * i['qty'] for i in cart),
        'count': sum(i['qty'] for i in cart),
    })


@login_required
def carrinho_view(request):
    cart = get_cart(request)
    for item in cart:
        item['subtotal'] = item['price'] * item['qty']
    return render(request, 'carrinho.html', {'cart': cart, 'total': cart_total(request)})


# ── Frete API ──────────────────────────────────────────────────────────────────

@require_POST
def api_frete(request):
    data = json.loads(request.body)
    cep = ''.join(filter(str.isdigit, data.get('cep', '')))
    if len(cep) != 8:
        return JsonResponse({'error': 'CEP inválido'}, status=400)

    # Verifica se o CEP é de Parnaíba — frete grátis
    try:
        r = http_req.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
        cidade = r.json().get('localidade', '') if r.ok else ''
    except Exception:
        cidade = ''

    if 'parnaíba' in cidade.lower() or 'parnaiba' in cidade.lower():
        return JsonResponse({
            'pac':   {'price': 0, 'days': 'Entrega local — grátis'},
            'sedex': {'price': 0, 'days': 'Entrega local — grátis'},
        })

    weight, length, width, height = cart_dimensions(request)
    result = calculate_freight(cep, weight, length, width, height)
    return JsonResponse(result)


def api_cep(request, cep):
    cep = ''.join(filter(str.isdigit, cep))
    try:
        r = http_req.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
        if r.ok:
            d = r.json()
            if not d.get('erro'):
                return JsonResponse(d)
    except Exception:
        pass
    return JsonResponse({'error': 'CEP não encontrado'}, status=404)


# ── Checkout ───────────────────────────────────────────────────────────────────

@login_required
def checkout_view(request):
    cart = get_cart(request)
    if not cart:
        return redirect('carrinho')

    if request.method == 'POST':
        payment = request.POST.get('payment', 'pix')
        freight_type = request.POST.get('freight_type', 'PAC')
        freight_price = float(request.POST.get('freight_price', 0) or 0)
        subtotal = cart_total(request)

        tmp = Order()
        tmp.gen_number()
        num = tmp.order_number

        cep = request.POST.get('cep', '')
        street = request.POST.get('street', '')
        number = request.POST.get('number', '')
        complement = request.POST.get('complement', '')
        neighborhood = request.POST.get('neighborhood', '')
        city = request.POST.get('city', '')
        state = request.POST.get('state', '')

        # Salvar endereço e método no perfil do usuário
        u = request.user
        u.saved_cep = cep
        u.saved_street = street
        u.saved_number = number
        u.saved_complement = complement
        u.saved_neighborhood = neighborhood
        u.saved_city = city
        u.saved_state = state
        u.saved_payment_method = payment
        u.save(update_fields=[
            'saved_cep', 'saved_street', 'saved_number', 'saved_complement',
            'saved_neighborhood', 'saved_city', 'saved_state', 'saved_payment_method',
        ])

        # Calcula taxa MP para crédito
        mp_installments_val = int(request.POST.get('mp_installments', 1) or 1)
        mp_fee = 0.0
        if payment == 'credit':
            fee_rate = MP_FEE_RATES.get(mp_installments_val, 0.0499)
            mp_fee = round((subtotal + freight_price) * fee_rate, 2)
        total_final = round(subtotal + freight_price + mp_fee, 2)

        pending_data = {
            'user_id': request.user.id,
            'payment_method': payment,
            'subtotal': subtotal,
            'freight': freight_price,
            'mp_fee': mp_fee,
            'total': total_final,
            'freight_type': freight_type,
            'cep': cep,
            'street': street,
            'number': number,
            'complement': complement,
            'neighborhood': neighborhood,
            'city': city,
            'state': state,
            'external_provider': '',
            'external_id': '',
            'external_url': '',
            'items': [
                {
                    'product_id': item['product_id'],
                    'product_name': item['name'],
                    'color': item.get('color', ''),
                    'size': item.get('size', ''),
                    'quantity': item['qty'],
                    'unit_price': item['price'],
                }
                for item in cart
            ],
        }

        pending = PendingOrder.objects.create(order_number=num, data=pending_data)

        if payment in ('credit', 'debit'):
            mp_token = request.POST.get('mp_token', '')
            mp_method = request.POST.get('mp_payment_method_id', '')
            mp_issuer = request.POST.get('mp_issuer_id', '')

            if not mp_token or not mp_method:
                pending.delete()
                messages.error(request, 'Dados do cartão inválidos. Tente novamente.')
                return redirect('checkout')

            try:
                result = mp.create_card_payment(
                    _pending_as_order(pending), mp_token, mp_method, mp_installments_val, mp_issuer
                )
                pending.external_id = result['id']
                pending.data['external_provider'] = 'mercadopago'
                pending.data['external_id'] = result['id']
                pending.save()

                if result['status'] == 'approved':
                    order = _create_order_from_pending(pending)
                    _mark_order_paid(order)
                    request.session['cart'] = []
                    request.session.modified = True
                elif result['status'] in ('in_process', 'pending', 'authorized'):
                    order = _create_order_from_pending(pending)
                    # Limpa carrinho mesmo para pagamentos em análise
                    request.session['cart'] = []
                    request.session.modified = True
                else:
                    pending.delete()
                    messages.error(request, 'Pagamento recusado. Verifique os dados do cartão e tente novamente.')
                    return redirect('checkout')

                return redirect('order_success', num=num)

            except mp.MercadoPagoError as e:
                pending.delete()
                messages.error(request, f'Erro ao processar pagamento: {e}')
                return redirect('checkout')

        return redirect('pix_payment', num=num)

    for item in cart:
        item['subtotal'] = item['price'] * item['qty']
    u = request.user
    return render(request, 'checkout.html', {
        'cart': cart,
        'total': cart_total(request),
        'saved': {
            'cep': u.saved_cep,
            'street': u.saved_street,
            'number': u.saved_number,
            'complement': u.saved_complement,
            'neighborhood': u.saved_neighborhood,
            'city': u.saved_city,
            'state': u.saved_state,
            'payment_method': u.saved_payment_method,
        },
    })


@login_required
def pix_payment_view(request, num):
    pending = get_object_or_404(PendingOrder, order_number=num)
    if pending.data.get('user_id') != request.user.id:
        return redirect('index')

    auto_confirm = False
    qr_img = None
    pix_code = None

    use_mp = bool(getattr(django_settings, 'MERCADOPAGO_ACCESS_TOKEN', ''))
    if use_mp:
        try:
            if not pending.external_id:
                # Primeira vez — cria PIX e salva QR no pending para reusar
                pix = mp.create_pix(_pending_as_order(pending))
                if pix.get('qr_code'):
                    pending.external_id = pix['id'] or ''
                    pending.data['external_provider'] = 'mercadopago'
                    pending.data['external_id'] = pix['id'] or ''
                    pending.data['pix_qr_code'] = pix['qr_code']
                    pending.data['pix_qr_base64'] = pix['qr_code_base64']
                    pending.save()
                    pix_code = pix['qr_code']
                    qr_img = pix['qr_code_base64']
                    auto_confirm = True
            else:
                # Reload da página — reutiliza QR já criado (sem nova cobrança)
                pix_code = pending.data.get('pix_qr_code', '')
                qr_img = pending.data.get('pix_qr_base64', '')
                if pix_code:
                    auto_confirm = True
        except Exception as e:
            logger.warning(f'Falha ao gerar PIX MP: {e}. Usando QR estático.')

    if not pix_code:
        qr_img, pix_code = generate_pix_qr(pending.total, pending.order_number)

    return render(request, 'pix_payment.html', {
        'order': pending,
        'qr_img': qr_img,
        'pix_code': pix_code,
        'auto_confirm': auto_confirm,
    })


@login_required
@require_GET
def pix_status_view(request, num):
    """Endpoint JSON para o frontend fazer polling enquanto o cliente paga."""
    try:
        order = Order.objects.get(order_number=num, user=request.user)
        if order.payment_status == 'pago':
            request.session['cart'] = []
            request.session.modified = True
            return JsonResponse({'status': 'pago'})
        return JsonResponse({'status': order.payment_status})
    except Order.DoesNotExist:
        pass

    pending = get_object_or_404(PendingOrder, order_number=num)
    if pending.data.get('user_id') != request.user.id:
        return JsonResponse({'status': 'pendente'})

    if pending.external_id:
        try:
            status = mp.check_status(pending.external_id)
            if status == 'PAID':
                order = _create_order_from_pending(pending)
                _mark_order_paid(order)
                request.session['cart'] = []
                request.session.modified = True
                return JsonResponse({'status': 'pago'})
        except mp.MercadoPagoError:
            pass
    return JsonResponse({'status': 'pendente'})


def _pending_as_order(pending):
    """Devolve um objeto Order não salvo com os dados do PendingOrder (para APIs que precisam do objeto)."""
    d = pending.data
    o = Order()
    o.order_number = pending.order_number
    o.user_id = d['user_id']
    o.payment_method = d['payment_method']
    o.subtotal = d['subtotal']
    o.freight = d['freight']
    o.total = d['total']
    o.freight_type = d['freight_type']
    o.cep = d['cep']
    o.street = d['street']
    o.number = d['number']
    o.complement = d['complement']
    o.neighborhood = d['neighborhood']
    o.city = d['city']
    o.state = d['state']
    return o


def _create_order_from_pending(pending):
    d = pending.data
    order = Order()
    order.order_number = pending.order_number
    order.user_id = d['user_id']
    order.payment_method = d['payment_method']
    order.subtotal = d['subtotal']
    order.freight = d['freight']
    order.total = d['total']
    order.freight_type = d['freight_type']
    order.cep = d['cep']
    order.street = d['street']
    order.number = d['number']
    order.complement = d['complement']
    order.neighborhood = d['neighborhood']
    order.city = d['city']
    order.state = d['state']
    order.external_provider = d.get('external_provider', '')
    order.external_id = pending.external_id or d.get('external_id', '')
    order.external_url = d.get('external_url', '')
    order.save()
    for item in d['items']:
        OrderItem.objects.create(
            order=order,
            product_id=item['product_id'],
            product_name=item['product_name'],
            color=item.get('color', ''),
            size=item.get('size', ''),
            quantity=item['quantity'],
            unit_price=item['unit_price'],
        )
    pending.delete()
    return order


def _mark_order_paid(order):
    if order.payment_status == 'pago':
        return
    order.payment_status = 'pago'
    order.status = 'confirmado'
    order.paid_at = timezone.now()
    order.save(update_fields=['payment_status', 'status', 'paid_at'])
    for item in order.items.all():
        if not item.product_id:
            continue
        try:
            p = Product.objects.get(pk=item.product_id)
            if p.stock > 0:
                p.stock = max(0, p.stock - item.quantity)
                p.save(update_fields=['stock'])
        except Product.DoesNotExist:
            pass


@csrf_exempt
@require_POST
def mercadopago_webhook_view(request):
    """
    Recebe notificações do Mercado Pago.
    Configure a URL no painel do MP: {SITE_URL}/webhook/mercadopago/
    Tipo de evento: pagamento (payment)
    """
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid json'}, status=400)

    # MP envia type="payment" e data.id com o ID do pagamento
    if payload.get('type') != 'payment':
        return JsonResponse({'ok': True})

    payment_id = str((payload.get('data') or {}).get('id', ''))
    if not payment_id:
        return JsonResponse({'ok': True})

    # Verificação de assinatura HMAC
    if not _verify_mp_signature(request, payment_id):
        logger.warning(f'Webhook MP com assinatura inválida para payment_id={payment_id}')
        return JsonResponse({'error': 'invalid signature'}, status=400)

    try:
        status = mp.check_status(payment_id)
    except mp.MercadoPagoError:
        return JsonResponse({'ok': True})

    if status != 'PAID':
        return JsonResponse({'ok': True})

    # Tenta encontrar pedido já criado
    try:
        order = Order.objects.get(external_id=payment_id)
        _mark_order_paid(order)
        return JsonResponse({'ok': True})
    except Order.DoesNotExist:
        pass

    # Tenta encontrar pedido pendente pelo external_id
    try:
        pending = PendingOrder.objects.get(external_id=payment_id)
        order = _create_order_from_pending(pending)
        _mark_order_paid(order)
    except PendingOrder.DoesNotExist:
        pass

    return JsonResponse({'ok': True})


@login_required
def order_success_view(request, num):
    try:
        order = Order.objects.get(order_number=num, user=request.user)
    except Order.DoesNotExist:
        # Cartão: webhook pode ainda não ter chegado — tenta criar a partir do pending
        try:
            pending = PendingOrder.objects.get(order_number=num)
            if pending.data.get('user_id') == request.user.id and pending.external_id:
                ext_status = mp.check_status(pending.external_id)
                if ext_status == 'PAID':
                    order = _create_order_from_pending(pending)
                    _mark_order_paid(order)
                else:
                    return render(request, 'order_success.html', {
                        'order': None, 'first_name': request.user.name.split()[0] if request.user.name else '',
                        'aguardando': True,
                    })
            else:
                return redirect('index')
        except (PendingOrder.DoesNotExist, mp.MercadoPagoError):
            return redirect('index')

    if order.payment_status == 'pago':
        request.session['cart'] = []
        request.session.modified = True

    first_name = request.user.name.split()[0] if request.user.name else request.user.name
    return render(request, 'order_success.html', {'order': order, 'first_name': first_name})


@login_required
def minha_conta_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'minha_conta.html', {'orders': orders})


@login_required
def favoritos_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related('product').order_by('-created_at')
    return render(request, 'favoritos.html', {'items': items})


@login_required
@require_POST
def api_wishlist_toggle(request):
    pid = request.POST.get('product_id')
    product = get_object_or_404(Product, pk=pid)
    obj, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        obj.delete()
    return JsonResponse({'saved': created})


@login_required
@require_GET
def api_wishlist_ids(request):
    ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
    return JsonResponse({'ids': ids})


# ── Admin ──────────────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_dashboard_view(request):
    total_orders = Order.objects.count()
    total_revenue = Order.objects.filter(payment_status='pago').aggregate(
        s=Sum('total')
    )['s'] or 0
    total_products = Product.objects.filter(is_active=True).count()
    total_users = User.objects.filter(is_admin=False).count()
    recent_orders = Order.objects.order_by('-created_at').select_related('user')[:10]
    low_stock = Product.objects.filter(stock__lte=5, is_active=True).select_related('category')
    return render(request, 'admin/dashboard.html', {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_products': total_products,
        'total_users': total_users,
        'recent_orders': recent_orders,
        'low_stock': low_stock,
    })


@login_required
@admin_required
def admin_produtos_view(request):
    products = Product.objects.order_by('-created_at').select_related('category')
    return render(request, 'admin/produtos.html', {'products': products})


@login_required
@admin_required
def admin_produto_form_view(request, pid=None):
    product = get_object_or_404(Product, pk=pid) if pid else None
    categories = Category.objects.all()

    if request.method == 'POST':
        if not product:
            product = Product()

        product.name = request.POST.get('name', '')
        product.description = request.POST.get('description', '')
        product.price = float(request.POST.get('price', 0) or 0)
        product.weight_grams = int(request.POST.get('weight_grams', 300) or 300)
        product.length_cm = int(request.POST.get('length_cm', 28) or 28)
        product.width_cm  = int(request.POST.get('width_cm',  19) or 19)
        product.height_cm = int(request.POST.get('height_cm',  5) or 5)
        cat_id = request.POST.get('category_id')
        product.category_id = int(cat_id) if cat_id else None
        product.stock = int(request.POST.get('stock', 0) or 0)
        product.is_featured = request.POST.get('is_featured') == 'on'
        product.is_active = request.POST.get('is_active', 'on') == 'on'

        colors = [c.strip() for c in request.POST.get('colors', '').split(',') if c.strip()]
        sizes = [s.strip() for s in request.POST.get('sizes', '').split(',') if s.strip()]
        product.colors = json.dumps(colors)
        product.sizes = json.dumps(sizes if sizes else ['P', 'M', 'G', 'GG'])

        existing = request.POST.getlist('existing_images')
        images = existing if pid else []

        upload_folder = os.path.join(django_settings.BASE_DIR, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        for f in request.FILES.getlist('images'):
            if f and f.name:
                if f.size > django_settings.MAX_UPLOAD_SIZE:
                    messages.error(request, f'Arquivo "{f.name}" muito grande. Máximo 16MB.')
                    continue
                ext = f.name.rsplit('.', 1)[-1].lower()
                if ext in ('jpg', 'jpeg', 'png', 'webp'):
                    fname = f"{uuid.uuid4().hex}.{ext}"
                    with open(os.path.join(upload_folder, fname), 'wb+') as dest:
                        for chunk in f.chunks():
                            dest.write(chunk)
                    images.append(f'/static/uploads/{fname}')
        product.images = json.dumps(images)
        product.save()
        messages.success(request, 'Produto salvo com sucesso! ✓')
        return redirect('admin_produtos')

    return render(request, 'admin/produto_form.html', {
        'product': product,
        'categories': categories,
    })


@login_required
@admin_required
def admin_produto_delete_view(request, pid):
    if request.method == 'POST':
        p = get_object_or_404(Product, pk=pid)
        OrderItem.objects.filter(product=p).update(product=None)
        p.delete()
        messages.info(request, 'Produto removido com sucesso.')
    return redirect('admin_produtos')


@login_required
@admin_required
def admin_pedidos_view(request):
    status_filter = request.GET.get('status', '')
    qs = Order.objects.order_by('-created_at').select_related('user')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'admin/pedidos.html', {
        'orders': qs,
        'current_status': status_filter,
    })


@login_required
@admin_required
def admin_pedido_detail_view(request, oid):
    order = get_object_or_404(Order, pk=oid)
    return render(request, 'admin/pedido_detail.html', {'order': order})


@login_required
@admin_required
def admin_update_order_view(request, oid):
    if request.method == 'POST':
        order = get_object_or_404(Order, pk=oid)
        order.status = request.POST.get('status', order.status)
        order.payment_status = request.POST.get('payment_status', order.payment_status)
        order.save()
        messages.success(request, 'Pedido atualizado!')
    return redirect('admin_pedidos')


@login_required
@admin_required
def admin_repor_estoque_view(request, pid):
    if request.method == 'POST':
        p = get_object_or_404(Product, pk=pid)
        qty = int(request.POST.get('qty', 0) or 0)
        if qty > 0:
            p.stock += qty
            p.save()
            messages.success(request, f'+{qty} unidades adicionadas ao estoque de "{p.name}".')
    return redirect('admin_produtos')


@login_required
@admin_required
def admin_categorias_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            slug = slugify_br(name)
            if not Category.objects.filter(slug=slug).exists():
                Category.objects.create(name=name, slug=slug)
                messages.success(request, 'Categoria adicionada!')
            else:
                messages.error(request, 'Categoria já existe.')
    cats = Category.objects.all()
    return render(request, 'admin/categorias.html', {'categories': cats})


@login_required
@admin_required
def admin_categoria_delete_view(request, cid):
    if request.method == 'POST':
        cat = get_object_or_404(Category, pk=cid)
        cat.delete()
        messages.info(request, 'Categoria removida.')
    return redirect('admin_categorias')


@login_required
@admin_required
def admin_usuarios_view(request):
    users = User.objects.order_by('-created_at')
    return render(request, 'admin/usuarios.html', {'users': users})


@login_required
@admin_required
def admin_usuario_delete_view(request, uid):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=uid)
        if not user.is_admin:
            user.delete()
            messages.success(request, 'Cliente excluído com sucesso.')
    return redirect('admin_usuarios')


# ── Error handlers ─────────────────────────────────────────────────────────────

def handler403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def handler404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def handler500(request):
    return render(request, 'errors/500.html', status=500)
