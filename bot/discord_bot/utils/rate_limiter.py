import time

_requests = {}
RATE_LIMIT_SECONDS = 5

def is_rate_limited(user_id: str) -> bool:
    last_request = _requests.get(user_id, 0)
    return time.time() - last_request < RATE_LIMIT_SECONDS

def record_request(user_id: str):
    _requests[user_id] = time.time()

def get_remaining_seconds(user_id: str) -> int:
    last_request = _requests.get(user_id, 0)
    remaining = RATE_LIMIT_SECONDS - (time.time() - last_request)
    return max(0, int(remaining))
