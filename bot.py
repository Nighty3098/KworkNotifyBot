import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from config import config
from database import db
from keyboards import get_admin_keyboard, get_main_keyboard, get_proxy_keyboard
from models import ProcessedProject, User
from parser import KworkParser
from proxy_manager import ProxyManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

monitoring_active: Dict[int, bool] = {}  # chat_id -> is_active
monitoring_tasks: Dict[int, str] = {}  # chat_id -> task_id

proxy_manager = None
if config.PROXY_STRING:
    try:
        proxy_manager = ProxyManager(config.PROXY_STRING)
        logger.info(
            f"✅ Менеджер прокси инициализирован с {len(proxy_manager.proxies)} прокси"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации менеджера прокси: {e}")
        proxy_manager = None
else:
    logger.warning("⚠️ Прокси не настроены, используется прямое подключение")


async def init_database_with_retry(max_retries: int = 5, delay: int = 5) -> bool:
    for attempt in range(max_retries):
        try:
            logger.info(f"🚀 Попытка подключения к БД ({attempt + 1}/{max_retries})...")
            db.init_db()
            logger.info("✅ База данных успешно инициализирована")
            return True
        except OperationalError as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            if attempt < max_retries - 1:
                logger.info(f"⏳ Ожидание {delay} секунд перед повторной попыткой...")
                await asyncio.sleep(delay)
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при инициализации БД: {e}")
            return False

    logger.error("❌ Не удалось подключиться к базе данных после всех попыток")
    return False


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    try:
        db.add_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        is_admin = db.is_user_admin(message.from_user.id)

        welcome_text = """🚀 <b>Бот для мониторинга Kwork с поддержкой прокси</b>

Я буду отслеживать новые проекты на Kwork через ротацию прокси и присылать вам уведомления.

<b>Основные команды:</b>
/monitor - запустить мониторинг
/stop - остановить мониторинг
/check - проверить сейчас
/status - статус мониторинга
/proxy - управление прокси
/help - справка

<b>Используйте кнопки ниже для управления:</b>"""

        await message.answer(welcome_text, reply_markup=get_main_keyboard(is_admin))

        logger.info(
            f"👤 Новый пользователь: {message.from_user.username or message.from_user.id}"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в команде /start: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке команды. Попробуйте позже."
        )


@dp.message(Command("proxy"))
@dp.message(F.text == "🔄 Прокси")
async def cmd_proxy(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔ <b>Эта команда доступна только администраторам</b>")
        return

    if not proxy_manager:
        await message.answer(
            "⚠️ <b>Менеджер прокси не инициализирован</b>\n\n"
            "Проверьте настройки в .env файле"
        )
        return

    try:
        stats = proxy_manager.get_stats()

        stats_text = f"""🔧 <b>Статистика прокси</b>

📊 <b>Общая статистика:</b>
• Всего прокси: {stats["total_proxies"]}
• Активных: {stats["active_proxies"]}
• Всего запросов: {stats["total_requests"]}
• Успешных: {stats["success_rate"]}%

📋 <b>Список прокси:</b>"""

        for i, proxy_info in enumerate(stats["proxies"][:10], 1):
            proxy_stats = proxy_info["stats"]
            status = "🟢" if proxy_stats["is_active"] else "🔴"
            stats_text += f"\n{i}. {status} {proxy_info['original'][:50]}..."
            stats_text += f"\n   Запросы: {proxy_stats['total_requests']}/{config.MAX_REQUESTS_PER_PROXY}"
            stats_text += (
                f" (✓{proxy_stats['success_count']} ✗{proxy_stats['fail_count']})"
            )

        if len(stats["proxies"]) > 10:
            stats_text += f"\n\n... и еще {len(stats['proxies']) - 10} прокси"

        await message.answer(
            stats_text, reply_markup=get_proxy_keyboard(), disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики прокси: {e}")
        await message.answer("❌ <b>Ошибка при получении статистики прокси</b>")


@dp.message(F.text == "🧪 Тест прокси")
async def cmd_test_proxy(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔ <b>Эта команда доступна только администраторам</b>")
        return

    if not proxy_manager:
        await message.answer("⚠️ <b>Менеджер прокси не инициализирован</b>")
        return

    await message.answer("🧪 <b>Начинаю тестирование прокси...</b>")

    try:
        test_results = []
        total_proxies = len(proxy_manager.proxies)

        for i, proxy in enumerate(proxy_manager.proxies, 1):
            await message.edit_text(f"🧪 Тестирую прокси {i}/{total_proxies}...")

            is_working = await proxy_manager.test_proxy(proxy, config.PROXY_TEST_URL)
            status = "✅" if is_working else "❌"

            test_results.append(
                {
                    "proxy": proxy.get("host", "unknown"),
                    "status": status,
                    "working": is_working,
                }
            )

            if is_working:
                proxy_manager.mark_success(proxy["url"])
            else:
                proxy_manager.mark_failure(proxy["url"])

            await asyncio.sleep(1)

        working_count = sum(1 for r in test_results if r["working"])

        report_text = f"""📋 <b>Результаты тестирования прокси</b>

✅ Работающих: {working_count}/{total_proxies}
❌ Не работающих: {total_proxies - working_count}

<b>Детали:</b>"""

        for result in test_results[:15]:  # Показываем первые 15
            report_text += f"\n{result['status']} {result['proxy']}"

        if len(test_results) > 15:
            report_text += f"\n\n... и еще {len(test_results) - 15} прокси"

        await message.answer(report_text)

    except Exception as e:
        logger.error(f"❌ Ошибка тестирования прокси: {e}")
        await message.answer("❌ <b>Ошибка при тестировании прокси</b>")


# Команда /monitor
@dp.message(Command("monitor"))
@dp.message(F.text == "▶️ Запустить мониторинг")
async def cmd_monitor(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔ <b>Эта команда доступна только администраторам</b>")
        return

    chat_id = message.chat.id

    if monitoring_active.get(chat_id):
        await message.answer("🔍 <b>Мониторинг уже запущен в этом чате!</b>")
        return

    try:
        monitoring_active[chat_id] = True

        task_id = f"monitor_{chat_id}"
        scheduler.add_job(
            check_new_projects,
            "interval",
            seconds=config.CHECK_INTERVAL,
            args=[chat_id],
            id=task_id,
            replace_existing=True,
        )

        monitoring_tasks[chat_id] = task_id

        proxy_info = ""
        if proxy_manager:
            stats = proxy_manager.get_stats()
            proxy_info = f"\n• Прокси: {stats['active_proxies']}/{stats['total_proxies']} активны"

        await message.answer(
            f"🔍 <b>Мониторинг запущен!</b>\n\n"
            f"• Проверка каждые: {config.CHECK_INTERVAL} секунд\n"
            f"• Чат ID: {chat_id}"
            f"{proxy_info}\n\n"
            f"<i>Первая проверка...</i>",
            reply_markup=get_admin_keyboard(),
        )

        logger.info(f"▶️ Мониторинг запущен для чата {chat_id}")

        await check_new_projects(chat_id, manual=True)

    except Exception as e:
        logger.error(f"❌ Ошибка запуска мониторинга: {e}")
        await message.answer("❌ <b>Ошибка при запуске мониторинга</b>")


@dp.message(Command("stop"))
@dp.message(F.text == "⏹️ Остановить мониторинг")
async def cmd_stop(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔ <b>Эта команда доступна только администраторам</b>")
        return

    chat_id = message.chat.id

    if not monitoring_active.get(chat_id):
        await message.answer("ℹ️ <b>Мониторинг не запущен в этом чате</b>")
        return

    try:
        monitoring_active[chat_id] = False

        task_id = monitoring_tasks.get(chat_id)
        if task_id and scheduler.get_job(task_id):
            scheduler.remove_job(task_id)
            del monitoring_tasks[chat_id]

        await message.answer("🛑 <b>Мониторинг остановлен</b>")
        logger.info(f"⏹️ Мониторинг остановлен для чата {chat_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка остановки мониторинга: {e}")
        await message.answer("❌ <b>Ошибка при остановке мониторинга</b>")


@dp.message(Command("check"))
@dp.message(F.text == "🔍 Проверить сейчас")
async def cmd_check(message: types.Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("⛔ <b>Эта команда доступна только администраторам</b>")
        return

    chat_id = message.chat.id
    await message.answer("🔍 <b>Проверяю новые проекты...</b>")

    try:
        await check_new_projects(chat_id, manual=True)
    except Exception as e:
        logger.error(f"❌ Ошибка при ручной проверке: {e}")
        await message.answer("❌ <b>Ошибка при проверке проектов</b>")


@dp.message(Command("status"))
@dp.message(F.text == "📊 Статус")
async def cmd_status(message: types.Message):
    chat_id = message.chat.id
    is_admin = message.from_user.id in config.ADMIN_IDS

    try:
        with db.get_session() as session:
            projects_count = session.query(ProcessedProject).count()

        proxy_info = ""
        if proxy_manager and is_admin:
            stats = proxy_manager.get_stats()
            proxy_info = f"\n• <b>Прокси:</b> {stats['active_proxies']}/{stats['total_proxies']} активны"
            proxy_info += f"\n• <b>Успешность:</b> {stats['success_rate']}%"

        status_text = f"""📊 <b>Статус мониторинга</b>

• <b>Мониторинг:</b> {"🟢 Активен" if monitoring_active.get(chat_id) else "🔴 Остановлен"}
• <b>Обработано проектов:</b> {projects_count}
• <b>Администратор:</b> {"✅ Да" if is_admin else "❌ Нет"}
• <b>ID чата:</b> <code>{chat_id}</code>{proxy_info}"""

        if is_admin:
            status_text += (
                f"\n• <b>Интервал проверки:</b> {config.CHECK_INTERVAL} секунд"
            )
            status_text += (
                f"\n• <b>ID пользователя:</b> <code>{message.from_user.id}</code>"
            )

        await message.answer(status_text)

    except Exception as e:
        logger.error(f"❌ Ошибка получения статуса: {e}")
        await message.answer("❌ <b>Ошибка при получении статуса</b>")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """📚 <b>Справка по командам</b>

<b>Основные команды:</b>
/start - Запустить бота
/help - Показать эту справку
/status - Статус мониторинга

<b>Команды для администраторов:</b>
/monitor - Запустить мониторинг
/stop - Остановить мониторинг
/check - Проверить проекты сейчас
/proxy - Управление прокси

<b>Как работает бот:</b>
1. Бот проверяет новые проекты на Kwork через ротацию прокси
2. Каждый прокси используется для 6 запросов
3. При обнаружении нового проекта отправляется уведомление
4. Проверка происходит каждые 2 минуты (или установленный интервал)
5. Проекты хранятся в базе данных для отслеживания дубликатов

<b>Настройка прокси:</b>
• Прокси настраиваются в файле .env
• Поддерживаются Shadowsocks, HTTP и SOCKS5 прокси
• Автоматическая проверка работоспособности прокси

Для начала работы запустите мониторинг командой /monitor"""

    await message.answer(help_text)


@dp.callback_query(F.data == "monitor_start")
async def callback_monitor_start(callback: types.CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    if monitoring_active.get(callback.message.chat.id):
        await callback.answer("🔍 Мониторинг уже запущен!", show_alert=True)
        return

    await cmd_monitor(callback.message)
    await callback.answer("✅ Мониторинг запущен")


@dp.callback_query(F.data == "monitor_stop")
async def callback_monitor_stop(callback: types.CallbackQuery):
    """Обработка остановки мониторинга через inline кнопку"""
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    await cmd_stop(callback.message)
    await callback.answer("✅ Мониторинг остановлен")


@dp.callback_query(F.data == "check_now")
async def callback_check_now(callback: types.CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("⛔ Доступно только админам", show_alert=True)
        return

    await cmd_check(callback.message)
    await callback.answer("✅ Проверка выполнена")


@dp.callback_query(F.data == "stats")
async def callback_stats(callback: types.CallbackQuery):
    await cmd_status(callback.message)
    await callback.answer()


async def send_project_notification(chat_id: int, project: Dict[str, Any]):
    try:
        message = f"""🎯 <b>НОВЫЙ ПРОЕКТ НА KWORK</b>

🏷️ <b>{project["title"]}</b>

💰 <b>{project["price"]}</b>
👤 <b>{project["username"]}</b>
⏰ <b>{project["time_left"]}</b>

📝 {project["description"]}

🔗 <a href="{project["url"]}">Открыть проект</a>"""

        await bot.send_message(chat_id, message, disable_web_page_preview=False)

        logger.info(f"✅ Уведомление отправлено: {project['title'][:50]}...")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления: {e}")
        return False


async def check_new_projects(chat_id: int, manual: bool = False):
    try:
        logger.info(
            f"🔍 Проверка проектов для чата {chat_id} {'(ручная)' if manual else '(автоматическая)'}"
        )

        parser = KworkParser(proxy_manager)

        async with parser as p:
            all_projects = await p.get_projects()

        if not all_projects:
            logger.warning("⚠️ Не удалось получить проекты с Kwork")
            if manual:
                await bot.send_message(
                    chat_id, "⚠️ <b>Не удалось получить проекты с Kwork</b>"
                )
            return

        logger.info(f"📊 Получено проектов с Kwork: {len(all_projects)}")

        new_projects = []
        for project in all_projects:
            if not db.is_processed(project["id"]):
                new_projects.append(project)
                db.mark_processed(project["id"], project["title"], project["price"])

        db.cleanup_old_projects(config.MAX_PROCESSED_PROJECTS)

        if new_projects:
            logger.info(f"🎉 Найдено новых проектов: {len(new_projects)}")

            if manual:
                await bot.send_message(
                    chat_id, f"🎉 <b>Найдено новых проектов: {len(new_projects)}</b>"
                )

            for i, project in enumerate(new_projects, 1):
                success = await send_project_notification(chat_id, project)
                if success and i < len(new_projects):  # Задержка между отправками
                    await asyncio.sleep(1)

            logger.info(f"✅ Отправлено уведомлений: {len(new_projects)}")

        elif manual:
            await bot.send_message(chat_id, "ℹ️ <b>Новых проектов нет</b>")
            logger.info("ℹ️ Новых проектов не найдено")

    except Exception as e:
        logger.error(f"❌ Ошибка проверки проектов: {e}")
        if manual:
            await bot.send_message(chat_id, "❌ <b>Ошибка при проверке проектов</b>")


@dp.message()
async def handle_unknown_message(message: types.Message):
    if message.text:
        await message.answer(
            "🤖 <b>Используйте команды или кнопки для управления ботом</b>\n\n"
            "Для списка команд отправьте /help",
            reply_markup=get_main_keyboard(message.from_user.id in config.ADMIN_IDS),
        )


@dp.error()
async def error_handler(event: types.ErrorEvent, **kwargs):
    logger.error(f"❌ Глобальная ошибка: {event.exception}")
    logger.error(f"Контекст ошибки: {event.update}")

    if config.ADMIN_IDS:
        admin_id = config.ADMIN_IDS[0]
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ <b>Произошла ошибка в боте:</b>\n\n<code>{str(event.exception)[:1000]}</code>",
            )
        except:
            pass


async def main():
    try:
        logger.info("🚀 Запуск бота для мониторинга Kwork...")

        if not config.BOT_TOKEN:
            logger.error("❌ Токен бота не указан в переменных окружения")
            return

        logger.info("🔧 Инициализация базы данных...")
        if not await init_database_with_retry():
            logger.error("❌ Критическая ошибка: не удалось подключиться к базе данных")
            return

        scheduler.start()
        logger.info(f"📅 Планировщик запущен (интервал: {config.CHECK_INTERVAL} сек)")

        await bot.delete_webhook(drop_pending_updates=True)

        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_info.username} (ID: {bot_info.id})")
        logger.info(f"👑 Администраторы: {config.ADMIN_IDS}")

        if proxy_manager:
            stats = proxy_manager.get_stats()
            logger.info(f"🔧 Загружено прокси: {stats['total_proxies']}")
        else:
            logger.warning("⚠️ Работа без прокси")

        logger.info("✅ Бот готов к работе. Ожидание сообщений...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
    finally:
        logger.info("🛑 Завершение работы бота...")
        scheduler.shutdown()

        for task_id in list(monitoring_tasks.values()):
            if scheduler.get_job(task_id):
                scheduler.remove_job(task_id)

        logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    import os

    os.makedirs("logs", exist_ok=True)

    asyncio.run(main())
