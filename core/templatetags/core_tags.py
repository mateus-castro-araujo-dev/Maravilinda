from django import template

register = template.Library()

COR_MAP = {
    'preto': '#1A1A1A', 'branco': '#FFFFFF', 'off-white': '#F5F0EB',
    'creme': '#FFF8DC', 'bege': '#D4B896', 'nude': '#C8956C',
    'areia': '#C2A882', 'caramelo': '#C47A2B', 'marrom': '#7B4F2E',
    'rosa': '#FFB6C1', 'rosa claro': '#FFD6E0', 'rosa escuro': '#C4637A',
    'rosa bebê': '#FFDDE1', 'pink': '#FF4FA3', 'magenta': '#D5006D',
    'vermelho': '#DC2626', 'vinho': '#7F1D1D', 'borgonha': '#800020',
    'coral': '#FF6B6B', 'salmão': '#FA8072', 'laranja': '#EA580C',
    'amarelo': '#EAB308', 'mostarda': '#B7791F', 'dourado': '#D4A017',
    'verde': '#16A34A', 'verde musgo': '#4A6741', 'verde militar': '#4B5320',
    'verde água': '#7FFFD4', 'menta': '#98D8C8', 'esmeralda': '#50C878',
    'azul': '#2563EB', 'azul claro': '#93C5FD', 'azul escuro': '#1E3A5F',
    'navy': '#001F5B', 'royal': '#4169E1', 'jeans': '#4A6FA5',
    'índigo': '#4F46E5', 'roxo': '#9333EA', 'lilás': '#C084FC',
    'lavanda': '#E6E6FA', 'violeta': '#7C3AED', 'ametista': '#9966CC',
    'cinza': '#9CA3AF', 'cinza claro': '#D1D5DB', 'cinza escuro': '#4B5563',
    'prata': '#C0C0C0', 'chumbo': '#36454F', 'terracota': '#C9684A',
    'turquesa': '#40E0D0', 'tiffany': '#81D8D0', 'petróleo': '#1B4F6A',
    'chocolate': '#7B3F00', 'ferrugem': '#8B4513', 'damasco': '#FBCEB1',
}


@register.filter
def cor_hex(nome):
    if not nome:
        return '#CCCCCC'
    n = str(nome).strip().lower()
    if n in COR_MAP:
        return COR_MAP[n]
    if nome.strip().startswith('#'):
        return nome.strip()
    return '#CCCCCC'


@register.filter
def brl(value):
    try:
        v = float(value)
        return f"{v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return value


@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def split(value, arg):
    return str(value).split(arg)
