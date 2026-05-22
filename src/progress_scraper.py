"""
学习进度抓取模块
从蓝桥云课课程页面抓取用户真实学习进度
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from src.config import config
from src.logger import logger


class ProgressScraper:
    """蓝桥云课学习进度抓取器"""

    # 状态文件路径
    STRUCTURE_CACHE: Path = config.PROJECT_ROOT / "data" / "course_structures.json"

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 20)
        # 确保缓存目录存在
        self.STRUCTURE_CACHE.parent.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------
    # 公开方法
    # ----------------------------------------------------------

    def scrape_all_courses(self) -> Dict[str, dict]:
        """抓取所有已配置课程的最新进度（注意：历史快照由 ProgressHistory 管理）"""
        all_progress = {}

        for course_id, info in config.get_course_info().items():
            logger.info(f"正在抓取课程：{info['name']}（{course_id}）")
            try:
                progress = self.scrape_single_course(course_id)
                all_progress[course_id] = progress
                logger.info(f"  ✓ {info['name']}：{progress['completed_count']}/{progress['total_count']} 完成")
            except Exception as e:
                logger.warning(f"  ✗ {info['name']} 抓取失败：{e}")
                all_progress[course_id] = {"error": str(e)}

        return all_progress

    def scrape_single_course(self, course_id: str) -> dict:
        """抓取单门课程的进度"""
        info = config.get_course_info().get(course_id)
        if not info:
            raise ValueError(f"未配置课程 ID：{course_id}")

        # 1️⃣ 获取课程结构（优先用缓存 / 在线 API）
        structure = self._get_course_structure(course_id)

        # 2️⃣ 用浏览器访问课程学习页面，提取完成状态
        completed_ids = self._fetch_completed_lab_ids(info["study_url"])

        # 3️⃣ 匹配完成状态到课程结构
        return self._merge_progress(structure, completed_ids)

    # ----------------------------------------------------------
    # 课程结构获取
    # ----------------------------------------------------------

    def _get_course_structure(self, course_id: str) -> dict:
        """获取课程结构（API + 缓存兜底）"""
        # 尝试从缓存读取
        cache = self._load_structure_cache()
        if course_id in cache:
            logger.debug("使用缓存的课程结构")
            return cache[course_id]

        # 走在线 API
        import urllib.request

        info = config.get_course_info().get(course_id)
        api_url = info.get("sections_api", "")

        if api_url:
            try:
                req = urllib.request.Request(api_url)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read().decode("utf-8")
                    stages = json.loads(raw)

                    structure = self._parse_stages(stages, course_id)
                    cache[course_id] = structure
                    self._save_structure_cache(cache)
                    logger.info("课程结构已从 API 获取并缓存")
                    return structure
            except Exception as e:
                logger.warning(f"API 获取结构失败：{e}，使用降级结构")

        # 降级：返回只有课程名的空结构
        fallback = {
            "course_id": course_id,
            "course_name": info["name"],
            "chapters": [],
            "lab_map": {},
        }
        return fallback

    def _parse_stages(self, stages: list, course_id: str) -> dict:
        """将 API 返回的 stages 解析为树形结构"""
        lab_map = {}
        chapters = []

        for stage in stages:
            if stage.get("is_default"):
                continue
            chapter = {
                "name": stage["name"],
                "sections": [],
            }
            for sub in stage.get("sub_stages", []):
                if sub.get("is_default"):
                    continue
                section = {
                    "name": sub["name"],
                    "items": [],
                }
                for lab in sub.get("labs", []):
                    item = {
                        "lab_id": lab["id"],
                        "name": lab["name"],
                        "type": lab["type"],
                    }
                    section["items"].append(item)
                    lab_map[str(lab["id"])] = item
                chapter["sections"].append(section)
            chapters.append(chapter)

        return {
            "course_id": course_id,
            "course_name": config.get_course_info().get(course_id, {}).get("name", ""),
            "chapters": chapters,
            "lab_map": lab_map,
        }

    # ----------------------------------------------------------
    # 浏览器提取完成状态
    # ----------------------------------------------------------

    def _fetch_completed_lab_ids(self, study_url: str) -> Set[int]:
        """用 Selenium 访问课程页，找出所有已完成 lab 的 ID"""
        logger.info(f"访问课程页面：{study_url}")
        self.driver.get(study_url)
        time.sleep(4)

        # 检查是否被重定向到登录页
        current_url = self.driver.current_url
        if "passport" in current_url or "login" in current_url:
            logger.info("检测到未登录状态，尝试登录主站...")
            if not self._login_main_site():
                logger.warning("主站登录失败，返回空进度")
                return set()

            # 登录后重新导航
            self.driver.get(study_url)
            time.sleep(4)

        # 尝试点击「章节目录」Tab（Vue 延迟加载）
        try:
            tab_btn = self.driver.find_element(
                By.XPATH, "//*[contains(text(), '章节目录')]"
            )
            self.driver.execute_script("arguments[0].click();", tab_btn)
            time.sleep(3)
            logger.debug("已点击「章节目录」标签")
        except Exception:
            logger.debug("未找到章节目录标签，可能已自动加载")

        # 👇 核心：用 JavaScript 提取完成状态
        completed_ids = self._extract_completed_via_js()
        logger.info(f"提取到 {len(completed_ids)} 个已完成 lab")

        if completed_ids:
            return completed_ids

        # 若 JS 提取失败，兜底：遍历 DOM
        logger.debug("JS 提取为空，使用 DOM 遍历兜底...")
        return self._extract_completed_via_dom()

    def _login_main_site(self) -> bool:
        """在 www.lanqiao.cn 登录"""
        try:
            self.driver.get("https://passport.lanqiao.cn/login/")
            time.sleep(3)

            username_input = self.driver.find_element(
                By.CSS_SELECTOR, "input[type='text'], input[placeholder*='手机']"
            )
            password_input = self.driver.find_element(
                By.CSS_SELECTOR, "input[type='password']"
            )

            username_input.clear()
            username_input.send_keys(config.LANQIAO_USERNAME)
            time.sleep(0.3)
            password_input.clear()
            password_input.send_keys(config.LANQIAO_PASSWORD)
            time.sleep(0.3)

            login_btn = self.driver.find_element(
                By.XPATH, "//button[contains(text(), '登录')]"
            )
            login_btn.click()
            time.sleep(5)

            # 检查是否跳转（表示登录成功）
            if "passport" not in self.driver.current_url:
                logger.info("主站登录成功")
                return True

            # 处理验证码
            page_text = self.driver.page_source
            if "验证码" in page_text or "滑块" in page_text:
                logger.info("主站需要验证码，请在浏览器中完成验证...")
                input(">>> 请在浏览器中完成验证后，按回车继续 <<<")
                return True

            logger.warning("主站登录可能失败")
            return False
        except Exception as e:
            logger.error(f"主站登录异常：{e}")
            return False

    def _extract_completed_via_js(self) -> Set[int]:
        """通过 JS 从 Vue 组件 / DOM 中提取已完成 lab 的 ID"""
        script = """
        (function() {
            var results = [];
            
            // 方法1: 查找所有带 labId 属性的已完成元素
            document.querySelectorAll('[class*=\"complete\"], [class*=\"finished\"], .fa-check, [class*=\"check\"]').forEach(function(el) {
                // 向上找包含 lab/data-id 的容器
                var parent = el.closest('[data-lab-id], [data-id], [class*=\"lab\"], [class*=\"item\"], li');
                if (parent) {
                    var id = parent.getAttribute('data-lab-id') || parent.getAttribute('data-id');
                    if (id) results.push(parseInt(id));
                }
            });
            
            // 方法2: 查找 SVG 对号图标附近
            document.querySelectorAll('svg use[href*=\"check\"], svg [href*=\"check\"]').forEach(function(el) {
                var parent = el.closest('[class*=\"item\"], li, [class*=\"lab\"]');
                if (parent) {
                    var link = parent.querySelector('a');
                    if (link && link.href) {
                        var m = link.href.match(/labs\\/(\\d+)/);
                        if (m) results.push(parseInt(m[1]));
                    }
                }
            });
            
            // 方法3: 优先从 Vuex / Pinia store 拿（最准确）
            try {
                var app = document.querySelector('#__nuxt').__vue_app__;
                if (app) {
                    var pinia = app.config.globalProperties.$pinia;
                    if (pinia && pinia.state && pinia.state.value) {
                        for (var key in pinia.state.value) {
                            var s = pinia.state.value[key];
                            if (s && s.completedLabs) {
                                results = results.concat(s.completedLabs);
                            }
                            if (s && s.completedIds) {
                                results = results.concat(s.completedIds);
                            }
                        }
                    }
                }
            } catch(e) {}
            
            // 方法4: 从 window.__NUXT__ 找
            try {
                if (window.__NUXT__ && window.__NUXT__.state) {
                    for (var k in window.__NUXT__.state) {
                        var v = window.__NUXT__.state[k];
                        if (v && typeof v === 'object') {
                            if (v.completedLabs) results = results.concat(v.completedLabs);
                            if (v.completedIds) results = results.concat(v.completedIds);
                        }
                    }
                }
            } catch(e) {}
            
            return [...new Set(results)];
        })();
        """
        try:
            result = self.driver.execute_script(script)
            if result:
                return set(int(x) for x in result if x)
        except WebDriverException as e:
            logger.debug(f"JS 提取失败：{e}")
        return set()

    def _extract_completed_via_dom(self) -> Set[int]:
        """DOM 兜底遍历"""
        script = """
        (function() {
            var completed = new Set();
            
            // 找所有链接
            document.querySelectorAll('a[href*=\"labs/\"]').forEach(function(a) {
                var m = a.href.match(/labs\\/(\\d+)/);
                if (!m) return;
                var labId = parseInt(m[1]);
                
                // 检查该链接所在行是否有完成标记
                var row = a.closest('li, [class*=\"item\"], tr, [class*=\"row\"]');
                if (row) {
                    var hasCheck = row.querySelector('.fa-check, [class*=\"check\"], [class*=\"complete\"]');
                    var hasStyle = row.querySelector('[style*=\"color\"]');
                    if (hasCheck) completed.add(labId);
                }
            });
            
            return Array.from(completed);
        })();
        """
        try:
            result = self.driver.execute_script(script)
            return set(result) if result else set()
        except WebDriverException:
            return set()

    # ----------------------------------------------------------
    # 合并进度 & 统计
    # ----------------------------------------------------------

    def _merge_progress(self, structure: dict, completed_ids: Set[int]) -> dict:
        """将完成状态合并到课程结构中"""
        total = 0
        completed = 0
        items_flat = []

        for ch in structure.get("chapters", []):
            for sec in ch.get("sections", []):
                for item in sec.get("items", []):
                    total += 1
                    done = item["lab_id"] in completed_ids
                    item["completed"] = done
                    if done:
                        completed += 1
                    items_flat.append(item)

        return {
            "course_id": structure["course_id"],
            "course_name": structure["course_name"],
            "total_count": total,
            "completed_count": completed,
            "completed_ids": list(completed_ids),
            "chapters": structure["chapters"],
            "items": items_flat,
            "snapshot_time": datetime.now().isoformat(),
        }

    # ----------------------------------------------------------
    # 课程结构缓存
    # ----------------------------------------------------------

    def _load_structure_cache(self) -> dict:
        """加载课程结构缓存"""
        if self.STRUCTURE_CACHE.exists():
            try:
                return json.loads(self.STRUCTURE_CACHE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, KeyError):
                pass
        return {}

    def _save_structure_cache(self, cache: dict):
        """保存课程结构缓存"""
        self.STRUCTURE_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ----------------------------------------------------------
    # 格式化输出
    # ----------------------------------------------------------

    @staticmethod
    def format_progress_for_ai(progress: dict, new_items: List[dict] = None) -> str:
        """将进度数据格式化为 AI 友好文本"""
        lines = []
        lines.append(f"课程：{progress.get('course_name', '未知')}")
        lines.append(f"总进度：{progress.get('completed_count', 0)}/{progress.get('total_count', 0)}")

        # 本周新增
        if new_items:
            lines.append(f"\n本周新增完成（{len(new_items)} 项）：")
            for item in new_items:
                lines.append(f"  ✅ {item.get('name', '')}")
        else:
            lines.append("\n本周新增完成：无")

        # 章节详情
        lines.append("\n详细进度：")
        for ch in progress.get("chapters", []):
            ch_done = sum(1 for s in ch.get("sections", [])
                          for i in s.get("items", []) if i.get("completed"))
            ch_total = sum(len(s.get("items", [])) for s in ch.get("sections", []))
            lines.append(f"\n【{ch['name']}】（{ch_done}/{ch_total}）")

            for sec in ch.get("sections", []):
                sec_done = sum(1 for i in sec.get("items", []) if i.get("completed"))
                sec_total = len(sec.get("items", []))
                lines.append(f"  📖 {sec['name']}（{sec_done}/{sec_total}）")

                for item in sec.get("items", []):
                    mark = "✅" if item.get("completed") else "⬜"
                    lines.append(f"    {mark} {item['name']}")

        return "\n".join(lines)

    @staticmethod
    def extract_knowledge_points(progress: dict) -> List[str]:
        """从已完成项目中提取知识点关键词"""
        points = []
        keywords_map = {
            "SELECT": "SELECT 查询语句",
            "INSERT": "INSERT 插入数据",
            "UPDATE": "UPDATE 更新数据",
            "DELETE": "DELETE 删除数据",
            "WHERE": "WHERE 条件查询",
            "ORDER BY": "ORDER BY 排序",
            "GROUP BY": "GROUP BY 分组查询",
            "HAVING": "HAVING 筛选分组",
            "JOIN": "JOIN 多表连接",
            "子查询": "子查询",
            "函数": "SQL 函数",
            "约束": "完整性约束",
            "DDL": "DDL 数据定义语言",
            "DML": "DML 数据操纵语言",
            "范式": "三大范式",
            "外键": "外键约束",
            "主键": "主键约束",
            "默认值": "默认值约束",
            "唯一约束": "唯一约束",
            "非空约束": "非空约束",
            "LIMIT": "LIMIT 限定查询",
            "运算符": "运算符",
            "等值连接": "等值连接查询",
            "内连接": "内连接查询",
            "外连接": "外连接查询",
            "自然连接": "自然连接查询",
        }

        for item in progress.get("items", []):
            if item.get("completed"):
                name = item.get("name", "")
                for keyword, point in keywords_map.items():
                    if keyword in name and point not in points:
                        points.append(point)

        return points
