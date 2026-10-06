"""Pure calendar dates and day summaries; database reads belong to the workspace."""

import calendar
from collections import defaultdict
from datetime import date


def month_weeks(month):
    return calendar.Calendar(firstweekday=calendar.MONDAY).monthdatescalendar(
        month.year, month.month
    )


def renderable_month(year, month, fallback):
    """A month's padding days must also fit Python's supported date range."""
    try:
        candidate = date(int(year), int(month), 1)
        month_weeks(candidate)
    except TypeError, ValueError, OverflowError:
        return fallback
    return candidate


def shift_month(month, offset):
    month_index = month.year * 12 + month.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return renderable_month(year, zero_based_month + 1, month)


def calendar_details(month, events, *, selected_day, agenda_day, today):
    """Group already ordered events and choose the mobile agenda's initial day."""
    weeks = month_weeks(month)
    events_by_date = defaultdict(list)
    first_month_event = None
    for event in events:
        events_by_date[event.scheduled_date].append(event)
        if first_month_event is None and event.scheduled_date.replace(day=1) == month:
            first_month_event = event.scheduled_date

    visible_days = {day for week in weeks for day in week}
    if agenda_day not in visible_days:
        agenda_day = None
    default_day = first_month_event or month
    if today.replace(day=1) == month and events_by_date[today]:
        default_day = today
    mobile_day = agenda_day or selected_day or default_day

    cells = []
    for week in weeks:
        row = []
        for day in week:
            day_events = events_by_date[day]
            row.append(
                {
                    "date": day,
                    "in_month": day.month == month.month,
                    "is_today": day == today,
                    "events": day_events,
                    "first_event": day_events[0] if day_events else None,
                    "more_count": max(0, len(day_events) - 1),
                }
            )
        cells.append(row)
    return {
        "calendar_weeks": cells,
        "mobile_agenda_day": mobile_day,
        "mobile_agenda_events": events_by_date[mobile_day],
        "calendar_event_count": len(events),
    }
