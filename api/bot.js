const { Telegraf } = require("telegraf");
const axios = require("axios");
const cheerio = require("cheerio");

// Глобальные переменные для хранения состояния
let processedProjects = new Set();
let monitoringInterval = null;

class KworkParser {
  constructor() {
    this.axiosInstance = axios.create({
      timeout: 10000,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
      },
    });
  }

  async getProjects() {
    try {
      const response = await this.axiosInstance.get(
        "https://kwork.ru/projects",
      );
      const html = response.data;

      const stateDataMatch = html.match(/window\.stateData\s*=\s*({.*?});/s);

      if (stateDataMatch) {
        try {
          const stateData = JSON.parse(stateDataMatch[1]);

          if (stateData.wantsListData && stateData.wantsListData.wants) {
            const projects = stateData.wantsListData.wants;
            console.log(`📊 Найдено проектов: ${projects.length}`);
            return this.parseProjects(projects);
          }
        } catch (error) {
          console.error("❌ Ошибка парсинга JSON:", error);
        }
      }

      return [];
    } catch (error) {
      console.error("❌ Ошибка запроса к Kwork:", error);
      return [];
    }
  }

  parseProjects(projectsData) {
    const parsedProjects = [];

    for (const project of projectsData) {
      try {
        const projectId = project.id;
        const title = project.name || "Без названия";

        let description = project.description || "Без описания";
        description = description.replace(/<[^>]+>/g, "");
        description = description.replace(/\r\n/g, " ");
        description = description.split(/\s+/).slice(0, 30).join(" ") + "...";

        let price = "Цена не указана";
        if (project.priceLimit && project.priceLimit !== "0") {
          price = `${parseFloat(project.priceLimit).toFixed(0)} руб.`;
        } else if (project.possiblePriceLimit) {
          price = `${project.possiblePriceLimit} руб.`;
        }

        const username = project.user?.username || "Аноним";
        const timeLeft = project.timeLeft || "";

        const projectData = {
          id: projectId,
          title: title,
          description: description,
          price: price,
          username: username,
          time_left: timeLeft,
          url: `https://kwork.ru/projects/view/${projectId}`,
        };

        parsedProjects.push(projectData);
      } catch (error) {
        console.error("❌ Ошибка парсинга проекта:", error);
      }
    }

    return parsedProjects;
  }

  async getNewProjects() {
    const allProjects = await this.getProjects();
    const newProjects = [];

    for (const project of allProjects) {
      if (!processedProjects.has(project.id)) {
        newProjects.push(project);
        processedProjects.add(project.id);
      }
    }

    // Очистка старых проектов
    if (processedProjects.size > 1000) {
      const array = Array.from(processedProjects);
      processedProjects = new Set(array.slice(-500));
    }

    return newProjects;
  }
}

// Инициализация бота и парсера
const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);
const kworkParser = new KworkParser();

// Команды бота
bot.start((ctx) => {
  ctx.reply(
    "🚀 Бот для мониторинга Kwork запущен!\n\nКоманды:\n/monitor - запустить мониторинг\n/stop - остановить мониторинг\n/check - проверить сейчас\n/status - статус",
  );
});

