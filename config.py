import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-me')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:password@localhost/ds'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # IP白名单
    ALLOWED_IPS = ['59.110.9.236', '127.0.0.1']

    # 是否跳过签名验证（测试用，生产必须为False）
    SKIP_SIGN_VERIFY = False

    # 是否跳过IP验证（测试用）
    SKIP_IP_VERIFY = False


class DevelopmentConfig(Config):
    DEBUG = True
    SKIP_SIGN_VERIFY = True
    SKIP_IP_VERIFY = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
