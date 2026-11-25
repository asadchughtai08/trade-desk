import time  # waqt ke liye
from collections import deque  # tez queue
from datetime import date  # aaj ki tareekh


class Limits:
    """Simple in-memory rate limit (per key, per minute) and daily LLM call cap."""

    def __init__(self, per_minute=10, daily_calls=300):
        self.per_minute = per_minute  # ek minute mein kitni requests
        self.daily_calls = daily_calls  # ek din mein kitni model calls
        self.times = {}  # key -> pichli requests ka waqt
        self.day = date.today()  # aaj ka din
        self.used = 0  # aaj kitni calls hui

    def rate_ok(self, key):
        """Return True if this key is under the per-minute limit (and count it)."""
        now = time.time()  # abhi ka waqt
        queue = self.times.setdefault(key, deque())  # is key ki queue
        while queue and now - queue[0] > 60:  # 60 second se purani hatao
            queue.popleft()  # hatao
        if len(queue) >= self.per_minute:  # limit poori
            return False  # mana karo
        queue.append(now)  # nayi request likho
        return True  # ijazat

    def _new_day_check(self):
        """Reset the daily counter when the date changes."""
        if date.today() != self.day:  # din badal gaya
            self.day = date.today()  # naya din
            self.used = 0  # counter zero

    def daily_ok(self):
        """Return True if today's LLM call cap is not reached."""
        self._new_day_check()  # din check karo
        return self.used < self.daily_calls  # cap se kam hai?

    def add_calls(self, n):
        """Add n LLM calls to today's counter."""
        self._new_day_check()  # din check karo
        self.used += n  # calls jama karo
