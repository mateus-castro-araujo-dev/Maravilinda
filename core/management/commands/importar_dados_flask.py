import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Category, Order, OrderItem, Product, User

FLASK_DB = Path(__file__).resolve().parents[3] / 'instance' / 'maravilinda.db'


class Command(BaseCommand):
    help = 'Importa dados do banco Flask (instance/maravilinda.db) para o Django'

    def handle(self, *args, **options):
        if not FLASK_DB.exists():
            self.stderr.write(f'Banco Flask não encontrado: {FLASK_DB}')
            return

        conn = sqlite3.connect(str(FLASK_DB))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        with transaction.atomic():
            self._importar_categories(c)
            self._importar_users(c)
            self._importar_products(c)
            self._importar_orders(c)
            self._importar_order_items(c)

        conn.close()
        self.stdout.write(self.style.SUCCESS('Importação concluída com sucesso!'))

    def _importar_categories(self, c):
        c.execute('SELECT * FROM categories')
        count = 0
        for row in c.fetchall():
            obj, created = Category.objects.update_or_create(
                id=row['id'],
                defaults={'name': row['name'], 'slug': row['slug']},
            )
            if created:
                count += 1
        self.stdout.write(f'  Categorias: {count} novas importadas')

    def _importar_users(self, c):
        c.execute('SELECT * FROM users')
        count = 0
        for row in c.fetchall():
            if User.objects.filter(email=row['email']).exists():
                continue
            u = User(
                id=row['id'],
                email=row['email'],
                name=row['name'],
                phone=row['phone'] or '',
                is_admin=bool(row['is_admin']),
                is_staff=bool(row['is_admin']),
                is_superuser=bool(row['is_admin']),
            )
            # Preserva o hash bcrypt do Flask adicionando o prefixo que Django entende
            flask_hash = row['password_hash']
            if flask_hash and flask_hash.startswith('$2'):
                u.password = 'bcrypt$' + flask_hash
            else:
                u.set_unusable_password()
            u.save()
            count += 1
        self.stdout.write(f'  Usuários: {count} novos importados')

    def _importar_products(self, c):
        c.execute('SELECT * FROM products')
        count = 0
        for row in c.fetchall():
            obj, created = Product.objects.update_or_create(
                id=row['id'],
                defaults={
                    'name': row['name'],
                    'description': row['description'] or '',
                    'price': row['price'],
                    'weight_grams': row['weight_grams'] or 300,
                    'category_id': row['category_id'],
                    'images': row['images'] or '[]',
                    'colors': row['colors'] or '[]',
                    'sizes': row['sizes'] or '["P","M","G","GG"]',
                    'stock': row['stock'] or 0,
                    'is_featured': bool(row['is_featured']),
                    'is_active': bool(row['is_active']),
                },
            )
            if created:
                count += 1
        self.stdout.write(f'  Produtos: {count} novos importados')

    def _importar_orders(self, c):
        c.execute('SELECT * FROM orders')
        count = 0
        for row in c.fetchall():
            obj, created = Order.objects.update_or_create(
                id=row['id'],
                defaults={
                    'order_number': row['order_number'],
                    'user_id': row['user_id'],
                    'status': row['status'] or 'aguardando',
                    'payment_method': row['payment_method'] or '',
                    'payment_status': row['payment_status'] or 'pendente',
                    'subtotal': row['subtotal'] or 0,
                    'freight': row['freight'] or 0,
                    'total': row['total'] or 0,
                    'freight_type': row['freight_type'] or '',
                    'cep': row['cep'] or '',
                    'street': row['street'] or '',
                    'number': row['number'] or '',
                    'complement': row['complement'] or '',
                    'neighborhood': row['neighborhood'] or '',
                    'city': row['city'] or '',
                    'state': row['state'] or '',
                },
            )
            if created:
                count += 1
        self.stdout.write(f'  Pedidos: {count} novos importados')

    def _importar_order_items(self, c):
        c.execute('SELECT * FROM order_items')
        count = 0
        for row in c.fetchall():
            obj, created = OrderItem.objects.update_or_create(
                id=row['id'],
                defaults={
                    'order_id': row['order_id'],
                    'product_id': row['product_id'],
                    'product_name': row['product_name'] or '',
                    'color': row['color'] or '',
                    'size': row['size'] or '',
                    'quantity': row['quantity'] or 1,
                    'unit_price': row['unit_price'] or 0,
                },
            )
            if created:
                count += 1
        self.stdout.write(f'  Itens de pedido: {count} novos importados')
