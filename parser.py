import asyncio
import json
import logging
import random
import re
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp_socks import ProxyConnector, SocksConnector
from bs4 import BeautifulSoup

from config import config
from proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


class KworkParser:
    def __init__(self, proxy_manager: Optional[ProxyManager] = None):
        self.session = None
        self.proxy_manager = proxy_manager
        self.current_proxy = None

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        self.kwork_headers = {
            **self.headers,
            "Host": "kwork.ru",
            "Referer": "https://kwork.ru/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        }

    async def __aenter__(self):
        self.session = await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _create_session(self) -> Optional[aiohttp.ClientSession]:
        try:
            session_kwargs = {
                "headers": self.kwork_headers,
                "timeout": aiohttp.ClientTimeout(total=config.PROXY_TIMEOUT),
            }

            if self.proxy_manager:
                self.current_proxy = self.proxy_manager.get_next_proxy()

                if self.current_proxy:
                    proxy_url = self.current_proxy["url"]
                    host = self.current_proxy.get("host", "unknown")
                    port = self.current_proxy.get("port", "unknown")
                    country = self.current_proxy.get("country", "Unknown")

                    logger.info(
                        f"Используем прокси: {host}:{port} ({country}) - {self.current_proxy['type']}"
                    )

                    if self.current_proxy["type"] in ["socks4", "socks5"]:
                        try:
                            connector = SocksConnector.from_url(proxy_url)
                            session_kwargs["connector"] = connector
                        except Exception as e:
                            logger.error(f"Ошибка создания SOCKS коннектора: {e}")
                            return None
                    elif self.current_proxy["type"] == "http":
                        try:
                            connector = ProxyConnector.from_url(proxy_url)
                            session_kwargs["connector"] = connector
                        except Exception as e:
                            logger.error(f"Ошибка создания HTTP коннектора: {e}")
                            return None

                else:
                    logger.warning(
                        "Нет доступных прокси, используем прямое подключение"
                    )

            return aiohttp.ClientSession(**session_kwargs)

        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            return None

    async def _make_request_with_retry(
        self, url: str, max_retries: int = 3
    ) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                if not self.session:
                    self.session = await self._create_session()
                    if not self.session:
                        logger.error("Не удалось создать сессию")
                        continue

                logger.info(
                    f"Делаем запрос к {url} (попытка {attempt + 1}/{max_retries})"
                )

                async with self.session.get(url) as response:
                    logger.info(f"Получен ответ: статус {response.status}")

                    if response.status == 200:
                        html = await response.text()

                        if self.proxy_manager and self.current_proxy:
                            self.proxy_manager.mark_success(self.current_proxy["url"])

                        return html
                    else:
                        logger.warning(f"Статус ответа {response.status} для {url}")

                        if self.proxy_manager and self.current_proxy:
                            self.proxy_manager.mark_failure(self.current_proxy["url"])

                        if response.status in [403, 429]:
                            logger.info(
                                f"Обнаружена блокировка (статус {response.status}), меняем прокси..."
                            )
                            await self._rotate_proxy()
                            continue

            except aiohttp.ClientError as e:
                logger.error(
                    f"Ошибка запроса (попытка {attempt + 1}/{max_retries}): {e}"
                )

                if self.proxy_manager and self.current_proxy:
                    self.proxy_manager.mark_failure(self.current_proxy["url"])

                await self._rotate_proxy()

                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                continue

            except Exception as e:
                logger.error(f"Неожиданная ошибка при запросе: {e}")
                break

        return None

    async def _rotate_proxy(self):
        """Сменить прокси и пересоздать сессию"""
        if self.session:
            await self.session.close()
            self.session = None

        if self.proxy_manager:
            self.current_proxy = self.proxy_manager.get_next_proxy()
            if self.current_proxy:
                host = self.current_proxy.get("host", "unknown")
                port = self.current_proxy.get("port", "unknown")
                country = self.current_proxy.get("country", "Unknown")
                logger.info(f"Сменили прокси на: {host}:{port} ({country})")
            else:
                logger.info("Нет доступных прокси, используем прямое подключение")

        self.session = await self._create_session()

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Fetch projects from Kwork"""
        try:
            logger.info("🔍 Запрос к Kwork...")
            url = "https://kwork.ru/projects"

            html = await self._make_request_with_retry(url)

            if not html:
                logger.error("❌ Не удалось получить данные с Kwork после всех попыток")
                return []

            if len(html) < 100:
                logger.error(f"❌ Получен слишком короткий ответ: {len(html)} символов")
                return []

            pattern = r"window\.stateData\s*=\s*({.*?});"
            match = re.search(pattern, html, re.DOTALL)

            if match:
                try:
                    state_data = json.loads(match.group(1))

                    if state_data.get("wantsListData", {}).get("wants"):
                        projects = state_data["wantsListData"]["wants"]
                        logger.info(f"📊 Найдено проектов: {len(projects)}")
                        return self._parse_projects(projects)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка парсинга JSON: {e}")

            logger.info("Пробуем альтернативный метод парсинга...")
            soup = BeautifulSoup(html, "html.parser")
            script_tags = soup.find_all("script")

            for script in script_tags:
                if script.string and "window.stateData" in script.string:
                    try:
                        lines = script.string.split("\n")
                        for line in lines:
                            if "window.stateData" in line:
                                start = line.find("{")
                                end = line.rfind("}") + 1
                                if start != -1 and end != -1:
                                    json_str = line[start:end]
                                    state_data = json.loads(json_str)

                                    if state_data.get("wantsListData", {}).get("wants"):
                                        projects = state_data["wantsListData"]["wants"]
                                        logger.info(
                                            f"📊 Найдено проектов (альтернативный метод): {len(projects)}"
                                        )
                                        return self._parse_projects(projects)
                    except Exception as e:
                        logger.error(f"Ошибка альтернативного парсинга: {e}")

            return []

        except Exception as e:
            logger.error(f"❌ Ошибка запроса к Kwork: {e}")
            return []
        finally:
            if self.session:
                await self.session.close()
                self.session = None

    def _parse_projects(self, projects_data: List[Dict]) -> List[Dict[str, Any]]:
        parsed_projects = []

        for project in projects_data:
            try:
                project_id = str(project.get("id", ""))
                title = project.get("name", "Без названия")

                description = project.get("description", "Без описания")
                description = re.sub(r"<[^>]+>", "", description)
                description = description.replace("\r\n", " ")
                words = description.split()
                description = (
                    " ".join(words[:30]) + "..." if len(words) > 30 else description
                )

                price = "Цена не указана"
                if project.get("priceLimit") and project["priceLimit"] != "0":
                    price = f"{float(project['priceLimit']):.0f} руб."
                elif project.get("possiblePriceLimit"):
                    price = f"{project['possiblePriceLimit']} руб."

                username = project.get("user", {}).get("username", "Аноним")
                time_left = project.get("timeLeft", "")

                project_data = {
                    "id": project_id,
                    "title": title,
                    "description": description,
                    "price": price,
                    "username": username,
                    "time_left": time_left,
                    "url": f"https://kwork.ru/projects/view/{project_id}",
                }

                parsed_projects.append(project_data)

            except Exception as e:
                logger.error(f"❌ Ошибка парсинга проекта: {e}")

        return parsed_projects
