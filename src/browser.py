"""
浏览器自动化模块
支持 Chrome、Edge、Firefox 多种浏览器
使用独立浏览器实例，不影响用户正在使用的浏览器
"""

import os
import time
import shutil
import glob
import subprocess
import tempfile
from typing import List
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from src.config import config
from src.logger import logger, log_manager


# 浏览器进程名映射
BROWSER_PROCESSES = {
    "chrome": ["chromedriver.exe"],  # 只清理驱动，不清理浏览器
    "edge": ["msedgedriver.exe"],
    "firefox": ["geckodriver.exe"],
}


def cleanup_browser_processes(browser_type: str = "all"):
    """清理残留的浏览器驱动进程（不清理浏览器本身）"""
    try:
        if browser_type == "all":
            processes = []
            for procs in BROWSER_PROCESSES.values():
                processes.extend(procs)
        else:
            processes = BROWSER_PROCESSES.get(browser_type, [])
        
        for proc in processes:
            subprocess.run(["taskkill", "/F", "/IM", proc], 
                           capture_output=True, text=True)
        
        time.sleep(0.5)
    except Exception as e:
        logger.debug(f"清理进程时出错：{e}")


def cleanup_stale_temp_dirs():
    """清理之前崩溃遗留的浏览器临时目录"""
    try:
        temp_base = tempfile.gettempdir()
        for prefix in ["lanqiao_edge_", "lanqiao_chrome_"]:
            for dir_path in glob.glob(os.path.join(temp_base, prefix + "*")):
                try:
                    # 只清理超过 1 天的目录（避免清理正在使用的）
                    dir_age = time.time() - os.path.getmtime(dir_path)
                    if dir_age > 86400:  # 24 hours
                        shutil.rmtree(dir_path, ignore_errors=True)
                        logger.debug(f"已清理过期临时目录：{dir_path}")
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"清理临时目录时出错：{e}")


