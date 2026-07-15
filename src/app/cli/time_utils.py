class TimeUtils:
    # Format seconds → "h:mm:ss"
    def format_time(self, seconds: int | None) -> str:
        if seconds is None:
            return ""
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        if not h:
            return f"{m}:{s:02d}"
        return f"{h}:{m:02d}:{s:02d}"
