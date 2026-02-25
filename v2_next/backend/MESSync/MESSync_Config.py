from .. import config

def get_credentials() -> tuple[str, str]:
    """
    v2_next의 전역 설정(config.py)에서 계정 정보를 가져옵니다.
    """
    user_id = config.MES_USER_ID
    password = config.MES_PASSWORD
    
    if not user_id or not password:
        # We don't raise error here to allow the scheduler to handle disabled state gracefully
        # but the caller should check if enabled.
        return user_id or "", password or ""
        
    return user_id, password