bot.command("monitor", (ctx) => {
  if (monitoringInterval) {
    ctx.reply("🔍 Мониторинг уже запущен!");
    return;
  }

  // Запуск мониторинга каждые 2 минуты
  monitoringInterval = setInterval(async () => {
    try {
      const newProjects = await kworkParser.getNewProjects();
      if (newProjects.length > 0) {
        console.log(`🎉 Найдено новых проектов: ${newProjects.length}`);
        for (const project of newProjects) {
          await sendProjectNotification(ctx, project);
          // Задержка между отправками
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
    } catch (error) {
      console.error("❌ Ошибка мониторинга:", error);
    }
  }, 120000); // 2 минуты

  ctx.reply("🔍 Мониторинг запущен! Проверка каждые 2 минуты.");
  console.log("✅ Мониторинг запущен");
});

bot.command("stop", (ctx) => {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
    monitoringInterval = null;
    ctx.reply("🛑 Мониторинг остановлен");
    console.log("🛑 Мониторинг остановлен");
  } else {
    ctx.reply("ℹ️ Мониторинг не запущен");
  }
});

bot.command("check", async (ctx) => {
  ctx.reply("🔍 Проверяю новые проекты...");

  try {
    const newProjects = await kworkParser.getNewProjects();
    if (newProjects.length > 0) {
      ctx.reply(`🎉 Найдено новых проектов: ${newProjects.length}`);
      for (const project of newProjects) {
        await sendProjectNotification(ctx, project);
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } else {
      ctx.reply("ℹ️ Новых проектов нет");
    }
  } catch (error) {
    ctx.reply("❌ Ошибка при проверке проектов");
    console.error("❌ Ошибка проверки:", error);
  }
});

bot.command("status", (ctx) => {
  const status = monitoringInterval ? "активен" : "остановлен";
  ctx.reply(
    `📊 Статус мониторинга: ${status}\nОбработано проектов: ${processedProjects.size}`,
  );
});

// Функция отправки уведомления о проекте
async function sendProjectNotification(ctx, project) {
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

    await ctx.telegram.sendMessage(ctx.chat.id, message, {
      parse_mode: "Markdown",
      disable_web_page_preview: false,
    });

    console.log(`✅ Уведомление отправлено: ${project.title}`);
  } catch (error) {
    console.error("❌ Ошибка отправки уведомления:", error);
  }
}

// Обработка ошибок бота
bot.catch((err, ctx) => {
  console.error(`❌ Ошибка бота для ${ctx.updateType}:`, err);
});

// Запуск бота
async function startBot() {
  try {
    // Для Vercel используем вебхуки, для локального - long polling
    if (process.env.VERCEL) {
      console.log("🚀 Бот запущен в режиме вебхука");
      // Vercel будет обрабатывать вебхуки через экспортированную функцию
    } else {
      console.log("🚀 Бот запущен в режиме long polling");
      await bot.launch();

      // Автозапуск мониторинга при старте в локальном режиме
      monitoringInterval = setInterval(async () => {
        try {
          const newProjects = await kworkParser.getNewProjects();
          if (newProjects.length > 0) {
            console.log(`🎉 Найдено новых проектов: ${newProjects.length}`);
            // В локальном режиме отправляем первому чату (можно настроить)
            for (const project of newProjects) {
              // Здесь нужно указать chat_id для локальных уведомлений
              const chatId = process.env.TELEGRAM_CHAT_ID;
              if (chatId) {
                await bot.telegram.sendMessage(
                  chatId,
                  `🎯 НОВЫЙ ПРОЕКТ: ${project.title}\n💰 ${project.price}\n🔗 ${project.url}`,
                  { parse_mode: "Markdown" },
                );
                await new Promise((resolve) => setTimeout(resolve, 1000));
              }
            }
          }
        } catch (error) {
          console.error("❌ Ошибка мониторинга:", error);
        }
      }, 120000);
    }

    console.log("✅ Бот успешно запущен");
  } catch (error) {
    console.error("❌ Ошибка запуска бота:", error);
    process.exit(1);
  }
}

// Экспорт для Vercel
module.exports = async (req, res) => {
  if (req.method === "POST") {
    try {
      await bot.handleUpdate(req.body);
      res.status(200).send("OK");
    } catch (error) {
      console.error("❌ Ошибка обработки вебхука:", error);
      res.status(500).send("Error");
    }
  } else {
    // Для GET запросов - информационная страница
    res.status(200).json({
      status: "Bot is running",
      monitoring: monitoringInterval ? "active" : "inactive",
      processed_projects: processedProjects.size,
      timestamp: new Date().toISOString(),
    });
  }
};

// Автозапуск при старте (только в локальном режиме)
if (!process.env.VERCEL) {
  startBot();
}

// Graceful shutdown
process.once("SIGINT", () => {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
  }
  bot.stop("SIGINT");
  console.log("🛑 Бот остановлен");
});

process.once("SIGTERM", () => {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
  }
  bot.stop("SIGTERM");
  console.log("🛑 Бот остановлен");
});
