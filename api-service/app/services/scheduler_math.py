"""
Scheduler math utilities for calculating time intervals and next run times
"""
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from random import randint
from typing import Optional

from ..db.models import FrequencyUnit, SchedulerJob


def now_utc() -> datetime:
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)


def compute_approx_seconds(unit: FrequencyUnit, value: int) -> Optional[int]:
    """
    Compute approximate interval in seconds for a frequency unit and value.
    Returns None for months since they vary in length.
    
    Args:
        unit: The frequency unit (minute, hour, day, week, month)
        value: The frequency value (e.g., 5 for "5 minutes")
        
    Returns:
        Approximate seconds or None for months
    """
    if unit == FrequencyUnit.MINUTE:
        return value * 60
    if unit == FrequencyUnit.HOUR:
        return value * 3600
    if unit == FrequencyUnit.DAY:
        return value * 86400
    if unit == FrequencyUnit.WEEK:
        return value * 7 * 86400
    if unit == FrequencyUnit.MONTH:
        return None  # months vary; keep None or use 30*86400 for rough stats
    return None


def add_interval(dt: datetime, unit: FrequencyUnit, value: int) -> datetime:
    """
    Add a time interval to a datetime based on frequency unit and value.
    
    Args:
        dt: Base datetime to add interval to
        unit: The frequency unit
        value: The frequency value
        
    Returns:
        New datetime with interval added
        
    Raises:
        ValueError: If unit is unknown
    """
    if unit == FrequencyUnit.MINUTE:
        return dt + timedelta(minutes=value)
    if unit == FrequencyUnit.HOUR:
        return dt + timedelta(hours=value)
    if unit == FrequencyUnit.DAY:
        return dt + timedelta(days=value)
    if unit == FrequencyUnit.WEEK:
        return dt + timedelta(weeks=value)
    if unit == FrequencyUnit.MONTH:
        return dt + relativedelta(months=+value)
    raise ValueError(f"Unknown frequency unit: {unit}")


def next_fire_time(job: SchedulerJob, *, from_dt: Optional[datetime] = None) -> datetime:
    """
    Calculate the next fire time for a scheduler job with optional jitter.
    
    Args:
        job: The scheduler job to calculate next fire time for
        from_dt: Base datetime to calculate from (defaults to current UTC time)
        
    Returns:
        Next scheduled fire time with jitter applied
    """
    base = from_dt or now_utc()
    
    # Parse the frequency unit from string
    freq_unit = FrequencyUnit(job.freq_unit)
    
    # Calculate next time based on frequency
    next_time = add_interval(base, freq_unit, job.freq_value)
    
    # Apply jitter if configured
    jitter_seconds = job.jitter_seconds
    if jitter_seconds > 0:
        jitter = randint(-jitter_seconds, jitter_seconds)
        next_time = next_time + timedelta(seconds=jitter)
    
    return next_time


def calculate_next_run_with_backoff(job: SchedulerJob, base_delay_seconds: int = 60) -> datetime:
    """
    Calculate next run time with exponential backoff for failed jobs.
    
    Args:
        job: The scheduler job that failed
        base_delay_seconds: Base delay in seconds for first failure
        
    Returns:
        Next run time with backoff applied
    """
    # Exponential backoff: base_delay * 2^failures, capped at 1 hour
    backoff_seconds = min(
        base_delay_seconds * (2 ** job.consecutive_failures),
        3600  # Cap at 1 hour
    )
    
    return now_utc() + timedelta(seconds=backoff_seconds)


def is_job_due(job: SchedulerJob, current_time: Optional[datetime] = None) -> bool:
    """
    Check if a scheduler job is due to run.
    
    Args:
        job: The scheduler job to check
        current_time: Current time to check against (defaults to UTC now)
        
    Returns:
        True if the job is due to run
    """
    if not job.enabled:
        return False
    
    current = current_time or now_utc()
    return job.next_run_at <= current


def is_job_locked(job: SchedulerJob, current_time: Optional[datetime] = None) -> bool:
    """
    Check if a scheduler job is currently locked.
    
    Args:
        job: The scheduler job to check
        current_time: Current time to check against (defaults to UTC now)
        
    Returns:
        True if the job is locked
    """
    if not job.locked_until:
        return False
    
    current = current_time or now_utc()
    return job.locked_until > current


def get_execution_duration_ms(started_at: datetime, completed_at: Optional[datetime] = None) -> Optional[int]:
    """
    Calculate execution duration in milliseconds.
    
    Args:
        started_at: When execution started
        completed_at: When execution completed (defaults to current time)
        
    Returns:
        Duration in milliseconds or None if not completed
    """
    if not completed_at:
        completed_at = now_utc()
    
    # Ensure both datetimes have timezone info for proper subtraction
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    
    duration = completed_at - started_at
    return int(duration.total_seconds() * 1000)