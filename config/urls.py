from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import handler403, handler404, handler500

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('core.urls')),
] + static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')

handler403 = handler403
handler404 = handler404
handler500 = handler500
