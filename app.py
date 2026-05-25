import os
import uuid
import json
import base64
import secrets
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash, abort)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import func
import requests as http_req

app = Flask(__name__)

# ── Configuração de Segurança ─────────────────────────────────────────────────
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', secrets.token_hex(32)),
    SQLALCHEMY_DATABASE_URI='sqlite:///maravilinda.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    UPLOAD_FOLDER=os.path.join('static', 'uploads'),
    # ── Configurar aqui ──
    WHATSAPP_NUMBER='5511999999999',
    PIX_KEY='pix@maravilinda.com.br',
    PIX_NAME='Maravilinda Moda',
    PIX_CITY='Sao Paulo',
)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para continuar.'
login_manager.login_message_category = 'info'
limiter = Limiter(get_remote_address, app=app,
                  default_limits=["300 per day", "60 per hour"],
                  storage_uri="memory://")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ── Mapa de cores em português ─────────────────────────────────────────────────
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

def cor_para_hex(nome):
    """Converte nome de cor em português para hex. Retorna a string original se não encontrar."""
    if not nome:
        return '#CCCCCC'
    n = nome.strip().lower()
    return COR_MAP.get(n, nome if nome.startswith('#') else '#CCCCCC')

@app.template_filter('cor_hex')
def cor_hex_filter(nome):
    return cor_para_hex(nome)

# ── Models ─────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    weight_grams = db.Column(db.Integer, default=300)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    images = db.Column(db.Text, default='[]')
    colors = db.Column(db.Text, default='[]')
    sizes = db.Column(db.Text, default='["P","M","G","GG"]')
    stock = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def images_list(self):
        return json.loads(self.images or '[]')

    @property
    def colors_list(self):
        return json.loads(self.colors or '[]')

    @property
    def sizes_list(self):
        return json.loads(self.sizes or '["P","M","G","GG"]')

    @property
    def first_image(self):
        imgs = self.images_list
        return imgs[0] if imgs else '/static/img/placeholder.svg'

    def fmt_price(self):
        return f"R$ {self.price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(30), default='aguardando')
    payment_method = db.Column(db.String(20))
    payment_status = db.Column(db.String(20), default='pendente')
    subtotal = db.Column(db.Float, default=0)
    freight = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    freight_type = db.Column(db.String(10))
    cep = db.Column(db.String(10))
    street = db.Column(db.String(150))
    number = db.Column(db.String(20))
    complement = db.Column(db.String(100))
    neighborhood = db.Column(db.String(100))
    city = db.Column(db.String(100))
    state = db.Column(db.String(2))
    items = db.relationship('OrderItem', backref='order', lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def gen_number(self):
        self.order_number = f"MLV{datetime.now().strftime('%y%m%d')}{secrets.token_hex(3).upper()}"

    def fmt_total(self):
        return f"R$ {self.total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='SET NULL'), nullable=True)
    product_name = db.Column(db.String(150))
    color = db.Column(db.String(50))
    size = db.Column(db.String(10))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float)
    product = db.relationship('Product')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Helpers ────────────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def get_cart():
    return session.get('cart', [])


def cart_total():
    return sum(i['price'] * i['qty'] for i in get_cart())


def cart_weight():
    total = 0
    for item in get_cart():
        p = db.session.get(Product, item['product_id'])
        if p:
            total += p.weight_grams * item['qty']
    return total or 300


def slugify(text):
    replacements = {'ç': 'c', 'ã': 'a', 'â': 'a', 'á': 'a', 'à': 'a',
                    'ê': 'e', 'é': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o',
                    'ú': 'u', 'ü': 'u', 'ñ': 'n', ' ': '-'}
    t = text.lower()
    for k, v in replacements.items():
        t = t.replace(k, v)
    return ''.join(c for c in t if c.isalnum() or c == '-')


def calculate_freight(cep, weight_grams):
    weight_grams = max(weight_grams, 300)
    extra = max(0, (weight_grams - 300) / 100)
    pac = round(15.0 + extra * 2.0, 2)
    sedex = round(25.0 + extra * 3.5, 2)
    pac = min(pac, 85.0)
    sedex = min(sedex, 130.0)
    return {
        'pac': {'price': pac, 'days': '8 a 12 dias úteis'},
        'sedex': {'price': sedex, 'days': '1 a 3 dias úteis'}
    }


