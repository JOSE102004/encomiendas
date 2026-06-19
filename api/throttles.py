from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

class LoginRateThrottle(AnonRateThrottle):
    """Limitar intentos de login: 5 por minuto"""
    scope = 'login_attempt'

class EmpleadoRateThrottle(UserRateThrottle):
    """Empleados: 100 peticiones por minuto"""
    scope = 'empleado'

class CambioEstadoThrottle(UserRateThrottle):
    """Limitar cambios de estado: 30 por hora"""
    scope = 'cambio_estado'
