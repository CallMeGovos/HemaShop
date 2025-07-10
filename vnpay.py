class VNPay:
    def __init__(self):
        self.requestData = {}

    def get_payment_url(self, payment_url, hash_secret_key):
        import hmac
        import hashlib
        import urllib.parse

        params = sorted(self.requestData.items())
        querystring = urllib.parse.urlencode(params)
        sign_data = querystring + "|" + hash_secret_key
        vnp_SecureHash = hmac.new(
            hash_secret_key.encode(),
            sign_data.encode(),
            hashlib.sha512
        ).hexdigest()
        return f"{payment_url}?{querystring}&vnp_SecureHash={vnp_SecureHash}"


vnpay = VNPay()
