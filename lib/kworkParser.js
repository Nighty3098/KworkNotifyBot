const axios = require("axios");
const cheerio = require("cheerio");

class KworkParser {
  constructor() {
    this.processedProjects = new Set();
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
      if (!this.processedProjects.has(project.id)) {
        newProjects.push(project);
        this.processedProjects.add(project.id);
      }
    }

    return newProjects;
  }

  cleanupOldProjects() {
    if (this.processedProjects.size > 1000) {
      const array = Array.from(this.processedProjects);
      this.processedProjects = new Set(array.slice(-500));
    }
  }
}

module.exports = KworkParser;
