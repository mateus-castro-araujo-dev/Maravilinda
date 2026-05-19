import json
import secrets
from datetime import datetime

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    is_admin = models.BooleanField(default=False)

    # Endereço padrão salvo no último checkout
    saved_cep = models.CharField(max_length=10, blank=True)
    saved_street = models.CharField(max_length=150, blank=True)
    saved_number = models.CharField(max_length=20, blank=True)
    saved_complement = models.CharField(max_length=100, blank=True)
    saved_neighborhood = models.CharField(max_length=100, blank=True)
    saved_city = models.CharField(max_length=100, blank=True)
    saved_state = models.CharField(max_length=2, blank=True)
    saved_payment_method = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email


class Category(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=60, unique=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.FloatField()
    weight_grams = models.IntegerField(default=300)
    length_cm = models.IntegerField(default=28)
    width_cm = models.IntegerField(default=19)
    height_cm = models.IntegerField(default=5)
    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='products'
    )
    images = models.TextField(default='[]')
    colors = models.TextField(default='[]')
    sizes = models.TextField(default='["P","M","G","GG"]')
    stock = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'products'

    def __str__(self):
        return self.name

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

    @property
    def fmt_price(self):
        return f"R$ {self.price:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


class Order(models.Model):
    order_number = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='orders'
    )
    status = models.CharField(max_length=30, default='aguardando')
    payment_method = models.CharField(max_length=20, blank=True)
    payment_status = models.CharField(max_length=20, default='pendente')
    subtotal = models.FloatField(default=0)
    freight = models.FloatField(default=0)
    total = models.FloatField(default=0)
    freight_type = models.CharField(max_length=10, blank=True)
    cep = models.CharField(max_length=10, blank=True)
    street = models.CharField(max_length=150, blank=True)
    number = models.CharField(max_length=20, blank=True)
    complement = models.CharField(max_length=100, blank=True)
    neighborhood = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    external_provider = models.CharField(max_length=30, blank=True)
    external_id = models.CharField(max_length=100, blank=True, db_index=True)
    external_url = models.URLField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'orders'

    def __str__(self):
        return self.order_number

    def gen_number(self):
        self.order_number = f"MLV{datetime.now().strftime('%y%m%d')}{secrets.token_hex(3).upper()}"

    @property
    def fmt_total(self):
        return f"R$ {self.total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='order_items'
    )
    product_name = models.CharField(max_length=150)
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=10, blank=True)
    quantity = models.IntegerField(default=1)
    unit_price = models.FloatField()

    class Meta:
        db_table = 'order_items'

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wishlist'
        unique_together = ('user', 'product')


class PendingOrder(models.Model):
    order_number = models.CharField(max_length=20, unique=True)
    external_id = models.CharField(max_length=200, blank=True, db_index=True)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pending_orders'

    @property
    def total(self):
        return self.data.get('total', 0)

    @property
    def fmt_total(self):
        t = self.total
        return f"R$ {t:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
