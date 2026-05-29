from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError

def health_check(request):
    status_code = 200
    response_data = {
        "status": "healthy",
        "services": {
            "database": "ok"
        }
    }
    
    # Intenta levantar un cursor en la base de datos para verificar conexión real
    try:
        db_conn = connections['default']
        db_conn.cursor()  
    except OperationalError:
        status_code = 503
        response_data["status"] = "unhealthy"
        response_data["services"]["database"] = "down"

    return JsonResponse(response_data, status=status_code)