import ssl
import certifi

def get_ssl_context() -> ssl.SSLContext:
    """
    Xavfsiz va zamonaviy CA sertifikatlari bilan ta'minlangan SSL kontekst.
    ssl._create_unverified_context() va ssl=False o'rniga ishlatiladi.
    """
    return ssl.create_default_context(cafile=certifi.where())
