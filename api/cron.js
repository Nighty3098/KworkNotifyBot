const KworkParser = require("../lib/kworkParser");
const TelegramBot = require("../lib/telegramBot");

const bot = new TelegramBot(
  process.env.TELEGRAM_BOT_TOKEN,
  process.env.TELEGRAM_CHAT_ID,
);

const kworkParser = new KworkParser();

module.exports = async (req, res) => {
  try {
    console.log("⏰ CRON: Запуск проверки проектов...");

    const newProjects = await kworkParser.getNewProjects();

    if (newProjects.length > 0) {
      console.log(`🎉 CRON: Найдено новых проектов: ${newProjects.length}`);
      await bot.sendMultipleProjects(newProjects);

      res.status(200).json({
        status: "success",
        message: `Found ${newProjects.length} new projects`,
        projects: newProjects.length,
      });
    } else {
      console.log("ℹ️ CRON: Новых проектов нет");
      res.status(200).json({
        status: "success",
        message: "No new projects found",
        projects: 0,
      });
    }

    kworkParser.cleanupOldProjects();
  } catch (error) {
    console.error("❌ CRON: Ошибка:", error);
    res.status(500).json({
      status: "error",
      message: error.message,
    });
  }
};
