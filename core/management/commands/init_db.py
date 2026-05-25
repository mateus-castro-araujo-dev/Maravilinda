from django.core.management.base import BaseCommand
from core.models import User, Category


class Command(BaseCommand):
    help = 'Inicializa o banco de dados com dados padrão'

    def handle(self, *args, **options):
        if not User.objects.filter(email='admin@maravilinda.com').exists():
            User.objects.create_superuser(
                email='admin@maravilinda.com',
                name='Administrador',
                password='Admin@2024!',
            )
            self.stdout.write(self.style.SUCCESS('Admin criado: admin@maravilinda.com / Admin@2024!'))

        default_cats = [
            ('Lançamentos', 'lancamentos'), ('Blusas', 'blusas'),
            ('Calças', 'calcas'), ('Vestidos', 'vestidos'),
            ('Conjuntos', 'conjuntos'), ('Macaquinhos', 'macaquinhos'),
            ('Shorts', 'shorts'), ('Saias', 'saias'),
            ('Acessórios', 'acessorios'), ('Sale', 'sale'),
        ]
        for name, slug in default_cats:
            Category.objects.get_or_create(slug=slug, defaults={'name': name})
        self.stdout.write(self.style.SUCCESS('Categorias padrão criadas.'))
