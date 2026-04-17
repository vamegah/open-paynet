from shared.config import env_float, env_int, env_text, load_json_config, load_secret, parse_api_keys


class Settings:
    KAFKA_BOOTSTRAP_SERVERS = env_text("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_PAYMENT_TOPIC = "payment-initiated"
    REDIS_URL = env_text("REDIS_URL", "redis://localhost:6379")
    JWT_SECRET = load_secret("JWT_SECRET", default="supersecret")
    JWT_ISSUER = env_text("JWT_ISSUER", "openpaynet-auth")
    JWT_AUDIENCE = env_text("JWT_AUDIENCE", "openpaynet-api")
    TOKENIZATION_SECRET = load_secret("TOKENIZATION_SECRET", default="tokenization-secret")
    MERCHANT_CREDENTIALS = load_json_config("MERCHANT_CREDENTIALS_JSON", default={})
    LEGACY_MERCHANT_API_KEYS = env_text("MERCHANT_API_KEYS", "")
    RATE_LIMIT_REQUESTS = 10
    RATE_LIMIT_PERIOD = 60
    EVENT_PUBLISH_TIMEOUT_SECONDS = env_float("EVENT_PUBLISH_TIMEOUT_SECONDS", 2.0)
    CIRCUIT_BREAKER_FAILURE_THRESHOLD = env_int("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 3)
    CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS = env_float("CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", 15.0)

    @classmethod
    def merchant_credentials(cls) -> dict[str, dict]:
        credentials = dict(cls.MERCHANT_CREDENTIALS)
        if not credentials and cls.LEGACY_MERCHANT_API_KEYS:
            credentials = parse_api_keys(cls.LEGACY_MERCHANT_API_KEYS)
        return credentials


settings = Settings()
