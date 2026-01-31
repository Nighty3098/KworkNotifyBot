from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🔍 Проверить сейчас")],
        [KeyboardButton(text="📊 Статус")],
    ]

    if is_admin:
        keyboard.append([KeyboardButton(text="▶️ Запустить мониторинг")])
        keyboard.append([KeyboardButton(text="⏹️ Остановить мониторинг")])
        keyboard.append([KeyboardButton(text="🔄 Прокси")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Запустить", callback_data="monitor_start"),
                InlineKeyboardButton(text="⏹️ Остановить", callback_data="monitor_stop"),
            ],
            [
                InlineKeyboardButton(text="🔍 Проверить", callback_data="check_now"),
                InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
            ],
            [InlineKeyboardButton(text="🔄 Прокси", callback_data="proxy_stats")],
        ]
    )
    return keyboard


def get_proxy_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧪 Тест всех прокси", callback_data="test_all_proxies"
                ),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_proxy"),
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
        ]
    )
    return keyboard
