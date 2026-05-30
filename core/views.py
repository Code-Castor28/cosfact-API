# ─────────────────────────────────────────────────────────────────
# api/v1/health/views.py
# ─────────────────────────────────────────────────────────────────
import os
import time
import platform

import psutil
import redis
from django.conf import settings
from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from django.http import JsonResponse


def health_check(request):
    """
    GET /api/v1/health/          → reporte completo (monitoreo / dashboard)
    GET /api/v1/health/?simple=1 → solo status 200/503 (load balancer / k8s)
    """
    if request.GET.get("simple"):
        ok, _ = _check_database()
        return JsonResponse(
            {"status": "healthy" if ok else "unhealthy"},
            status=200 if ok else 503,
        )

    services = {}
    overall_healthy = True

    # ── 1. Base de datos ───────────────────────────────────────────
    db_ok, db_latency_ms = _check_database()
    services["database"] = {
        "status": "ok" if db_ok else "down",
        "latency_ms": db_latency_ms,
    }
    if not db_ok:
        overall_healthy = False

    # ── 2. Redis (conexión directa) ────────────────────────────────
    redis_ok, redis_info = _check_redis()
    services["redis"] = redis_info
    if not redis_ok:
        overall_healthy = False

    # ── 3. Caché de Django ─────────────────────────────────────────
    cache_ok, cache_detail = _check_cache()
    services["cache"] = {
        "status": "ok" if cache_ok else "down",
        "backend": _cache_backend_name(),
        "detail": cache_detail,
    }
    if not cache_ok:
        overall_healthy = False

    # ── 4. Celery workers + colas + tareas fallidas ────────────────
    celery_ok, celery_info = _check_celery()
    services["celery"] = celery_info
    if not celery_ok:
        overall_healthy = False

    # ── 5. Proceso actual (memoria / CPU) ──────────────────────────
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info()
    services["process"] = {
        "memory_rss_mb": round(mem.rss / 1024 / 1024, 2),
        "memory_vms_mb": round(mem.vms / 1024 / 1024, 2),
        "cpu_percent": proc.cpu_percent(interval=0.1),
        "threads": proc.num_threads(),
    }

    # ── 6. Uptime del proceso ──────────────────────────────────────
    uptime_seconds = int(time.time() - proc.create_time())
    services["uptime"] = {
        "seconds": uptime_seconds,
        "human": _format_uptime(uptime_seconds),
    }

    # ── 7. Info de la aplicación ───────────────────────────────────
    services["app"] = {
        "version": getattr(settings, "APP_VERSION", "n/d"),
        "commit": getattr(settings, "GIT_COMMIT", "n/d"),
        "environment": getattr(settings, "ENVIRONMENT", "n/d"),
        "python": platform.python_version(),
        "django": _django_version(),
        "url": request.build_absolute_uri(),
    }

    return JsonResponse(
        {"status": "healthy" if overall_healthy else "unhealthy", "services": services},
        status=200 if overall_healthy else 503,
    )


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _check_database():
    """Ejecuta SELECT 1 y mide latencia."""
    try:
        conn = connections["default"]
        start = time.monotonic()
        conn.cursor().execute("SELECT 1")
        return True, round((time.monotonic() - start) * 1000, 2)
    except OperationalError:
        return False, None


