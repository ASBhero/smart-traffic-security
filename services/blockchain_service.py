import hashlib
import json
from datetime import datetime


def create_record(data):

    payload = json.dumps(
        data,
        sort_keys=True
    )

    record_hash = hashlib.sha256(
        payload.encode()
    ).hexdigest()


    return {
        "timestamp": str(datetime.utcnow()),
        "hash": record_hash,
        "data": data
    }