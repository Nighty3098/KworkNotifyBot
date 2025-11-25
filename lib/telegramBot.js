const { Telegraf } = require("telegraf");

class TelegramBot {
  constructor(token, chatId) {
    this.bot = new Telegraf(token);
    this.chatId = chatId;
    this.setupHandlers();
  }

  setupHandlers() {
    this.bot.start((ctx) => {
      ctx.reply(
        "🚀 Бот для мониторинга Kwork запущен!\n\nЯ буду присылать уведомления о новых проектах.",
      );
    });

    this.bot.command("check", async (ctx) => {
      ctx.reply("🔍 Проверяю новые проекты...");
    });

    this.bot.command("stats", (ctx) => {
      ctx.reply(
        "📊 Бот работает в режиме мониторинга.\nНовые проекты приходят автоматически.",
      );
    });
  }

  async sendProjectNotification(project) {
    try {
      const message = `
🎯 *НОВЫЙ ПРОЕКТ НА KWORK*

🏷️ *${project.title}*

💰 *${project.price}*
👤 *${project.username}*
⏰ *${project.time_left}*

📝 ${project.description}

🔗 [Открыть проект](${project.url})
            `.trim();

      await this.bot.telegram.sendMessage(this.chatId, message, {
        parse_mode: "Markdown",
        disable_web_page_preview: false,
      });

      console.log(`✅ Уведомление отправлено: ${project.title}`);
      return true;
    } catch (error) {
      console.error("❌ Ошибка отправки уведомления:", error);
      return false;
    }
  }

  async sendMultipleProjects(projects) {
    for (const project of projects) {
      await this.sendProjectNotification(project);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  launch() {
    this.bot.launch();
    console.log("🤖 Telegram бот запущен");
  }
}

module.exports = TelegramBot;
