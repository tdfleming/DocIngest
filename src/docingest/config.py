from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    # MinIO (S3-compatible blob storage)
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "docingest"

    # FastEmbed (local embeddings)
    fastembed_model: str = "BAAI/bge-small-en-v1.5"

    # MongoDB
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_database: str = "docingest"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # Redis
    redis_url: str = "redis://redis:6379"

    # Processing
    chunk_max_tokens: int = 512
    chunk_overlap_percent: int = 10
    chunking_strategy: str = "fixed"
    embedding_batch_size: int = 100
    embedding_dimensions: int = 384

    # Rate Limiting
    default_rate_limit: int = 100

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
