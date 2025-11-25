const { Telegraf } = require("telegraf");
const axios = require("axios");

let processedProjects = new Set();
let monitoringInterval = null;
let isMonitoring = false;

class KworkParser {
  constructor() {
    this.retryCount = 3;
    this.retryDelay = 2000;

    this.axiosInstance = axios.create({
      timeout: 30000, // 30 секунд
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "Upgrade-Insecure-Requests": "1",
      },
    });
  }

  async getProjects() {
    for (let attempt = 1; attempt <= this.retryCount; attempt++) {
      try {
        console.log(
          `🔍 Запрос к Kwork (попытка ${attempt}/${this.retryCount})...`,
        );

        const response = await this.axiosInstance.get(
          "https://kwork.ru/projects",
          {
            timeout: 30000,
          },
        );

        const html = response.data;

        const projects = this.extractProjectsFromHtml(html);
        if (projects && projects.length > 0) {
          console.log(`📊 Найдено проектов: ${projects.length}`);
          return projects;
        }

        if (attempt < this.retryCount) {
          console.log(
            `⏳ Проекты не найдены, повтор через ${this.retryDelay / 1000} сек...`,
          );
          await this.delay(this.retryDelay);
        }
      } catch (error) {
        console.error(
          `❌ Ошибка запроса (попытка ${attempt}/${this.retryCount}):`,
          error.message,
        );

        if (attempt < this.retryCount) {
          console.log(`⏳ Повтор через ${this.retryDelay / 1000} сек...`);
          await this.delay(this.retryDelay);
        } else {
          console.error("❌ Все попытки запроса завершились ошибкой");
        }
      }
    }
    return [];
  }

  extractProjectsFromHtml(html) {
    const stateDataMatch = html.match(/window\.stateData\s*=\s*({.*?});/s);
    if (stateDataMatch) {
      try {
        const stateData = JSON.parse(stateDataMatch[1]);
        if (stateData.wantsListData && stateData.wantsListData.wants) {
          return this.parseProjects(stateData.wantsListData.wants);
        }
      } catch (error) {
        console.error("❌ Ошибка парсинга stateData:", error.message);
      }
    }

    const scriptMatches = html.match(/<script[^>]*>([\s\S]*?)<\/script>/gi);
    if (scriptMatches) {
      for (const script of scriptMatches) {
        if (script.includes("wants") && script.includes("projects")) {
          try {
            const jsonMatch = script.match(/{[\s\S]*"wants"[\s\S]*}/);
            if (jsonMatch) {
              const data = JSON.parse(jsonMatch[0]);
              if (data.wants) {
                return this.parseProjects(data.wants);
              }
            }
          } catch (error) {}
        }
      }
    }

    return [];
  }

  parseProjects(projectsData) {
    const parsedProjects = [];

    for (const project of projectsData) {
      try {
        const projectId = project.id;
        if (!projectId) continue;

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
        console.error("❌ Ошибка парсинга проекта:", error.message);
      }
    }

    return parsedProjects;
  }

  async getNewProjects() {
    try {
      const allProjects = await this.getProjects();
      const newProjects = [];

      for (const project of allProjects) {
        if (project.id && !processedProjects.has(project.id)) {
          newProjects.push(project);
          processedProjects.add(project.id);
        }
      }

      if (processedProjects.size > 1000) {
        const array = Array.from(processedProjects);
        processedProjects = new Set(array.slice(-500));
      }

      return newProjects;
    } catch (error) {
      console.error("❌ Ошибка в getNewProjects:", error.message);
      return [];
    }
  }

  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

const bot = new Telegraf(process.env.TELEGRAM_BOT_TOKEN);
const kworkParser = new KworkParser();

async function sendProjectNotification(chatId, project) {
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

    await bot.telegram.sendMessage(chatId, message, {
      parse_mode: "Markdown",
      disable_web_page_preview: false,
    });

    console.log(`✅ Уведомление отправлено: ${project.title}`);
    return true;
  } catch (error) {
    console.error("❌ Ошибка отправки уведомления:", error.message);
    return false;
  }
}

bot.start((ctx) => {
  ctx.reply(
    "🚀 Бот для мониторинга Kwork запущен!\n\nКоманды:\n/monitor - запустить мониторинг\n/stop - остановить мониторинг\n/check - проверить сейчас\n/status - статус",
  );
});

