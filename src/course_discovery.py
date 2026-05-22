"""
课程自动发现模块
从 SaaS 周报页面提取课程名 → 从蓝桥主站 API 反查课程 ID
用户不再需要手动配置 COURSE_IDS
"""

import json
import re
import urllib.request
from typing import Dict, List, Optional
from pathlib import Path

from selenium.webdriver.common.by import By
from src.config import config
from src.logger import logger

# 课程映射缓存文件
CACHE_FILE = config.PROJECT_ROOT / "data" / "course_mapping.json"


class CourseDiscovery:
    """课程自动发现器"""

    def __init__(self, driver):
        self.driver = driver
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def discover(self) -> Dict[str, dict]:
        """
        完整发现流程：SaaS 页面课程名 → 蓝桥课程 ID

        返回格式与 Config.get_course_info() 一致：
        { "61384": { "name": "数据库技术", "sections_api": "...", "study_url": "..." } }
        """
        # 1. 尝试缓存
        cached = self._load_cache()
        if cached:
            logger.info("使用缓存的课程映射")
            return cached

        # 2. 从 SaaS 周报页面提取课程名
        course_names = self._extract_from_page()
        if not course_names:
            logger.warning("未能从 SaaS 页面发现课程名")
            return {}

        logger.info(f"SaaS 页面发现课程：{course_names}")

        # 3. 逐个搜索蓝桥课程 ID
        course_info = {}
        for name in course_names:
            cid = self._search_course_id(name)
            if cid:
                course_info[cid] = {
                    "name": name,
                    "sections_api": f"https://www.lanqiao.cn/api/v2/courses/{cid}/labs/?page_size=500",
                    "study_url": f"https://www.lanqiao.cn/courses/{cid}/learning/",
                }
                logger.info(f"  ✅ {name} → ID={cid}")
            else:
                logger.warning(f"  ❌ 未找到匹配：{name}")

        # 4. 缓存
        if course_info:
            self._save_cache(course_info)
            logger.info(f"课程映射已缓存到 {CACHE_FILE}")

        return course_info

    # ------------------------------------------------------------------
    # SaaS 页面提取
    # ------------------------------------------------------------------

    def _extract_from_page(self) -> List[str]:
        """从当前 SaaS 周报页面提取课程名称"""
        # 确保在周报页面
        current_url = self.driver.current_url
        if "weekly" not in current_url and "evaluation" not in current_url:
            logger.debug("当前不在周报页面，尝试导航...")
            self.driver.get(config.WEEKLY_URL)
            import time
            time.sleep(3)

        # 策略1：CSS 选择器匹配常见课程元素
        courses = self._try_css_selectors()
        if courses:
            return courses

        # 策略2：正则匹配页面文本中的课程名
        courses = self._try_regex_extract()
        if courses:
            return courses

        # 策略3：从页面链接中提取
        courses = self._try_link_extract()
        if courses:
            return courses

        return []

    def _try_css_selectors(self) -> List[str]:
        """策略1：用 CSS 选择器查找课程元素"""
        selectors = [
            ".course-name",
            ".el-tag",
            "[class*='course']",
            "[class*='subject']",
            ".tag-item",
            ".label-tag",
            "[class*='tag']",
        ]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                texts = [el.text.strip() for el in elements if el.text.strip()]
                # 过滤掉太短或太长的文本（课程名通常 2-20 字）
                texts = [t for t in texts if 2 <= len(t) <= 20]
                if texts:
                    logger.debug(f"CSS 选择器 '{selector}' 发现：{texts}")
                    return texts
            except Exception:
                continue
        return []

    def _try_regex_extract(self) -> List[str]:
        """策略2：用正则从页面源码中提取课程名"""
        try:
            page_text = self.driver.page_source
            patterns = [
                r'关联课程[：:]\s*(.+?)(?:<|\\n|\n)',
                r'本周课程[：:]\s*(.+?)(?:<|\\n|\n)',
                r'课程名称[：:]\s*(.+?)(?:<|\\n|\n)',
                r'course[_-]?name["\s:>]+([^<"]{2,20})',
            ]
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    text = match.group(1).strip()
                    # 按逗号、顿号、斜杠分割
                    names = [c.strip() for c in re.split(r'[,，、/]', text) if c.strip()]
                    if names:
                        logger.debug(f"正则匹配发现：{names}")
                        return names
        except Exception:
            pass
        return []

    def _try_link_extract(self) -> List[str]:
        """策略3：从页面链接中提取课程名"""
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='courses']")
            for link in links:
                text = link.text.strip()
                if text and 2 <= len(text) <= 20:
                    return [text]
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------
    # 蓝桥课程 ID 搜索
    # ------------------------------------------------------------------

    def _search_course_id(self, course_name: str) -> Optional[str]:
        """通过蓝桥主站 API 搜索课程 ID"""
        # 策略1：精确搜索
        cid = self._api_search(course_name, exact=True)
        if cid:
            return cid

        # 策略2：模糊搜索
        cid = self._api_search(course_name, exact=False)
        if cid:
            return cid

        # 策略3：从用户已报名课程中查找
        cid = self._search_from_user_courses(course_name)
        if cid:
            return cid

        return None

    def _api_search(self, course_name: str, exact: bool = True) -> Optional[str]:
        """调用蓝桥课程搜索 API"""
        try:
            encoded = urllib.request.quote(course_name)
            url = f"https://www.lanqiao.cn/api/v2/courses/?search={encoded}&page_size=10"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # API 返回 {"results": [...]} 或 {"data": [...]}
                courses = data if isinstance(data, list) else data.get("results", data.get("data", []))

                if not courses:
                    return None

                if exact:
                    # 精确匹配
                    for c in courses:
                        if c.get("name", "") == course_name:
                            return str(c["id"])
                else:
                    # 模糊匹配（包含关系）
                    for c in courses:
                        name = c.get("name", "")
                        if course_name in name or name in course_name:
                            return str(c["id"])

        except Exception as e:
            logger.debug(f"API 搜索失败 ({course_name}): {e}")
        return None

    def _search_from_user_courses(self, course_name: str) -> Optional[str]:
        """从蓝桥用户课程页面搜索（需要已登录主站）"""
        try:
            # 先确保在主站
            self.driver.get("https://www.lanqiao.cn/user/courses/")
            import time
            time.sleep(3)

            # 如果跳转到登录页，说明未登录主站
            if "passport" in self.driver.current_url or "login" in self.driver.current_url:
                logger.debug("主站未登录，跳过用户课程搜索")
                return None

            # 在页面中查找匹配的课程链接
            links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/courses/']")
            for link in links:
                text = link.text.strip()
                if course_name in text or text in course_name:
                    href = link.get_attribute("href")
                    match = re.search(r'/courses/(\d+)', href)
                    if match:
                        return match.group(1)

        except Exception as e:
            logger.debug(f"用户课程搜索失败：{e}")
        return None

    # ------------------------------------------------------------------
    # 缓存
    # ------------------------------------------------------------------

    def _load_cache(self) -> Optional[Dict[str, dict]]:
        """加载课程映射缓存"""
        if CACHE_FILE.exists():
            try:
                data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                if data and isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, KeyError):
                pass
        return None

    def _save_cache(self, course_info: dict):
        """保存课程映射缓存"""
        try:
            CACHE_FILE.write_text(
                json.dumps(course_info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"缓存保存失败：{e}")

    @staticmethod
    def clear_cache():
        """清除课程映射缓存"""
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            logger.info("课程映射缓存已清除")
