# Loopwise Known Issues (updated by engineering)

- **KI-101**: CSV export occasionally omits the "Assignee" column when a task has more than one assignee. Fix expected in the next release. Workaround: use JSON export instead.
- **KI-114**: Mobile app push notifications can be delayed by up to 15 minutes during peak hours (9-10am local time). Under investigation.
- **KI-120**: Time tracking entries submitted from the mobile app before app version 4.2 may show the wrong timezone. Workaround: re-submit the entry from the web app.
- **KI-122**: Bulk task move between boards can silently drop custom field values if the destination board doesn't have a matching custom field. Not a bug — expected behavior — but a common source of confusion. Recommend confirming the destination board has matching custom fields before a bulk move.
