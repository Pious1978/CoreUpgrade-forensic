import datetime

class MarketCalendar:
    @staticmethod
    def is_session(date_obj: datetime.date) -> bool:
        """Verify if a given date is an active trading session (excludes weekends and official exchange holidays)."""
        if date_obj.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Official Indian Exchange Holidays (Sample for 2026)
        holidays = {
            datetime.date(2026, 1, 26),
            datetime.date(2026, 4, 14),
            datetime.date(2026, 5, 1),
            datetime.date(2026, 8, 15),
            datetime.date(2026, 10, 2),
            datetime.date(2026, 12, 25),
        }
        return date_obj not in holidays
