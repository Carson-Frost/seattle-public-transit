"""Tab modules for Seattle Transit app."""

from tabs.performance import render as render_performance
from tabs.schedules import render as render_schedules
from tabs.actual_trips import render as render_actual_trips

__all__ = ["render_performance", "render_schedules", "render_actual_trips"]
