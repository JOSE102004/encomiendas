from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from envios.api_auth import EncomiendaTokenView, LoginCookieView, LogoutCookieView
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('envios.urls')),
    path('clientes/', include('clientes.urls')),
    path('rutas/', include('rutas.urls')),

    # API REST con versionado dinámico
    path('api/<version>/', include('api.urls')),

    # Auth JWT
    path('api/v1/auth/token/', EncomiendaTokenView.as_view(), name='token_obtain'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),

    # Auth JWT via HttpOnly cookies
    path('api/v1/auth/login/', LoginCookieView.as_view(), name='auth_login'),
    path('api/v1/auth/logout/', LogoutCookieView.as_view(), name='auth_logout'),

    # Documentacion
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