class BrowserManager:
    """浏览器管理器（独立实例，不影响用户浏览器）"""
    
    def __init__(self):
        """初始化浏览器（延迟初始化）"""
        self.driver = None
        self._initialized = False
        self._browser_type = None
        self._temp_dir = None  # 跟踪临时目录，用于清理
        
        # 清理之前崩溃遗留的临时目录
        cleanup_stale_temp_dirs()
        
        # 创建本次运行的截图目录
        self.screenshot_dir = config.SCREENSHOTS_DIR / log_manager.get_run_time()
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"截图目录：{self.screenshot_dir}")
    
    def _ensure_initialized(self):
        """确保浏览器已初始化"""
        if not self._initialized:
            self._init_browser()
            self._initialized = True
    
    def _init_browser(self):
        """初始化浏览器"""
        logger.info("正在初始化浏览器...")
        
        browser_type = config.BROWSER_TYPE.lower()
        
        if browser_type == "auto":
            cleanup_browser_processes("all")
            time.sleep(1)
            
            for browser in ["edge", "chrome", "firefox"]:
                try:
                    self._init_specific_browser(browser)
                    return
                except Exception as e:
                    logger.warning(f"{browser} 初始化失败：{e}")
            
            raise RuntimeError("无法初始化任何浏览器")
        else:
            cleanup_browser_processes(browser_type)
            time.sleep(1)
            self._init_specific_browser(browser_type)
    
    def _init_specific_browser(self, browser_type: str):
        """初始化指定类型的浏览器"""
        logger.info(f"尝试使用 {browser_type.upper()} 浏览器...")
        
        try:
            if browser_type == "edge":
                self._init_edge()
            elif browser_type == "chrome":
                self._init_chrome()
            elif browser_type == "firefox":
                self._init_firefox()
            else:
                raise ValueError(f"不支持的浏览器类型：{browser_type}")
        except Exception as e:
            error_msg = str(e).lower()
            # 驱动版本不匹配的常见错误信息
            if "version" in error_msg or "mismatch" in error_msg or "session not created" in error_msg:
                logger.error(f"{browser_type.upper()} 浏览器驱动版本不匹配！")
                logger.error("请尝试以下解决方案：")
                logger.error("  1. 更新浏览器到最新版本")
                logger.error("  2. Selenium 4.6+ 会自动下载匹配的驱动，请确保 pip 包是最新的：")
                logger.error("     pip install --upgrade selenium")
                logger.error("  3. 或在 .env 中手动指定 CHROMEDRIVER_PATH")
            raise
        
        self._browser_type = browser_type
        logger.info(f"{browser_type.upper()} 浏览器初始化成功")
    
    def _get_user_data_dir(self, browser_type: str) -> str:
        """获取独立的用户数据目录（不影响用户浏览器）"""
        # 在项目目录下创建独立的浏览器数据目录
        data_dir = config.PROJECT_ROOT / ".browser_data" / browser_type
        data_dir.mkdir(parents=True, exist_ok=True)
        return str(data_dir)
    
    def _init_edge(self):
        """初始化Edge浏览器（独立实例）"""
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        
        options = EdgeOptions()
        if config.HEADLESS:
            options.add_argument("--headless")
        
        # 使用临时目录作为用户数据目录（独立实例）
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="lanqiao_edge_")
        options.add_argument(f"--user-data-dir={temp_dir}")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("detach", True)
        
        service = EdgeService()
        self.driver = webdriver.Edge(service=service, options=options)
        self._temp_dir = temp_dir
        self._setup_driver()
        logger.info(f"Edge 浏览器数据目录：{temp_dir}")
    
    def _init_chrome(self):
        """初始化Chrome浏览器（独立实例）"""
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        
        options = ChromeOptions()
        if config.HEADLESS:
            options.add_argument("--headless")
        
        # 使用临时目录作为用户数据目录（独立实例）
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="lanqiao_chrome_")
        options.add_argument(f"--user-data-dir={temp_dir}")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("detach", True)
        
        if config.CHROMEDRIVER_PATH:
            service = ChromeService(config.CHROMEDRIVER_PATH)
        else:
            service = ChromeService()
        
        self.driver = webdriver.Chrome(service=service, options=options)
        self._temp_dir = temp_dir
        self._setup_driver()
        logger.info(f"Chrome 浏览器数据目录：{temp_dir}")
    
    def _init_firefox(self):
        """初始化Firefox浏览器（独立实例）"""
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        
        options = FirefoxOptions()
        if config.HEADLESS:
            options.add_argument("--headless")
        
        # 使用独立的配置文件
        profile_dir = self._get_user_data_dir("firefox")
        options.add_argument("-profile")
        options.add_argument(profile_dir)
        
        options.add_argument("--width=1920")
        options.add_argument("--height=1080")
        
        service = FirefoxService()
        self.driver = webdriver.Firefox(service=service, options=options)
        self._setup_driver()
    
    def _setup_driver(self):
        """设置驱动通用配置"""
        try:
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
        except Exception:
            # Firefox 不支持 CDP，跳过反检测注入
            logger.debug("CDP 命令不可用（可能为 Firefox），跳过反检测注入")
    
    def take_screenshot(self, name: str = "screenshot"):
        """截图保存"""
        try:
            filename = f"{name}.png"
            filepath = self.screenshot_dir / filename
            self.driver.save_screenshot(str(filepath))
            logger.info(f"截图已保存：{filename}")
        except Exception as e:
            logger.error(f"截图失败：{e}")
    
    def login(self) -> bool:
        """登录蓝桥SaaS平台（全自动，无需用户交互）"""
        self._ensure_initialized()
        logger.info("开始登录蓝桥SaaS平台...")
        
        try:
            # 直接访问周报页面（如果未登录会自动跳转到登录页）
            self.driver.get(config.WEEKLY_URL)
            time.sleep(3)
            
            logger.info(f"当前页面：{self.driver.current_url}")
            logger.info(f"页面标题：{self.driver.title}")
            
            # 如果已经在周报页面，说明已登录
            if "写周报" in self.driver.title or "weekly/write" in self.driver.current_url:
                logger.info("✓ 已登录，已在周报页面")
                return True
            
            # 如果不在登录页面，可能已登录
            if "登录" not in self.driver.title:
                logger.info("已登录状态，跳转到周报页面...")
                self.driver.get(config.WEEKLY_URL)
                time.sleep(3)
                return True
            
            # 需要登录
            logger.info("需要登录，开始填写登录表单...")
            time.sleep(2)
            
            # 查找输入框
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"找到 {len(all_inputs)} 个 input 元素")
            
            # 查找用户名输入框
            username_input = None
            for selector in ["input[type='text']", "input[type='tel']", "input[placeholder*='手机']"]:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        username_input = elements[0]
                        break
                except Exception:
                    continue

            # 查找密码输入框
            password_input = None
            try:
                password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            except Exception:
                pass
            
            if not username_input or not password_input:
                logger.error("未找到登录表单元素")
                self.take_screenshot("login_form_not_found")
                return False
            
            # 输入账号密码
            logger.info(f"输入账号：{config.LANQIAO_USERNAME}")
            username_input.clear()
            time.sleep(0.3)
            for char in config.LANQIAO_USERNAME:
                username_input.send_keys(char)
                time.sleep(0.05)
            time.sleep(0.5)
            
            logger.info("输入密码：****")
            password_input.clear()
            time.sleep(0.3)
            for char in config.LANQIAO_PASSWORD:
                password_input.send_keys(char)
                time.sleep(0.05)
            time.sleep(0.5)
            
            self.take_screenshot("after_input")
            
            # 点击登录按钮
            login_button = None
            for btn in self.driver.find_elements(By.TAG_NAME, "button"):
                if any(kw in btn.text for kw in ["登录", "登 录", "Login"]):
                    login_button = btn
                    break
            
            if login_button:
                login_button.click()
                logger.info("点击登录按钮")
            else:
                password_input.send_keys(Keys.RETURN)
                logger.info("按回车提交")
            
            # 等待登录处理
            time.sleep(5)
            self.take_screenshot("after_login")
            logger.info(f"登录后URL：{self.driver.current_url}")
            
            # 检查是否需要验证码
            if "登录" in self.driver.title:
                page_text = self.driver.page_source
                if "验证码" in page_text or "captcha" in page_text.lower() or "滑块" in page_text:
                    logger.info("检测到验证码，等待用户处理...")
                    logger.info("请在浏览器中完成验证并点击登录")
                    
                    # 自动等待验证码完成（最多等待60秒）
                    for i in range(60):
                        time.sleep(1)
                        if "登录" not in self.driver.title:
                            logger.info("验证码处理完成，登录成功！")
                            break
                        if i % 10 == 0 and i > 0:
                            logger.info(f"等待验证码处理... {i}秒")
                    
                    # 再次检查
                    if "登录" in self.driver.title:
                        logger.warning("验证码等待超时，继续尝试跳转...")
            
            # 登录成功，直接跳转到周报页面
            logger.info("正在跳转到周报页面...")
            self.driver.get(config.WEEKLY_URL)
            time.sleep(5)

            # 等待表单元素加载（Vue SPA 需要时间渲染）
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "textarea"))
                )
                logger.info("表单元素已加载")
            except Exception:
                logger.debug("等待 textarea 超时，继续尝试...")
            
            self.take_screenshot("weekly_page")
            logger.info(f"周报页面URL：{self.driver.current_url}")
            logger.info(f"周报页面标题：{self.driver.title}")
            
            if "写周报" in self.driver.title or "weekly/write" in self.driver.current_url:
                logger.info("✓ 已成功进入周报页面！")
                return True
            else:
                logger.warning("可能未成功进入周报页面，当前URL：" + self.driver.current_url)
                self.take_screenshot("weekly_page_fail")
                return False
            
        except Exception as e:
            logger.error(f"登录失败：{e}")
            self.take_screenshot("login_error")
            return False
    
    def navigate_to_weekly_page(self) -> bool:
        """导航到周报填写页面"""
        self._ensure_initialized()
        logger.info("正在导航到周报填写页面...")
        
        try:
            weekly_urls = [
                config.WEEKLY_URL,
                "https://saas.lanqiao.cn/saas/lyzyjsxy-lqb/student/evaluation/weekly/write/",
                "https://saas.lanqiao.cn/saas/lyzyjsxy-lqb/student/evaluation/weekly/",
            ]
            
            for url in weekly_urls:
                if not url:
                    continue
                logger.info(f"尝试URL：{url}")
                self.driver.get(url)
                time.sleep(2)
                
                if "404" not in self.driver.title and "登录" not in self.driver.title:
                    logger.info(f"找到有效页面！")
                    self.take_screenshot("weekly_page")
                    return True
            
            logger.warning("所有URL都无法访问")
            input("\n>>> 请手动打开周报页面，然后按回车继续 <<<\n")
            self.take_screenshot("weekly_page_manual")
            return True
            
        except Exception as e:
            logger.error(f"导航失败：{e}")
            return False
    
    def extract_sidebar_progress(self) -> dict:
        """
        从周报页面右侧边栏提取学习进度数据。
        优点：不需要导航到课程页面，避免浏览器离开周报页。
        """
        import re

        result = {
            "courses": [],
            "course_stats": {},   # {课程名: {rate, challenge, video, lab, document}}
            "unfinished": [],     # 未完成的项目名称
            "study_minutes": 0,   # 本周学习总时长（分钟）
        }

        # 等待侧边栏加载
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".border-card"))
            )
        except Exception:
            logger.warning("等待侧边栏加载超时")
            return result

        # 提取课程卡片（完课情况区域）
        cards = self.driver.find_elements(By.CSS_SELECTOR, ".border-card")
        for card in cards:
            try:
                card_text = card.text.strip()
                if not card_text:
                    continue

                # 匹配"完成率 XX%"的卡片 = 课程进度卡片
                rate_match = re.search(r'完成率\s*([\d.]+)\s*%', card_text)
                if rate_match:
                    # 提取课程名（第一行粗体文字）
                    bold_els = card.find_elements(By.CSS_SELECTOR, ".bold, .font-bold, b, strong")
                    course_name = ""
                    for el in bold_els:
                        t = el.text.strip()
                        if t and "%" not in t and "完成" not in t and "时长" not in t:
                            course_name = t
                            break

                    if not course_name:
                        # fallback: 取第一行非空文本
                        lines = [l.strip() for l in card_text.split("\n") if l.strip()]
                        course_name = lines[0] if lines else "未知课程"

                    result["courses"].append(course_name)
                    stats = {"rate": rate_match.group(1)}

                    # 解析 "挑战完成0/2；视频完成4/4；实验完成1/1；文档完成1/1"
                    for m in re.finditer(r'(\S+?)完成(\d+)/(\d+)', card_text):
                        stats[m.group(1)] = {"done": int(m.group(2)), "total": int(m.group(3))}

                    result["course_stats"][course_name] = stats

                # 匹配"总时长 XX 分钟"的卡片 = 学习时长卡片
                time_match = re.search(r'总时长\s*(\d+)\s*分钟', card_text)
                if time_match:
                    result["study_minutes"] = int(time_match.group(1))

            except Exception:
                continue

        # 提取未完成项目（来自黄色警告框）
        try:
            alerts = self.driver.find_elements(
                By.CSS_SELECTOR, ".ant-alert-warning .ant-alert-message, .ant-alert-warning .ant-alert-description"
            )
            for alert in alerts:
                text = alert.text.strip()
                # 提取【xxx】中的项目名
                items = re.findall(r'【(.+?)】', text)
                result["unfinished"].extend(items)
        except Exception:
            pass

        logger.info(f"侧边栏数据：课程={result['courses']}, 时长={result['study_minutes']}分钟, 未完成={len(result['unfinished'])}项")
        return result

    def get_page_info(self) -> dict:
        """读取页面信息"""
        self._ensure_initialized()
        logger.info("正在读取页面信息...")
        
        info = {
            "courses": [],
            "week_range": "",
        }
        
        try:
            # 尝试获取课程
            course_selectors = [".course-name", ".el-tag", "[class*='course']"]
            for selector in course_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        info["courses"] = [el.text.strip() for el in elements if el.text.strip()]
                        break
                except Exception:
                    continue
            
            if not info["courses"]:
                info["courses"] = [v["name"] for v in config.get_course_info().values()]
                logger.warning(f"未识别到课程，使用配置默认：{info['courses']}")
            else:
                logger.info(f"识别到课程：{info['courses']}")
            
            # 计算本周时间
            from datetime import timedelta
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            info["week_range"] = f"{monday.strftime('%Y-%m-%d')}~{sunday.strftime('%Y-%m-%d')}"
            logger.info(f"周报时间：{info['week_range']}")
            
            return info
            
        except Exception as e:
            logger.error(f"读取信息失败：{e}")
            return info
    
    def select_week_and_courses(self, courses: List[str]) -> bool:
        """自动选择「周报时间」和「关联课程」下拉框"""
        logger.info("开始选择周报时间和关联课程...")

        # ---- 选择「周报时间」（单选下拉框） ----
        try:
            # 找到第一个 ant-select（周报时间）
            week_select = self.driver.find_element(
                By.CSS_SELECTOR, ".ant-select.ant-select-enabled"
            )
            # 点击打开下拉框
            self.driver.execute_script("arguments[0].click();", week_select)
            time.sleep(1)

            # 选择第一个选项（本周）
            options = self.driver.find_elements(
                By.CSS_SELECTOR, ".ant-select-dropdown-menu-item"
            )
            if options:
                self.driver.execute_script("arguments[0].click();", options[0])
                logger.info(f"周报时间已选择：{options[0].text.strip()}")
                time.sleep(0.5)
            else:
                logger.warning("未找到周报时间选项")
        except Exception as e:
            logger.warning(f"选择周报时间失败：{e}")

        # ---- 选择「关联课程」（多选下拉框） ----
        try:
            # 找到第二个 ant-select（关联课程）
            selects = self.driver.find_elements(
                By.CSS_SELECTOR, ".ant-select.ant-select-enabled"
            )
            if len(selects) >= 2:
                course_select = selects[1]
                self.driver.execute_script("arguments[0].click();", course_select)
                time.sleep(1)

                # 逐个搜索并选择课程
                for course_name in courses:
                    try:
                        # 在搜索框中输入课程名
                        search_input = self.driver.find_element(
                            By.CSS_SELECTOR, ".ant-select-search__field"
                        )
                        search_input.clear()
                        search_input.send_keys(course_name)
                        time.sleep(1)

                        # 点击第一个匹配的选项
                        options = self.driver.find_elements(
                            By.CSS_SELECTOR, ".ant-select-dropdown-menu-item"
                        )
                        matched = False
                        for opt in options:
                            opt_text = opt.text.strip()
                            if course_name in opt_text or opt_text in course_name:
                                self.driver.execute_script("arguments[0].click();", opt)
                                logger.info(f"课程已选择：{opt_text}")
                                matched = True
                                time.sleep(0.5)
                                break
                        if not matched:
                            logger.warning(f"未找到匹配课程：{course_name}")
                    except Exception as e:
                        logger.warning(f"选择课程 {course_name} 失败：{e}")

                # 点击空白处关闭下拉框
                try:
                    body = self.driver.find_element(By.TAG_NAME, "body")
                    body.click()
                    time.sleep(0.5)
                except Exception:
                    pass

                logger.info(f"关联课程选择完成：{courses}")
            else:
                logger.warning("未找到关联课程下拉框")
        except Exception as e:
            logger.warning(f"选择关联课程失败：{e}")

        return True

    def fill_weekly_form(self, content: dict) -> bool:
        """填写周报表单（自动导航 + 多策略查找表单元素）"""
        self._ensure_initialized()
        logger.info("开始填写周报表单...")

        # 确保在周报页面（进度抓取可能导航到了其他页面）
        current = self.driver.current_url
        if "weekly/write" not in current and "evaluation" not in current:
            logger.info("当前不在周报页面，正在导航...")
            self.driver.get(config.WEEKLY_URL)
            time.sleep(5)

        # 等待 textarea 出现
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "textarea"))
            )
            logger.info("textarea 已加载")
        except Exception:
            logger.warning("等待 textarea 超时，尝试继续...")

        self.take_screenshot("before_fill")

        # 字段名与可能的 placeholder/label 关键词映射
        field_keywords = {
            "summary": ["总结", "本周学习", "学习内容", "工作总结"],
            "problem": ["问题", "遇到", "困难", "难点"],
            "solution": ["解决", "方案", "办法", "措施"],
            "plan": ["计划", "下周", "安排", "下一步"],
        }

        try:
            # 策略1：通过 placeholder 或 label 匹配 textarea
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            logger.info(f"找到 {len(textareas)} 个 textarea 元素")

            field_map = self._match_fields_by_label(textareas, field_keywords)
            if len(field_map) >= 3:
                logger.info(f"通过标签匹配到 {len(field_map)} 个字段")
                return self._fill_fields(field_map, content)

            # 策略2：通过 contenteditable 元素匹配
            logger.info("textarea 匹配不足，尝试 contenteditable 元素...")
            editables = self.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
            logger.info(f"找到 {len(editables)} 个 contenteditable 元素")

            field_map = self._match_fields_by_label(editables, field_keywords)
            if len(field_map) >= 3:
                logger.info(f"通过标签匹配到 {len(field_map)} 个 contenteditable 字段")
                return self._fill_fields(field_map, content, is_contenteditable=True)

            # 策略3：查找 div 编辑器（常见于 Vue/React 富文本）
            logger.info("尝试查找富文本编辑器...")
            editors = self.driver.find_elements(By.CSS_SELECTOR, ".ql-editor, .w-e-text, [class*='editor'], [class*='rich-text']")
            logger.info(f"找到 {len(editors)} 个编辑器元素")

            field_map = self._match_fields_by_label(editors, field_keywords)
            if len(field_map) >= 3:
                logger.info(f"通过标签匹配到 {len(field_map)} 个富文本编辑器字段")
                return self._fill_fields(field_map, content, is_richtext=True)

            # 策略4：按顺序填写（兜底，假设页面元素顺序固定）
            if len(textareas) >= 4:
                # 检查是否恰好有 4 个 textarea（排除非表单 textarea）
                # 通过 placeholder 或 class 过滤掉搜索框等非表单元素
                form_textareas = [
                    ta for ta in textareas
                    if not ta.get_attribute("placeholder") or
                       any(kw in (ta.get_attribute("placeholder") or "")
                           for kw in ["总结", "问题", "解决", "计划", "输入", "填写", "请输入"])
                ]
                if len(form_textareas) >= 4:
                    logger.warning("标签匹配失败，按 DOM 顺序填写（可能不准确）")
                    fields = ["summary", "problem", "solution", "plan"]
                    fallback_map = {fields[i]: form_textareas[i] for i in range(4)}
                    return self._fill_fields(fallback_map, content)
                else:
                    logger.warning(f"过滤后仅 {len(form_textareas)} 个表单 textarea，跳过兜底策略")

            # 策略5：查找所有可能的输入区域
            logger.warning("未找到标准表单元素，尝试通用输入...")
            all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
            logger.info(f"找到 {len(all_inputs)} 个 input 元素")

            # 截图帮助调试
            self.take_screenshot("form_elements_debug")

            logger.error("无法识别表单元素，请查看截图 form_elements_debug.png")
            return False

        except Exception as e:
            logger.error(f"填写失败：{e}")
            self.take_screenshot("fill_error")
            return False

    def _match_fields_by_label(self, elements, field_keywords: dict) -> dict:
        """
        通过元素的 placeholder、aria-label、label 关联或附近文本匹配字段
        
        Args:
            elements: DOM 元素列表
            field_keywords: 字段名到关键词列表的映射
            
        Returns:
            {field_name: element} 映射
        """
        field_map = {}
        
        for el in elements:
            # 收集元素相关的文本信息
            texts = []
            try:
                # placeholder
                ph = el.get_attribute("placeholder") or ""
                if ph:
                    texts.append(ph)
                # aria-label
                aria = el.get_attribute("aria-label") or ""
                if aria:
                    texts.append(aria)
                # name 属性
                name = el.get_attribute("name") or ""
                if name:
                    texts.append(name)
                # id 属性
                el_id = el.get_attribute("id") or ""
                if el_id:
                    texts.append(el_id)
                # 前一个兄弟元素的文本（通常是 label）
                try:
                    prev = self.driver.execute_script(
                        "return arguments[0].previousElementSibling ? arguments[0].previousElementSibling.textContent : '';", el
                    )
                    if prev:
                        texts.append(prev)
                except Exception:
                    pass
                # 父元素中的 label 文本
                try:
                    label = self.driver.execute_script(
                        "var p = arguments[0].closest('.form-item, .form-group, .ant-form-item, [class*=\"form\"]');"
                        "if (p) { var l = p.querySelector('label'); if (l) return l.textContent; }"
                        "return '';", el
                    )
                    if label:
                        texts.append(label)
                except Exception:
                    pass
            except Exception:
                pass
            
            all_text = " ".join(texts)
            
            # 匹配字段
            for field_name, keywords in field_keywords.items():
                if field_name not in field_map:
                    for kw in keywords:
                        if kw in all_text:
                            field_map[field_name] = el
                            logger.debug(f"字段 [{field_name}] 通过关键词 '{kw}' 匹配到元素 (text: {all_text[:50]})")
                            break
        
        return field_map

    def _fill_fields(self, field_map: dict, content: dict, 
                     is_contenteditable: bool = False, is_richtext: bool = False) -> bool:
        """
        填写表单字段
        
        Args:
            field_map: {field_name: element} 映射
            content: {field_name: text} 内容
            is_contenteditable: 是否为 contenteditable 元素
            is_richtext: 是否为富文本编辑器
        """
        success_count = 0
        
        for field_name, el in field_map.items():
            if field_name not in content:
                continue
            try:
                text = content[field_name]
                
                if is_richtext:
                    self.driver.execute_script(
                        "arguments[0].innerHTML = arguments[1].replace(/\\n/g, '<br>');",
                        el, text
                    )
                elif is_contenteditable:
                    self.driver.execute_script(
                        "arguments[0].innerText = arguments[1]; "
                        "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                        el, text
                    )
                else:
                    script = """
                    var textarea = arguments[0];
                    textarea.value = arguments[1];
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                    textarea.dispatchEvent(new Event('change', { bubbles: true }));
                    """
                    self.driver.execute_script(script, el, text)
                
                logger.info(f"字段 [{field_name}] 填写成功")
                success_count += 1
            except Exception as e:
                logger.error(f"字段 [{field_name}] 填写失败：{e}")
        
        if success_count > 0:
            logger.info(f"成功填写 {success_count} 个字段")
            return True
        else:
            logger.error("所有字段填写失败")
            return False
    
    def submit_form(self) -> bool:
        """提交周报表单"""
        self._ensure_initialized()
        logger.info("准备提交周报...")
        
        self.take_screenshot("before_submit")
        
        try:
            all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
            logger.info(f"找到 {len(all_buttons)} 个按钮")
            
            submit_button = None
            for btn in all_buttons:
                btn_text = btn.text.strip()
                if any(kw in btn_text for kw in ["提交", "保存", "发布", "确定"]):
                    submit_button = btn
                    logger.info(f"找到提交按钮：{btn_text}")
                    break
            
            if not submit_button:
                logger.warning("未找到提交按钮")
                # 尝试滚动页面查找更多按钮
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                
                # 再次查找
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in all_buttons:
                    btn_text = btn.text.strip()
                    if any(kw in btn_text for kw in ["提交", "保存", "发布"]):
                        submit_button = btn
                        break
                
                if not submit_button:
                    logger.error("仍未找到提交按钮")
                    self.take_screenshot("no_submit_button")
                    return False
            
            self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(0.5)
            submit_button.click()
            
            time.sleep(2)
            
            # 检查确认弹窗
            try:
                for btn in self.driver.find_elements(By.CSS_SELECTOR, ".el-button--primary"):
                    if btn.text.strip() in ["确定", "确认"]:
                        btn.click()
                        break
            except Exception:
                pass
            
            self.take_screenshot("after_submit")
            logger.info("周报提交完成！")
            return True
            
        except Exception as e:
            logger.error(f"提交失败：{e}")
            self.take_screenshot("submit_error")
            return False
    
    def close(self):
        """关闭浏览器实例并清理临时文件"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("自动化浏览器已关闭")
            except Exception:
                pass
        # 清理临时用户数据目录
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                logger.debug(f"已清理临时目录：{self._temp_dir}")
            except Exception:
                pass
            self._temp_dir = None
        # 只清理驱动进程
        cleanup_browser_processes()


# 全局浏览器实例
browser = BrowserManager()
