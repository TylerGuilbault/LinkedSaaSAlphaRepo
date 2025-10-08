from fastapi import APIRouter
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from typing import Optional, Dict, Any
from app.services.scheduler import run_once

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

scheduler: Optional[BackgroundScheduler] = None

@router.post("/run")
def run_now() -> Dict[str, Any]:
    return run_once()

@router.post("/start")
def start(cron: str = "0 9 * * *") -> Dict[str, Any]:
    # default: 9:00 every day (server time). Use standard 5-field cron: m h dom mon dow
    global scheduler
    if scheduler and scheduler.running:
        return {"status": "already-running"}

    scheduler = BackgroundScheduler(timezone="UTC")
    trigger = CronTrigger.from_crontab(cron)
    scheduler.add_job(run_once, trigger, id="daily_post", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    return {"status": "started", "cron": cron}

@router.post("/stop")
def stop() -> Dict[str, Any]:
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        return {"status": "stopped"}
    return {"status": "not-running"}

@router.get("/status")
def status() -> Dict[str, Any]:
    global scheduler
    return {"running": bool(scheduler and scheduler.running)}
