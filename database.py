import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker

from config import config
from models import Base, MonitoringSettings, ProcessedProject, User

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        try:
            logger.info(
                f"Подключение к базе данных: {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
            )
            database_url = f"postgresql://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
            logger.info(
                f"URL подключения: {database_url.replace(config.DB_PASSWORD, '***')}"
            )

            self.engine = create_engine(
                database_url, pool_pre_ping=True, pool_recycle=3600, echo=False
            )
            self.SessionLocal = sessionmaker(
                autocommit=False, autoflush=False, bind=self.engine
            )
            self.Session = scoped_session(self.SessionLocal)

        except Exception as e:
            logger.error(f"Ошибка при создании подключения к БД: {e}")
            raise

    def init_db(self):
        try:
            logger.info("Создание таблиц в базе данных...")
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ Таблицы успешно созданы")
        except SQLAlchemyError as e:
            logger.error(f"❌ Ошибка создания таблиц: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при создании таблиц: {e}")
            raise

    @contextmanager
    def get_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка в сессии БД: {e}")
            raise
        finally:
            session.close()

    def add_user(
        self,
        user_id: int,
        username: str = None,
        first_name: str = None,
        last_name: str = None,
    ):
        with self.get_session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.is_active = True
                user.is_admin = user_id in config.ADMIN_IDS
            else:
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=user_id in config.ADMIN_IDS,
                )
                session.add(user)

    def is_user_admin(self, user_id: int) -> bool:
        with self.get_session() as session:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                return user.is_admin
            else:
                return user_id in config.ADMIN_IDS

    def is_processed(self, project_id: str) -> bool:
        with self.get_session() as session:
            return (
                session.query(ProcessedProject).filter_by(project_id=project_id).first()
                is not None
            )

    def mark_processed(self, project_id: str, title: str = None, price: str = None):
        with self.get_session() as session:
            if not self.is_processed(project_id):
                project = ProcessedProject(
                    project_id=project_id, title=title, price=price
                )
                session.add(project)

    def cleanup_old_projects(self, max_count: int = 1000):
        with self.get_session() as session:
            count = session.query(ProcessedProject).count()
            if count > max_count:
                to_delete = count - max_count
                oldest = (
                    session.query(ProcessedProject)
                    .order_by(ProcessedProject.created_at)
                    .limit(to_delete)
                    .all()
                )
                for project in oldest:
                    session.delete(project)
                logger.info(f"Очищено {len(oldest)} старых проектов")


db = Database()