def generate_pix_payload(amount, order_number):
    def tlv(tag, value):
        return f"{tag:02d}{len(value):02d}{value}"

    key = app.config['PIX_KEY']
    name = app.config['PIX_NAME'][:25]
    city = app.config['PIX_CITY'][:15]

    merchant_account = tlv(0, "BR.GOV.BCB.PIX") + tlv(1, key)
    txid = tlv(5, order_number[:25])
    additional = tlv(62, txid)

    payload = (
        tlv(0, "01") +
        tlv(26, merchant_account) +
        tlv(52, "0000") +
        tlv(53, "986") +
        tlv(54, f"{amount:.2f}") +
        tlv(58, "BR") +
        tlv(59, name) +
        tlv(60, city) +
        additional +
        "6304"
    )

    # CRC16-CCITT
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
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember') == 'on')
            flash('Bem-vinda de volta! 💕', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        flash('E-mail ou senha incorretos.', 'error')
    return render_template('login.html')


@app.route('/cadastro', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        errors = []
        if len(name) < 2:
            errors.append('Nome muito curto.')
        if len(password) < 8:
            errors.append('Senha deve ter pelo menos 8 caracteres.')
        if password != confirm:
            errors.append('As senhas não coincidem.')
        if User.query.filter_by(email=email).first():
            errors.append('Este e-mail já está cadastrado.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('cadastro.html')

        user = User(name=name, email=email, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash('Conta criada! Seja bem-vinda à Maravilinda 🌸', 'success')
        return redirect(url_for('index'))
    return render_template('cadastro.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Até logo! 👋', 'info')
    return redirect(url_for('index'))


# ── Loja ───────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    featured = Product.query.filter_by(is_featured=True, is_active=True).limit(8).all()
    recent = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all()
    all_products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
    return render_template('index.html', featured=featured, recent=recent, all_products=all_products)


@app.route('/produtos')
def produtos():
    cat_slug = request.args.get('categoria', '')
    search = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Product.query.filter_by(is_active=True)
    cat = None
    if cat_slug:
        cat = Category.query.filter_by(slug=cat_slug).first_or_404()
        query = query.filter_by(category_id=cat.id)
    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    products = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=12)
    return render_template('produtos.html', products=products, current_cat=cat, search=search)


@app.route('/produto/<int:pid>')
def produto(pid):
    product = Product.query.filter_by(id=pid, is_active=True).first_or_404()
    related = Product.query.filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.is_active == True
    ).limit(4).all()
    return render_template('produto.html', product=product, related=related)


# ── Carrinho API ───────────────────────────────────────────────────────────────
@app.route('/api/cart')
def api_cart():
    cart = get_cart()
    return jsonify({'cart': cart, 'total': cart_total(), 'count': sum(i['qty'] for i in cart)})


@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    data = request.get_json()
    p = db.session.get(Product, data.get('product_id'))
    if not p or not p.is_active:
        return jsonify({'error': 'Produto não encontrado'}), 404

    cart = get_cart()
    key = f"{p.id}|{data.get('color','')}|{data.get('size','')}"
    qty = int(data.get('qty', 1))

    for item in cart:
        if item.get('key') == key:
            item['qty'] += qty
            session['cart'] = cart
            return jsonify({'success': True, 'count': sum(i['qty'] for i in cart)})

    cart.append({
        'key': key, 'product_id': p.id, 'name': p.name,
        'price': p.price, 'image': p.first_image,
        'color': data.get('color', ''), 'size': data.get('size', ''), 'qty': qty
    })
    session['cart'] = cart
    return jsonify({'success': True, 'count': sum(i['qty'] for i in cart)})


@app.route('/api/cart/update', methods=['POST'])
def api_cart_update():
    data = request.get_json()
    key = data.get('key')
    qty = int(data.get('qty', 1))
    cart = get_cart()
    for item in cart:
        if item.get('key') == key:
            if qty <= 0:
                cart.remove(item)
            else:
                item['qty'] = qty
            break
    session['cart'] = cart
    return jsonify({'success': True, 'total': cart_total(), 'count': sum(i['qty'] for i in cart)})


@app.route('/api/cart/remove', methods=['POST'])
def api_cart_remove():
    data = request.get_json()
    cart = [i for i in get_cart() if i.get('key') != data.get('key')]
    session['cart'] = cart
    return jsonify({'success': True, 'total': cart_total(), 'count': sum(i['qty'] for i in cart)})


@app.route('/carrinho')
def carrinho():
    cart = get_cart()
    return render_template('carrinho.html', cart=cart, total=cart_total())


# ── Frete API ──────────────────────────────────────────────────────────────────
@app.route('/api/frete', methods=['POST'])
def api_frete():
    data = request.get_json()
    cep = ''.join(filter(str.isdigit, data.get('cep', '')))
    if len(cep) != 8:
        return jsonify({'error': 'CEP inválido'}), 400
    result = calculate_freight(cep, cart_weight())
    return jsonify(result)


@app.route('/api/cep/<cep>')
def api_cep(cep):
    cep = ''.join(filter(str.isdigit, cep))
    try:
        r = http_req.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
        if r.ok:
            d = r.json()
            if not d.get('erro'):
                return jsonify(d)
    except Exception:
        pass
    return jsonify({'error': 'CEP não encontrado'}), 404


# ── Checkout ───────────────────────────────────────────────────────────────────
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = get_cart()
    if not cart:
        return redirect(url_for('carrinho'))

    if request.method == 'POST':
        payment = request.form.get('payment', 'pix')
        freight_type = request.form.get('freight_type', 'PAC')
        freight_price = float(request.form.get('freight_price', 0) or 0)

        order = Order()
        order.gen_number()
        order.user_id = current_user.id
        order.payment_method = payment
        order.subtotal = cart_total()
        order.freight = freight_price
        order.total = cart_total() + freight_price
        order.freight_type = freight_type
        order.cep = request.form.get('cep', '')
        order.street = request.form.get('street', '')
        order.number = request.form.get('number', '')
        order.complement = request.form.get('complement', '')
        order.neighborhood = request.form.get('neighborhood', '')
        order.city = request.form.get('city', '')
        order.state = request.form.get('state', '')

        db.session.add(order)
        db.session.flush()

        for item in cart:
            oi = OrderItem(
                order_id=order.id, product_id=item['product_id'],
                product_name=item['name'], color=item.get('color', ''),
                size=item.get('size', ''), quantity=item['qty'],
                unit_price=item['price']
            )
            db.session.add(oi)
            # Baixa no estoque
            p = db.session.get(Product, item['product_id'])
            if p and p.stock > 0:
                p.stock = max(0, p.stock - item['qty'])

        db.session.commit()
        session['cart'] = []

        if payment == 'pix':
            return redirect(url_for('pix_payment', oid=order.id))
        return redirect(url_for('order_success', oid=order.id))

    return render_template('checkout.html', cart=cart, total=cart_total())


@app.route('/pagamento/pix/<int:oid>')
@login_required
def pix_payment(oid):
    order = Order.query.filter_by(id=oid, user_id=current_user.id).first_or_404()
    qr_img, pix_code = generate_pix_qr(order.total, order.order_number)
    return render_template('pix_payment.html', order=order, qr_img=qr_img, pix_code=pix_code)


@app.route('/pedido/sucesso/<int:oid>')
@login_required
def order_success(oid):
    order = Order.query.filter_by(id=oid, user_id=current_user.id).first_or_404()
    return render_template('order_success.html', order=order)


@app.route('/minha-conta')
@login_required
def minha_conta():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('minha_conta.html', orders=orders)


# ── Admin ──────────────────────────────────────────────────────────────────────
@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    total_orders = Order.query.count()
    total_revenue = db.session.query(func.sum(Order.total)).filter_by(payment_status='pago').scalar() or 0
    total_products = Product.query.filter_by(is_active=True).count()
    total_users = User.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    low_stock = Product.query.filter(Product.stock <= 5, Product.is_active == True).all()
    return render_template('admin/dashboard.html', total_orders=total_orders,
                           total_revenue=total_revenue, total_products=total_products,
                           total_users=total_users, recent_orders=recent_orders,
                           low_stock=low_stock)


@app.route('/admin/produtos')
@login_required
@admin_required
def admin_produtos():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/produtos.html', products=products)


@app.route('/admin/produto/novo', methods=['GET', 'POST'])
@app.route('/admin/produto/<int:pid>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_produto_form(pid=None):
    product = db.session.get(Product, pid) if pid else None
    categories = Category.query.all()

    if request.method == 'POST':
        if not product:
            product = Product()
            db.session.add(product)

        product.name = request.form.get('name', '')
        product.description = request.form.get('description', '')
        product.price = float(request.form.get('price', 0) or 0)
        product.weight_grams = int(request.form.get('weight_grams', 300) or 300)
        cat_id = request.form.get('category_id')
        product.category_id = int(cat_id) if cat_id else None
        product.stock = int(request.form.get('stock', 0) or 0)
        product.is_featured = request.form.get('is_featured') == 'on'
        product.is_active = request.form.get('is_active', 'on') == 'on'

        colors = [c.strip() for c in request.form.get('colors', '').split(',') if c.strip()]
        sizes = [s.strip() for s in request.form.get('sizes', '').split(',') if s.strip()]
        product.colors = json.dumps(colors)
        product.sizes = json.dumps(sizes if sizes else ['P', 'M', 'G', 'GG'])

        # Imagens que o admin manteve (não removeu via botão X)
        existing = request.form.getlist('existing_images')
        images = existing if pid else []

        # Novas imagens enviadas
        for f in request.files.getlist('images'):
            if f and f.filename:
                ext = f.filename.rsplit('.', 1)[-1].lower()
                if ext in ('jpg', 'jpeg', 'png', 'webp'):
                    fname = f"{uuid.uuid4().hex}.{ext}"
                    f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                    images.append(f'/static/uploads/{fname}')
        product.images = json.dumps(images)

        db.session.commit()
        flash('Produto salvo com sucesso! ✓', 'success')
        return redirect(url_for('admin_produtos'))

    return render_template('admin/produto_form.html', product=product, categories=categories)


@app.route('/admin/produto/<int:pid>/deletar', methods=['POST'])
@login_required
@admin_required
def admin_produto_delete(pid):
    p = db.session.get(Product, pid)
    if p:
        # Remove itens de pedido vinculados antes de deletar
        OrderItem.query.filter_by(product_id=pid).update({'product_id': None})
        db.session.delete(p)
        db.session.commit()
        flash('Produto removido com sucesso.', 'info')
    return redirect(url_for('admin_produtos'))


@app.route('/admin/pedidos')
@login_required
@admin_required
def admin_pedidos():
    status_filter = request.args.get('status', '')
    query = Order.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    orders = query.order_by(Order.created_at.desc()).all()
    return render_template('admin/pedidos.html', orders=orders, current_status=status_filter)


@app.route('/admin/pedido/<int:oid>')
@login_required
@admin_required
def admin_pedido_detail(oid):
    order = Order.query.get_or_404(oid)
    return render_template('admin/pedido_detail.html', order=order)


@app.route('/admin/pedido/<int:oid>/status', methods=['POST'])
@login_required
@admin_required
def admin_update_order(oid):
    order = Order.query.get_or_404(oid)
    order.status = request.form.get('status', order.status)
    order.payment_status = request.form.get('payment_status', order.payment_status)
    db.session.commit()
    flash('Pedido atualizado!', 'success')
    return redirect(url_for('admin_pedidos'))


@app.route('/admin/produto/<int:pid>/estoque', methods=['POST'])
@login_required
@admin_required
def admin_repor_estoque(pid):
    p = db.session.get(Product, pid)
    if p:
        qty = int(request.form.get('qty', 0) or 0)
        if qty > 0:
            p.stock += qty
            db.session.commit()
            flash(f'+{qty} unidades adicionadas ao estoque de "{p.name}".', 'success')
    return redirect(url_for('admin_produtos'))

@app.route('/admin/categorias', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_categorias():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            slug = slugify(name)
            if not Category.query.filter_by(slug=slug).first():
                db.session.add(Category(name=name, slug=slug))
                db.session.commit()
                flash('Categoria adicionada!', 'success')
            else:
                flash('Categoria já existe.', 'error')
    cats = Category.query.all()
    return render_template('admin/categorias.html', categories=cats)


@app.route('/admin/categoria/<int:cid>/deletar', methods=['POST'])
@login_required
@admin_required
def admin_categoria_delete(cid):
    cat = db.session.get(Category, cid)
    if cat:
        db.session.delete(cat)
        db.session.commit()
        flash('Categoria removida.', 'info')
    return redirect(url_for('admin_categorias'))


@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_usuarios():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/usuarios.html', users=users)


# ── Context & Errors ───────────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    cart = get_cart()
    return {
        'cart_count': sum(i['qty'] for i in cart),
        'all_categories': Category.query.all(),
        'whatsapp_number': app.config['WHATSAPP_NUMBER'],
    }


@app.errorhandler(403)
def e403(e): return render_template('errors/403.html'), 403

@app.errorhandler(404)
def e404(e): return render_template('errors/404.html'), 404

@app.errorhandler(500)
def e500(e): return render_template('errors/500.html'), 500


# ── Init DB ────────────────────────────────────────────────────────────────────
def init_db():
    db.create_all()
    if not User.query.filter_by(email='admin@maravilinda.com').first():
        admin = User(name='Administrador', email='admin@maravilinda.com', is_admin=True)
        admin.set_password('Admin@2024!')
        db.session.add(admin)

    default_cats = [
        ('Lançamentos', 'lancamentos'), ('Blusas', 'blusas'),
        ('Calças', 'calcas'), ('Vestidos', 'vestidos'),
        ('Conjuntos', 'conjuntos'), ('Macaquinhos', 'macaquinhos'),
        ('Shorts', 'shorts'), ('Saias', 'saias'),
        ('Acessórios', 'acessorios'), ('Sale', 'sale'),
    ]
    for name, slug in default_cats:
        if not Category.query.filter_by(slug=slug).first():
            db.session.add(Category(name=name, slug=slug))
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
