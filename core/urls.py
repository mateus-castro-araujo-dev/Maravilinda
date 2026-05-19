from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('cadastro/', views.cadastro_view, name='cadastro'),
    path('logout/', views.logout_view, name='logout'),

    # Reset de senha
    path('senha/esqueci/', views.AsyncPasswordResetView.as_view(
        template_name='auth/password_reset.html',
        email_template_name='auth/password_reset_email.txt',
        subject_template_name='auth/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('senha/enviada/', auth_views.PasswordResetDoneView.as_view(
        template_name='auth/password_reset_done.html',
    ), name='password_reset_done'),
    path('senha/confirmar/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='auth/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('senha/redefinida/', auth_views.PasswordResetCompleteView.as_view(
        template_name='auth/password_reset_complete.html',
    ), name='password_reset_complete'),

    # Loja
    path('', views.index_view, name='index'),
    path('produtos/', views.produtos_view, name='produtos'),
    path('produto/<int:pid>/', views.produto_view, name='produto'),

    # Carrinho
    path('carrinho/', views.carrinho_view, name='carrinho'),
    path('api/cart/', views.api_cart, name='api_cart'),
    path('api/cart/add/', views.api_cart_add, name='api_cart_add'),
    path('api/cart/update/', views.api_cart_update, name='api_cart_update'),
    path('api/cart/remove/', views.api_cart_remove, name='api_cart_remove'),

    # Frete / CEP
    path('api/frete/', views.api_frete, name='api_frete'),
    path('api/cep/<str:cep>/', views.api_cep, name='api_cep'),

    # Checkout & Pedidos
    path('checkout/', views.checkout_view, name='checkout'),
    path('pagamento/pix/<str:num>/', views.pix_payment_view, name='pix_payment'),
    path('pagamento/pix/<str:num>/status/', views.pix_status_view, name='pix_status'),
    path('webhook/mercadopago/', views.mercadopago_webhook_view, name='mercadopago_webhook'),
    path('pedido/sucesso/<str:num>/', views.order_success_view, name='order_success'),
    path('minha-conta/', views.minha_conta_view, name='minha_conta'),
    path('favoritos/', views.favoritos_view, name='favoritos'),
    path('api/wishlist/toggle/', views.api_wishlist_toggle, name='api_wishlist_toggle'),
    path('api/wishlist/ids/', views.api_wishlist_ids, name='api_wishlist_ids'),

    # Admin
    path('admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/produtos/', views.admin_produtos_view, name='admin_produtos'),
    path('admin/produto/novo/', views.admin_produto_form_view, name='admin_produto_form'),
    path('admin/produto/<int:pid>/editar/', views.admin_produto_form_view, name='admin_produto_form_edit'),
    path('admin/produto/<int:pid>/deletar/', views.admin_produto_delete_view, name='admin_produto_delete'),
    path('admin/produto/<int:pid>/estoque/', views.admin_repor_estoque_view, name='admin_repor_estoque'),
    path('admin/pedidos/', views.admin_pedidos_view, name='admin_pedidos'),
    path('admin/pedido/<int:oid>/', views.admin_pedido_detail_view, name='admin_pedido_detail'),
    path('admin/pedido/<int:oid>/status/', views.admin_update_order_view, name='admin_update_order'),
    path('admin/categorias/', views.admin_categorias_view, name='admin_categorias'),
    path('admin/categoria/<int:cid>/deletar/', views.admin_categoria_delete_view, name='admin_categoria_delete'),
    path('admin/usuarios/', views.admin_usuarios_view, name='admin_usuarios'),
]