def _check_redis():
    """Conecta directamente a Redis y retorna métricas del servidor."""
    broker_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
    try:
        # decode_responses=True es vital para que devuelva texto (str) y no bytes (b'')
        client = redis.Redis.from_url(broker_url, socket_connect_timeout=2, decode_responses=True)
        
        start = time.monotonic()
        client.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        
        # El '# type: ignore' le cierra la boca a Mypy/Pyright con el falso positivo del Awaitable
        info = client.info()  # type: ignore
        
        return True, {
            "status": "ok",
            "latency_ms": latency_ms,
            "version": info.get("redis_version"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
            "uptime_in_seconds": info.get("uptime_in_seconds"),
        }
    except Exception as exc:
        # Si el servidor está apagado o el puerto cerrado, cae aquí sin romper Django
        return False, {"status": "down", "detail": str(exc)}


def _check_cache():
    """Escribe y lee una clave de prueba en el caché de Django."""
    key = "_health_probe"
    try:
        cache.set(key, "ok", timeout=5)
        val = cache.get(key)
        if val == "ok":
            return True, "read/write ok"
        return False, "la lectura devolvió un valor inesperado"
    except Exception as exc:
        return False, str(exc)


def _check_celery():
    """
    Inspecciona workers, colas y tareas fallidas recientes.
    Usa la instancia central definida en core/celery.py.
    """
    try:
        from core import celery_app

        inspector = celery_app.control.inspect(timeout=2.0)

        active_map   = inspector.active()   or {}
        stats_map    = inspector.stats()    or {}
        reserved_map = inspector.reserved() or {}

        workers = []
        for worker_name, worker_stats in stats_map.items():
            active_tasks   = active_map.get(worker_name, [])
            reserved_tasks = reserved_map.get(worker_name, [])
            workers.append({
                "name": worker_name,
                "status": "online",
                "active_tasks": len(active_tasks),
                "reserved_tasks": len(reserved_tasks),
                "pool": worker_stats.get("pool", {}).get("implementation", "n/d"),
                "concurrency": worker_stats.get("pool", {}).get("max-concurrency", "n/d"),
                "processed_total": worker_stats.get("total", {}),
            })

        queue_info   = _check_celery_queues(celery_app)
        failed_tasks = _check_celery_failures()

        ok = len(workers) > 0
        return ok, {
            "status": "ok" if ok else "no_workers",
            "workers_online": len(workers),
            "workers": workers,
            "queues": queue_info,
            "failed_tasks_recent": failed_tasks,
        }

    except Exception as exc:
        return False, {"status": "error", "detail": str(exc)}


def _check_celery_queues(celery_app):
    """
    Lee de Redis la cantidad de mensajes pendientes en cada cola.
    Detecta automáticamente: cola por defecto + colas del beat_schedule.
    """
    broker_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
    queues = {}
    try:
        client = redis.Redis.from_url(broker_url, socket_connect_timeout=2)

        # Colas configuradas explícitamente en task_queues
        configured = {q.name for q in (celery_app.conf.task_queues or [])}

        # Cola por defecto
        configured.add(celery_app.conf.task_default_queue or "celery")

        # Colas usadas en el beat_schedule (ej: 'default')
        for task_conf in (celery_app.conf.beat_schedule or {}).values():
            queue_name = task_conf.get("options", {}).get("queue")
            if queue_name:
                configured.add(queue_name)

        for queue_name in sorted(configured):
            queues[queue_name] = {"pending_messages": client.llen(queue_name)}

    except Exception as exc:
        queues["error"] = str(exc)

    return queues


def _check_celery_failures():
    """
    Busca tareas con estado FAILURE en el result backend de Redis.
    Retorna los últimos 10 fallos con task_id, traceback recortado y fecha.
    Si el backend no está configurado o falla, retorna lista vacía sin romper.
    """
    import json

    broker_url = getattr(settings, "CELERY_RESULT_BACKEND",
                 getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"))
    try:
        client = redis.Redis.from_url(broker_url, socket_connect_timeout=2)
        keys = client.keys("celery-task-meta-*")
        failures = []
        for key in keys[-50:]:
            raw = client.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if data.get("status") == "FAILURE":
                failures.append({
                    "task_id": data.get("task_id"),
                    "traceback": (data.get("traceback") or "")[:300],
                    "date_done": data.get("date_done"),
                })
        return failures[-10:]
    except Exception:
        return []


def _cache_backend_name():
    try:
        backend = settings.CACHES["default"]["BACKEND"]
        return backend.rsplit(".", 1)[-1]
    except Exception:
        return "unknown"


def _format_uptime(seconds: int) -> str:
    days,   rem    = divmod(seconds, 86400)
    hours,  rem    = divmod(rem, 3600)
    minutes, secs  = divmod(rem, 60)
    parts = []
    if days:    parts.append(f"{days}d")
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _django_version():
    import django
    return django.get_version()