import hashlib
import json
from datetime import datetime


blockchain = []


def add_block(data):

    block = {
        "timestamp": str(datetime.utcnow()),
        "data": data
    }


    block_string = json.dumps(
        block,
        sort_keys=True
    )


    block["hash"] = hashlib.sha256(
        block_string.encode()
    ).hexdigest()


    blockchain.append(block)


    return block