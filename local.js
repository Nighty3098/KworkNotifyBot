require("dotenv").config();

console.log("🚀 Запуск локального монитора Kwork...");
console.log("🤖 Инициализация Telegram бота...");

if (!process.env.TELEGRAM_BOT_TOKEN) {
  console.error("❌ TELEGRAM_BOT_TOKEN не установлен в .env файле");
  process.exit(1);
}

if (!process.env.TELEGRAM_CHAT_ID) {
  console.warn(
    "⚠️ TELEGRAM_CHAT_ID не установлен. Уведомления будут отправляться только по командам.",
  );
}

require("./api/bot.js");

console.log("✅ Бот запущен в локальном режиме");
console.log("📝 Используйте команды в Telegram:");
console.log("   /monitor - запустить мониторинг");
console.log("   /stop - остановить мониторинг");
console.log("   /check - проверить сейчас");
console.log("   /status - статус мониторинга");
console.log("\n💡 Для остановки нажмите Ctrl+C");
