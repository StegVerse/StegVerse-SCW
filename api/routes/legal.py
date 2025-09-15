# add after imports
NS = os.getenv("LEGAL_NS", "v1")

# replace old constants
_EVENTS_KEY = f"legal:{NS}:events"
_REPORTS_KEY = f"legal:{NS}:reports"
