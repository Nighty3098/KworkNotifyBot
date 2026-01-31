import asyncio
import base64
import json
import logging
import random
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType, SocksConnector

logger = logging.getLogger(__name__)


class ProxyManager:
    def __init__(self, proxy_strings: str):
        self.proxies = self._parse_proxies(proxy_strings)
        self.proxy_stats: Dict[str, Dict] = {}
        self.current_proxy_index = 0
        self.request_counter = 0
        self.max_requests_per_proxy = 6

        for proxy in self.proxies:
            self.proxy_stats[proxy["url"]] = {
                "success_count": 0,
                "fail_count": 0,
                "total_requests": 0,
                "is_active": True,
                "last_used": None,
                "country": proxy.get("country", "Unknown"),
            }

        logger.info(f"Загружено прокси: {len(self.proxies)}")
        for i, proxy in enumerate(self.proxies, 1):
            logger.info(
                f"Прокси {i}: {proxy.get('type')} - {proxy.get('host', 'unknown')}:{proxy.get('port', 'unknown')} - {proxy.get('country', 'Unknown')}"
            )

    def _parse_proxies(self, proxy_strings: str) -> List[Dict]:
        proxies = []

        if not proxy_strings or not proxy_strings.strip():
            return proxies

        for proxy_str in proxy_strings.split(","):
            proxy_str = proxy_str.strip()
            if not proxy_str:
                continue

            try:
                country = "Unknown"
                original_proxy_str = proxy_str

                if "#" in proxy_str:
                    proxy_part, comment = proxy_str.split("#", 1)
                    comment = comment.strip()
                    comment = re.sub(
                        r"[\U00010000-\U0010ffff]", "", comment, flags=re.UNICODE
                    )
                    comment = comment.replace("%20", " ").strip()
                    if comment:
                        country = comment.split()[0] if comment.split() else "Unknown"
                    proxy_str = proxy_part

                proxy_str = proxy_str.strip()

                if proxy_str.startswith("ss://"):
                    proxy_info = self._parse_shadowsocks(proxy_str)
                    if proxy_info:
                        proxy_info["country"] = country
                        proxy_info["original"] = original_proxy_str
                        proxies.append(proxy_info)
                elif proxy_str.startswith(
                    ("http://", "https://", "socks4://", "socks5://")
                ):
                    parsed = urlparse(proxy_str)
                    proxy_type = (
                        "http" if parsed.scheme in ["http", "https"] else parsed.scheme
                    )

                    host = parsed.hostname
                    port = parsed.port

                    if not port:
                        if parsed.scheme == "http":
                            port = 80
                        elif parsed.scheme == "https":
                            port = 443
                        elif parsed.scheme in ["socks4", "socks5"]:
                            port = 1080
                        else:
                            port = 80

                    proxies.append(
                        {
                            "type": proxy_type,
                            "url": proxy_str,
                            "host": host,
                            "port": port,
                            "original": original_proxy_str,
                            "country": country,
                        }
                    )
                else:
                    logger.warning(f"Неизвестный формат прокси: {proxy_str}")

            except Exception as e:
                logger.error(f"Ошибка парсинга прокси {proxy_str}: {e}")

        return proxies

    def _parse_shadowsocks(self, ss_url: str) -> Optional[Dict]:
        try:
            clean_url = ss_url.split("#")[0]
            if not clean_url.startswith("ss://"):
                return None

            import re

            host_port_pattern = (
                r"([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}):([0-9]{1,5})"
            )
            match = re.search(host_port_pattern, clean_url)

            if match:
                host = match.group(1)
                port = int(match.group(2))

                proxy_url = f"socks5://{host}:{port}"

                return {"type": "socks5", "url": proxy_url, "host": host, "port": port}

            try:
                base64_part = clean_url[5:]
                if "?" in base64_part:
                    base64_part = base64_part.split("?")[0]

                padding = 4 - len(base64_part) % 4
                if padding != 4:
                    base64_part += "=" * padding

                decoded = base64.b64decode(base64_part).decode("utf-8", errors="ignore")

                match = re.search(host_port_pattern, decoded)
                if match:
                    host = match.group(1)
                    port = int(match.group(2))

                    proxy_url = f"socks5://{host}:{port}"

                    return {
                        "type": "socks5",
                        "url": proxy_url,
                        "host": host,
                        "port": port,
                    }
            except:
                pass

            return None

        except Exception as e:
            logger.error(f"Ошибка парсинга Shadowsocks URL {ss_url}: {e}")
            return None

    def get_next_proxy(self) -> Optional[Dict]:
        if not self.proxies:
            return None

        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_proxy_index]
            stats = self.proxy_stats[proxy["url"]]

            if (
                stats["is_active"]
                and stats["total_requests"] < self.max_requests_per_proxy
            ):
                self.current_proxy_index = (self.current_proxy_index + 1) % len(
                    self.proxies
                )
                return proxy

            self.current_proxy_index = (self.current_proxy_index + 1) % len(
                self.proxies
            )

        logger.warning("Все прокси исчерпали лимит запросов или неактивны")

        for proxy in self.proxies:
            stats = self.proxy_stats[proxy["url"]]
            if not stats["is_active"]:
                stats["is_active"] = True
                stats["total_requests"] = 0
                logger.info(
                    f"Сброшен статус для прокси: {proxy.get('host', 'unknown')}"
                )

        if self.proxies:
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(
                self.proxies
            )
            return proxy

        return None

    def mark_success(self, proxy_url: str):
        if proxy_url in self.proxy_stats:
            self.proxy_stats[proxy_url]["success_count"] += 1
            self.proxy_stats[proxy_url]["total_requests"] += 1
            self.proxy_stats[proxy_url]["last_used"] = asyncio.get_event_loop().time()

    def mark_failure(self, proxy_url: str):
        if proxy_url in self.proxy_stats:
            self.proxy_stats[proxy_url]["fail_count"] += 1
            self.proxy_stats[proxy_url]["total_requests"] += 1

            if self.proxy_stats[proxy_url]["fail_count"] >= 3:
                self.proxy_stats[proxy_url]["is_active"] = False
                logger.warning(f"Прокси помечен как неактивный: {proxy_url}")

    async def test_proxy(
        self, proxy: Dict, test_url: str = "https://api.ipify.org?format=json"
    ) -> bool:
        try:
            connector = None
            session_kwargs = {
                "timeout": aiohttp.ClientTimeout(total=10),
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            }

            if proxy["type"] in ["socks4", "socks5"]:
                connector = SocksConnector.from_url(proxy["url"])
                session_kwargs["connector"] = connector
            elif proxy["type"] == "http":
                connector = ProxyConnector.from_url(proxy["url"])
                session_kwargs["connector"] = connector

            async with aiohttp.ClientSession(**session_kwargs) as session:
                async with session.get(test_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(
                            f"Прокси работает. Ваш IP: {data.get('ip', 'unknown')}"
                        )
                        return True
                    else:
                        logger.warning(f"Прокси вернул статус {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Ошибка проверки прокси {proxy.get('host', 'unknown')}: {e}")
            return False
        finally:
            if connector:
                await connector.close()

    def get_stats(self) -> Dict:
        total = len(self.proxies)
        active = sum(1 for stats in self.proxy_stats.values() if stats["is_active"])
        total_requests = sum(
            stats["total_requests"] for stats in self.proxy_stats.values()
        )
        success_rate = 0

        if total_requests > 0:
            total_success = sum(
                stats["success_count"] for stats in self.proxy_stats.values()
            )
            success_rate = (total_success / total_requests) * 100

        return {
            "total_proxies": total,
            "active_proxies": active,
            "total_requests": total_requests,
            "success_rate": round(success_rate, 2),
            "proxies": [
                {
                    "url": url,
                    "stats": stats,
                    "country": stats.get("country", "Unknown"),
                    "host": next(
                        (
                            p.get("host", "unknown")
                            for p in self.proxies
                            if p["url"] == url
                        ),
                        "unknown",
                    ),
                    "port": next(
                        (
                            p.get("port", "unknown")
                            for p in self.proxies
                            if p["url"] == url
                        ),
                        "unknown",
                    ),
                    "original": next(
                        (
                            p.get("original", "")
                            for p in self.proxies
                            if p["url"] == url
                        ),
                        "",
                    ),
                }
                for url, stats in self.proxy_stats.items()
            ],
        }

    def reset_all_proxies(self):
        for proxy in self.proxies:
            stats = self.proxy_stats[proxy["url"]]
            stats["is_active"] = True
            stats["total_requests"] = 0
            stats["success_count"] = 0
            stats["fail_count"] = 0
        logger.info("Все прокси сброшены")
