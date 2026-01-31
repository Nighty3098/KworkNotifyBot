import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS = [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ]

    DB_HOST = os.getenv("DB_HOST", "postgres")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "kwork_bot")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "600"))
    MAX_PROCESSED_PROJECTS = int(os.getenv("MAX_PROCESSED_PROJECTS", "1000"))

    PROXY_STRING = os.getenv("PROXY_STRING", "")
    MAX_REQUESTS_PER_PROXY = int(os.getenv("MAX_REQUESTS_PER_PROXY", "6"))
    PROXY_TEST_URL = os.getenv("PROXY_TEST_URL", "https://api.ipify.org?format=json")
    PROXY_TIMEOUT = int(os.getenv("PROXY_TIMEOUT", "10"))

    @property
    def DATABASE_URL(self):
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


config = Config()
