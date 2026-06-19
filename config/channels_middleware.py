from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from channels.auth import AuthMiddlewareStack
from urllib.parse import parse_qs

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token_string):
    try:
        token   = AccessToken(token_string)
        user_id = token['user_id']
        return User.objects.get(pk=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    El token llega como parámetro de la URL:
    ws://localhost:8000/ws/encomiendas/?token=eyJhbGci...
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            query_string = scope.get('query_string', b'').decode('utf-8')
            params     = parse_qs(query_string)
            token_list   = params.get('token', [])

            if token_list:
                scope['user'] = await get_user_from_token(token_list[0])
            elif not scope.get('user') or isinstance(scope['user'], AnonymousUser):
                # Optionally check if AuthMiddlewareStack already populated user (for session auth)
                scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)

def JWTAuthMiddlewareStack(inner):
    return AuthMiddlewareStack(JWTAuthMiddleware(inner))