bot.command("monitor", async (ctx) => {
  if (isMonitoring) {
    ctx.reply("🔍 Мониторинг уже запущен!");
    return;
  }

  isMonitoring = true;
  const chatId = ctx.chat.id;

  ctx.reply("🔍 Мониторинг запущен! Проверка каждые 3 минуты.");
  console.log("✅ Мониторинг запущен");

  const performCheck = async () => {
    if (!isMonitoring) return;

    try {
      console.log("🔍 Автоматическая проверка проектов...");
      const newProjects = await kworkParser.getNewProjects();
      if (newProjects.length > 0) {
        console.log(`🎉 Найдено новых проектов: ${newProjects.length}`);
        let sentCount = 0;

        for (const project of newProjects) {
          if (!isMonitoring) break;

          const success = await sendProjectNotification(chatId, project);
          if (success) {
            sentCount++;
            await new Promise((resolve) => setTimeout(resolve, 1500));
          }
        }

        if (sentCount > 0) {
          await bot.telegram.sendMessage(
            chatId,
            `📊 Проверка завершена. Отправлено уведомлений: ${sentCount}`,
          );
        }
      } else {
        console.log("ℹ️ Новых проектов нет");
      }
    } catch (error) {
      console.error("❌ Ошибка мониторинга:", error.message);
      await bot.telegram.sendMessage(
        chatId,
        "❌ Произошла ошибка при проверке проектов. Мониторинг продолжается.",
      );
    }
  };

  // Запуск мониторинга каждые 25 минут
  monitoringInterval = setInterval(performCheck, 1000 * 60 * 25);

  setTimeout(performCheck, 5000);
});

bot.command("stop", (ctx) => {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
    monitoringInterval = null;
    isMonitoring = false;
    ctx.reply("🛑 Мониторинг остановлен");
    console.log("🛑 Мониторинг остановлен");
  } else {
    ctx.reply("ℹ️ Мониторинг не запущен");
  }
});

bot.command("check", async (ctx) => {
  const chatId = ctx.chat.id;
  ctx.reply("🔍 Проверяю новые проекты...");

  try {
    const newProjects = await kworkParser.getNewProjects();
    if (newProjects.length > 0) {
      ctx.reply(`🎉 Найдено новых проектов: ${newProjects.length}`);
      let sentCount = 0;

      for (const project of newProjects) {
        const success = await sendProjectNotification(chatId, project);
        if (success) {
          sentCount++;
          await new Promise((resolve) => setTimeout(resolve, 1500));
        }
      }

      if (sentCount < newProjects.length) {
        ctx.reply(
          `📊 Удалось отправить ${sentCount} из ${newProjects.length} уведомлений`,
        );
      }
    } else {
      ctx.reply("ℹ️ Новых проектов нет");
    }
  } catch (error) {
    ctx.reply("❌ Ошибка при проверке проектов");
    console.error("❌ Ошибка проверки:", error.message);
  }
});

bot.command("status", (ctx) => {
  const status = isMonitoring ? "активен" : "остановлен";
  ctx.reply(
    `📊 Статус мониторинга: ${status}\nОбработано проектов: ${processedProjects.size}`,
  );
});

bot.command("ping", (ctx) => {
  ctx.reply("🏓 Pong! Бот работает нормально");
});

bot.catch((err, ctx) => {
  console.error(`❌ Ошибка бота для ${ctx.updateType}:`, err.message);
});

async function startBot() {
  try {
    if (process.env.VERCEL) {
      console.log("🚀 Бот запущен в режиме вебхука на Vercel");
    } else {
      console.log("🚀 Бот запущен в режиме long polling");
      await bot.launch();
    }

    console.log("✅ Бот успешно запущен");
  } catch (error) {
    console.error("❌ Ошибка запуска бота:", error.message);
    process.exit(1);
  }
}

module.exports = async (req, res) => {
  if (req.method === "POST") {
    try {
      await bot.handleUpdate(req.body);
      res.status(200).send("OK");
    } catch (error) {
      console.error("❌ Ошибка обработки вебхука:", error.message);
      res.status(500).send("Error");
    }
  } else {
    res.status(200).json({
      status: "Bot is running",
      monitoring: isMonitoring ? "active" : "inactive",
      processed_projects: processedProjects.size,
      timestamp: new Date().toISOString(),
    });
  }
};

if (!process.env.VERCEL) {
  startBot();
}

process.once("SIGINT", () => {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
    isMonitoring = false;
  }
  bot.stop("SIGINT");
  console.log("🛑 Бот остановлен");
});

process.once("SIGTERM", () => {
  if (monitoringInterval) {
    clearInterval(monitoringInterval);
    isMonitoring = false;
  }
  bot.stop("SIGTERM");
  console.log("🛑 Бот остановлен");
});
