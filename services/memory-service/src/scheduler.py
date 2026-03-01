"""
Scheduler — Registra el job semanal del pipeline de aprendizaje episódico.

Usa APScheduler 3.x con AsyncIOScheduler para integrarse con el event loop
de FastAPI sin bloquear la aplicación.

El job se ejecuta cada domingo a las 23:00 (hora local del servidor).
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from database import AsyncSessionLocal
from pipeline_manager import run_pipeline

_scheduler = AsyncIOScheduler()


async def _weekly_pipeline_job() -> None:
    """Job que APScheduler llama cada domingo a las 23:00."""
    logger.info("[scheduler] iniciando job semanal del pipeline")
    async with AsyncSessionLocal() as db:
        result = await run_pipeline(db)
    logger.info(f"[scheduler] job finalizado — status={result.get('status')}")


def start_scheduler() -> None:
    """Registra el job y arranca el scheduler. Llamar desde startup_event."""
    _scheduler.add_job(
        _weekly_pipeline_job,
        CronTrigger(day_of_week="sun", hour=23, minute=0),
        id="weekly_episodic_pipeline",
        replace_existing=True,
        max_instances=1,          # nunca dos runs simultáneos desde el scheduler
        coalesce=True,            # si se perdió un disparo, ejecutar uno solo
    )
    _scheduler.start()
    logger.info("[scheduler] iniciado — pipeline episódico cada domingo 23:00")


def stop_scheduler() -> None:
    """Detiene el scheduler. Llamar desde shutdown_event."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] detenido")


def get_next_run_time() -> str | None:
    """Devuelve el próximo disparo del job como ISO string, o None."""
    job = _scheduler.get_job("weekly_episodic_pipeline")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
