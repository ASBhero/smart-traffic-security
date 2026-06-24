import uuid


def issue_certificate(device_id):

    serial = str(uuid.uuid4())


    certificate = (
        "CERTIFICATE_FOR_" 
        + device_id
    )


    return {
        "serial":serial,
        "certificate":certificate
    }