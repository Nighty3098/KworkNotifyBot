require("dotenv").config();
const TelegramBot = require("./lib/telegramBot");
const KworkParser = require("./lib/kworkParser");

class LocalMonitor {
  constructor() {
    this.bot = new TelegramBot(
      process.env.TELEGRAM_BOT_TOKEN,
      process.env.TELEGRAM_CHAT_ID,
    );
    this.kworkParser = new KworkParser();
    this.isMonitoring = false;
    this.intervalId = null;
  }

  async init() {
    console.log("🚀 Запуск локального монитора Kwork...");

    // Запускаем Telegram бота
    this.bot.launch();

    // Обработка команды /stop для локального режима
    this.bot.bot.command("stop", (ctx) => {
      if (this.isMonitoring) {
        this.stopMonitoring();
        ctx.reply("🛑 Мониторинг остановлен");
      } else {
        ctx.reply("ℹ️ Мониторинг не запущен");
      }
    });

    // Обработка команды /start_monitor
    this.bot.bot.command("start_monitor", (ctx) => {
      if (!this.isMonitoring) {
        this.startMonitoring();
        ctx.reply("🔍 Мониторинг запущен (локальный режим)");
      } else {
        ctx.reply("ℹ️ Мониторинг уже запущен");
      }
    });

    // Обработка команды /check_now
    this.bot.bot.command("check_now", async (ctx) => {
      ctx.reply("🔍 Проверяю новые проекты...");
      await this.checkProjects();
    });

    // Обработка команды /status
    this.bot.bot.command("status", (ctx) => {
      const status = this.isMonitoring ? "активен" : "остановлен";
      ctx.reply(
        `📊 Статус мониторинга: ${status}\nОбработано проектов: ${this.kworkParser.processedProjects.size}`,
      );
    });
  }

  async checkProjects() {
    try {
      console.log("🔍 Проверка новых проектов...");
      const newProjects = await this.kworkParser.getNewProjects();

      if (newProjects.length > 0) {
        console.log(`🎉 Найдено новых проектов: ${newProjects.length}`);
        await this.bot.sendMultipleProjects(newProjects);

        // Отправляем отчет в Telegram
        await this.bot.bot.telegram.sendMessage(
          process.env.TELEGRAM_CHAT_ID,
          `📊 Проверка завершена. Найдено новых проектов: ${newProjects.length}`,
        );
      } else {
        console.log("ℹ️ Новых проектов нет");
      }

      this.kworkParser.cleanupOldProjects();
      return newProjects.length;
    } catch (error) {
      console.error("❌ Ошибка проверки проектов:", error);
      return 0;
    }
  }

  startMonitoring(interval = 30000) {
    if (this.isMonitoring) {
      console.log("ℹ️ Мониторинг уже запущен");
      return;
    }

    this.isMonitoring = true;
    console.log(`🔍 Запуск мониторинга с интервалом ${interval / 1000} секунд`);

    // Первая проверка сразу
    this.checkProjects();

    // Последующие проверки по интервалу
    this.intervalId = setInterval(async () => {
      await this.checkProjects();
    }, interval);

    // Уведомление в Telegram
    this.bot.bot.telegram.sendMessage(
      process.env.TELEGRAM_CHAT_ID,
      `🔍 Локальный мониторинг Kwork запущен!\nИнтервал проверки: ${interval / 1000} секунд`,
    );
  }

  stopMonitoring() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.isMonitoring = false;
    console.log("🛑 Мониторинг остановлен");

    // Уведомление в Telegram
    this.bot.bot.telegram.sendMessage(
      process.env.TELEGRAM_CHAT_ID,
      "🛑 Мониторинг остановлен",
    );
  }

  async runOnce() {
    console.log("🔍 Единоразовая проверка проектов...");
    await this.bot.init();
    const count = await this.checkProjects();
    console.log(`✅ Проверка завершена. Найдено проектов: ${count}`);
    process.exit(0);
  }

  async runMonitor() {
    await this.init();
    this.startMonitoring(30000); // 30 секунд

    // Обработка graceful shutdown
    process.on("SIGINT", () => {
      console.log("\n🛑 Получен SIGINT. Останавливаю мониторинг...");
      this.stopMonitoring();
      process.exit(0);
    });

    process.on("SIGTERM", () => {
      console.log("\n🛑 Получен SIGTERM. Останавливаю мониторинг...");
      this.stopMonitoring();
      process.exit(0);
    });

    console.log(
      "✅ Локальный мониторинг запущен. Нажмите Ctrl+C для остановки.",
    );
  }
}

// Запуск в зависимости от аргументов командной строки
const args = process.argv.slice(2);
const monitor = new LocalMonitor();

if (args.includes("--once")) {
  monitor.runOnce();
} else if (args.includes("--monitor")) {
  monitor.runMonitor();
} else {
  // Режим по умолчанию - интерактивный
  monitor.runMonitor();
}
