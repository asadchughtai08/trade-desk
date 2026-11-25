import json  # JSON log ke liye
from datetime import datetime, timezone  # waqt ke liye
from utils import mask_text  # private data chhupane ke liye


def log_event(**fields):
    """Print one structured JSON log line. Text values are masked."""
    line = {"time": datetime.now(timezone.utc).isoformat()}  # waqt sab se pehle
    for key, value in fields.items():  # har field ke liye
        line[key] = mask_text(value) if isinstance(value, str) else value  # text ho to mask karo
    print(json.dumps(line), flush=True)  # ek line print karo
