import requests


class HSMClient:


    def __init__(self):

        self.base_url = "https://hsm-server/api"



    def sign_data(self, data):

        # later replaced with real HSM API call

        response = requests.post(
            f"{self.base_url}/sign",
            json={
                "data": data
            }
        )

        return response.json()



    def generate_key(self):

        response = requests.post(
            f"{self.base_url}/keys/generate"
        )

        return response.json()



    def issue_certificate(self, csr):

        response = requests.post(
            f"{self.base_url}/certificate/issue",
            json={
                "csr": csr
            }
        )

        return response.json()
    