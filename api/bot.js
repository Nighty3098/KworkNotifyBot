const TelegramBot = require("../lib/telegramBot");
const KworkParser = require("../lib/kworkParser");

// Проверяем, что переменные окружения установлены
if (!process.env.TELEGRAM_BOT_TOKEN || !process.env.TELEGRAM_CHAT_ID) {
  console.error("❌ Не установлены TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID");
  process.exit(1);
}

// Инициализация
const bot = new TelegramBot(
  process.env.TELEGRAM_BOT_TOKEN,
  process.env.TELEGRAM_CHAT_ID,
);

const kworkParser = new KworkParser();

// Запуск бота
bot.launch();

// Функция для проверки новых проектов
async function checkNewProjects() {
  try {
    console.log("🔍 Проверка новых проектов...");
    const newProjects = await kworkParser.getNewProjects();

    if (newProjects.length > 0) {
      console.log(`🎉 Найдено новых проектов: ${newProjects.length}`);
      await bot.sendMultipleProjects(newProjects);
    } else {
      console.log("ℹ️ Новых проектов нет");
    }

    kworkParser.cleanupOldProjects();
  } catch (error) {
    console.error("❌ Ошибка проверки проектов:", error);
  }
}

// Экспорт для Vercel
module.exports = async (req, res) => {
  if (req.method === "POST") {
    // Обработка вебхука от Telegram
    try {
      await bot.bot.handleUpdate(req.body);
      res.status(200).send("OK");
    } catch (error) {
      console.error("❌ Ошибка обработки вебхука:", error);
      res.status(500).send("Error");
    }
  } else {
    res.status(200).json({
      status: "Bot is running",
      message: "Kwork monitor bot is active",
    });
  }
};

// Для локального тестирования (только если не на Vercel)
if (process.env.VERCEL !== "1") {
  console.log("🏠 Локальный режим запуска");

  // Проверка каждые 30 секунд
  setInterval(checkNewProjects, 30000);

  // Первая проверка при запуске
  setTimeout(checkNewProjects, 5000);
}
