from django.conf import settings
from .models import Category


def globals(request):
    cart = request.session.get('cart', [])
    return {
        'cart_count': sum(i['qty'] for i in cart),
        'all_categories': Category.objects.all(),
        'whatsapp_number': getattr(settings, 'WHATSAPP_NUMBER', ''),
        'instagram_user': getattr(settings, 'INSTAGRAM_USER', ''),
        'facebook_user': getattr(settings, 'FACEBOOK_USER', ''),
        'mp_public_key': getattr(settings, 'MERCADOPAGO_PUBLIC_KEY', ''),
    }
