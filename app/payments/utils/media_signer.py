from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

signer = TimestampSigner()

def generate_media_token(path: str) -> str:
    """
    Gera token assinado e temporário para acesso ao arquivo
    """
    return signer.sign(path)


def unsign_media_token(token: str, max_age: int = 300) -> str:
    """
    Valida token e retorna o path original
    max_age em segundos (ex: 300 = 5 min)
    """
    return signer.unsign(token, max_age=max_age)
