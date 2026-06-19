from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

class EncomiendaTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Agregar datos del empleado al payload del JWT
        token['username'] = user.username
        token['email'] = user.email
        try:
            emp = user.empleado
            token['empleado_id'] = emp.id
            token['empleado_cod'] = emp.codigo
            token['cargo'] = emp.cargo
        except Exception:
            pass
        return token

from api.throttles import LoginRateThrottle

class EncomiendaTokenView(TokenObtainPairView):
    serializer_class = EncomiendaTokenSerializer
    throttle_classes = [LoginRateThrottle]

class LoginCookieView(APIView):
    permission_classes = []

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {'error': 'Credenciales inválidas.'},
                status=401
            )

        refresh = RefreshToken.for_user(user)
        response = Response({'message': 'Login exitoso.'})

        # Guardar el JWT en una HttpOnly Cookie
        response.set_cookie(
            key='access_token',
            value=str(refresh.access_token),
            httponly=True,    # no accesible desde JS
            secure=True,      # solo por HTTPS
            samesite='Lax',   # protege contra CSRF
            max_age=3600,     # 1 hora
        )
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure=True,
            samesite='Lax',
            max_age=604800,   # 7 días
        )
        return response

class LogoutCookieView(APIView):
    def post(self, request):
        response = Response({'message': 'Logout exitoso.'})
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response
