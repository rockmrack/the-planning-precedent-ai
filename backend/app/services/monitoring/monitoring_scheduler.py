"""
Monitoring Scheduler
Schedules and runs periodic checks for new planning applications
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from .alert_service import AlertService, PlanningApplication

logger = logging.getLogger(__name__)


class ScheduleFrequency(str, Enum):
    """How often to check for new applications"""
    HOURLY = "hourly"
    TWICE_DAILY = "twice_daily"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass
class MonitoringJob:
    """A scheduled monitoring job"""
    id: str
    name: str
    frequency: ScheduleFrequency
    source: str  # Which council/data source
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    is_active: bool = True
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None


@dataclass
class MonitoringStats:
    """Statistics for monitoring service"""
    total_jobs: int = 0
    active_jobs: int = 0
    total_applications_processed: int = 0
    total_alerts_triggered: int = 0
    last_run: Optional[datetime] = None
    uptime_seconds: int = 0


class MonitoringScheduler:
    """Schedules and manages monitoring jobs"""

    def __init__(
        self,
        alert_service: AlertService,
        scraper_func: Optional[Callable] = None
    ):
        self.alert_service = alert_service
        self.scraper_func = scraper_func

        self.jobs: Dict[str, MonitoringJob] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._start_time: Optional[datetime] = None

        # Stats
        self.total_applications_processed = 0
        self.total_alerts_triggered = 0

        # Initialize default jobs
        self._init_default_jobs()

    def _init_default_jobs(self):
        """Initialize default monitoring jobs"""
        # Camden Council - check twice daily
        self.jobs["camden"] = MonitoringJob(
            id="camden",
            name="Camden Council Planning Portal",
            frequency=ScheduleFrequency.TWICE_DAILY,
            source="camden_council",
            next_run=datetime.utcnow() + timedelta(hours=1)
        )

        # Weekly summary job
        self.jobs["weekly_summary"] = MonitoringJob(
            id="weekly_summary",
            name="Weekly Summary Digest",
            frequency=ScheduleFrequency.WEEKLY,
            source="internal",
            next_run=self._next_weekday(0, 9)  # Monday 9 AM
        )

    def _next_weekday(self, weekday: int, hour: int) -> datetime:
        """Get next occurrence of a weekday at specific hour"""
        now = datetime.utcnow()
        days_ahead = weekday - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_date = now + timedelta(days=days_ahead)
        return next_date.replace(hour=hour, minute=0, second=0, microsecond=0)

    async def start(self):
        """Start the monitoring scheduler"""
        if self._running:
            return

        self._running = True
        self._start_time = datetime.utcnow()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Monitoring scheduler started")

    async def stop(self):
        """Stop the monitoring scheduler"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring scheduler stopped")

    async def _run_loop(self):
        """Main scheduler loop"""
        while self._running:
            try:
                now = datetime.utcnow()

                # Check each job
                for job_id, job in self.jobs.items():
                    if not job.is_active:
                        continue

                    if job.next_run and job.next_run <= now:
                        await self._run_job(job)

                # Sleep for 5 minutes between checks
                await asyncio.sleep(300)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)

    async def _run_job(self, job: MonitoringJob):
        """Run a monitoring job"""
        logger.info(f"Running job: {job.name}")

        try:
            if job.source == "camden_council":
                await self._check_camden_applications(job)
            elif job.source == "internal":
                await self._run_internal_job(job)

            job.last_run = datetime.utcnow()
            job.run_count += 1
            job.next_run = self._calculate_next_run(job)
            job.last_error = None

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            job.error_count += 1
            job.last_error = str(e)
            # Retry in 1 hour on error
            job.next_run = datetime.utcnow() + timedelta(hours=1)

    async def _check_camden_applications(self, job: MonitoringJob):
        """Check for new Camden planning applications"""
        applications = []

        if self.scraper_func:
            # Use provided scraper function
            raw_data = await self.scraper_func()
            applications = [
                self._convert_to_application(d) for d in raw_data
            ]
        else:
            # Demo mode - generate sample applications
            applications = self._generate_demo_applications()

        if applications:
            triggers = await self.alert_service.process_new_applications(applications)
            self.total_applications_processed += len(applications)
            self.total_alerts_triggered += len(triggers)

            logger.info(
                f"Processed {len(applications)} applications, "
                f"triggered {len(triggers)} alerts"
            )

    async def _run_internal_job(self, job: MonitoringJob):
        """Run internal maintenance jobs"""
        if job.id == "weekly_summary":
            # Would generate and send weekly digest emails
            logger.info("Would send weekly summary digests")

    def _calculate_next_run(self, job: MonitoringJob) -> datetime:
        """Calculate the next run time for a job"""
        now = datetime.utcnow()

        if job.frequency == ScheduleFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif job.frequency == ScheduleFrequency.TWICE_DAILY:
            # 8 AM and 6 PM
            if now.hour < 8:
                return now.replace(hour=8, minute=0, second=0)
            elif now.hour < 18:
                return now.replace(hour=18, minute=0, second=0)
            else:
                return (now + timedelta(days=1)).replace(hour=8, minute=0, second=0)
        elif job.frequency == ScheduleFrequency.DAILY:
            return (now + timedelta(days=1)).replace(hour=6, minute=0, second=0)
        elif job.frequency == ScheduleFrequency.WEEKLY:
            return self._next_weekday(0, 9)

        return now + timedelta(hours=1)

    def _convert_to_application(self, data: dict) -> PlanningApplication:
        """Convert raw scraper data to PlanningApplication"""
        return PlanningApplication(
            reference=data.get("reference", ""),
            address=data.get("address", ""),
            postcode=data.get("postcode", ""),
            ward=data.get("ward", ""),
            description=data.get("description", ""),
            applicant=data.get("applicant"),
            agent=data.get("agent"),
            development_type=data.get("development_type"),
            policies=data.get("policies", []),
            received_date=data.get("received_date"),
            decision_date=data.get("decision_date"),
            outcome=data.get("outcome"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude")
        )

    def _generate_demo_applications(self) -> List[PlanningApplication]:
        """Generate demo applications for testing"""
        return [
            PlanningApplication(
                reference=f"2024/0001/P",
                address="123 Haverstock Hill, London",
                postcode="NW3 4QG",
                ward="Belsize",
                description="Single storey rear extension to provide additional living space",
                development_type="Householder",
                policies=["D1", "D2", "A1"]
            ),
            PlanningApplication(
                reference=f"2024/0002/P",
                address="45 Fitzjohns Avenue, London",
                postcode="NW3 5JY",
                ward="Frognal",
                description="Conversion of basement to habitable accommodation with front lightwell",
                development_type="Householder",
                policies=["D1", "D2", "A3"]
            )
        ]

    # Public API methods

    def add_job(self, job: MonitoringJob) -> None:
        """Add a new monitoring job"""
        self.jobs[job.id] = job
        logger.info(f"Added monitoring job: {job.name}")

    def remove_job(self, job_id: str) -> bool:
        """Remove a monitoring job"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info(f"Removed monitoring job: {job_id}")
            return True
        return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a monitoring job"""
        if job_id in self.jobs:
            self.jobs[job_id].is_active = False
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a monitoring job"""
        if job_id in self.jobs:
            self.jobs[job_id].is_active = True
            self.jobs[job_id].next_run = datetime.utcnow() + timedelta(minutes=5)
            return True
        return False

    async def run_job_now(self, job_id: str) -> bool:
        """Manually trigger a job to run immediately"""
        if job_id in self.jobs:
            await self._run_job(self.jobs[job_id])
            return True
        return False

    def get_stats(self) -> MonitoringStats:
        """Get monitoring service statistics"""
        uptime = 0
        if self._start_time:
            uptime = int((datetime.utcnow() - self._start_time).total_seconds())

        return MonitoringStats(
            total_jobs=len(self.jobs),
            active_jobs=sum(1 for j in self.jobs.values() if j.is_active),
            total_applications_processed=self.total_applications_processed,
            total_alerts_triggered=self.total_alerts_triggered,
            last_run=max(
                (j.last_run for j in self.jobs.values() if j.last_run),
                default=None
            ),
            uptime_seconds=uptime
        )

    def get_job_status(self) -> List[dict]:
        """Get status of all jobs"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "frequency": job.frequency.value,
                "source": job.source,
                "is_active": job.is_active,
                "last_run": job.last_run.isoformat() if job.last_run else None,
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "run_count": job.run_count,
                "error_count": job.error_count,
                "last_error": job.last_error
            }
            for job in self.jobs.values()
        ]
