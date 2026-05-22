"""
配置管理模块
负责加载 .env 配置文件并提供全局配置访问
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


def _normalize_separators(value: str) -> str:
    """
    将中文分隔符统一替换为英文分隔符
    避免用户在 .env 中误用中文逗号导致解析失败
    """
    if not value:
        return value
    # 全角逗号、顿号、分号 → 英文逗号
    for ch in ['\uff0c', '\u3001', '\uff1b']:
        value = value.replace(ch, ',')
    # 去除多余空格
    return value


# 预设的模型配置
MODEL_PRESETS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "name": "DeepSeek V2"
    },
    "deepseek-coder": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-coder",
        "name": "DeepSeek Coder"
    },
    "mimo": {
        "base_url": "https://api.xiaomi.com/v1",
        "model": "MiMo-V2.5-Pro",
        "name": "小米 MiMo"
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-turbo",
        "name": "通义千问"
    },
    "qwen-plus": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "name": "通义千问 Plus"
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "name": "智谱 GLM"
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "name": "月之暗面 Kimi"
    },
    "baichuan": {
        "base_url": "https://api.baichuan-ai.com/v1",
        "model": "Baichuan4",
        "name": "百川智能"
    },
    "yi": {
        "base_url": "https://api.lingyiwanwu.com/v1",
        "model": "yi-lightning",
        "name": "零一万物"
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "name": "OpenAI"
    }
}


class Config:
    """全局配置类"""
    
    # 项目路径
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    LOGS_DIR: Path = PROJECT_ROOT / "logs"
    SCREENSHOTS_DIR: Path = PROJECT_ROOT / "screenshots"
    
    # 蓝桥平台
    LANQIAO_USERNAME: str = os.getenv('LANQIAO_USERNAME', '')
    LANQIAO_PASSWORD: str = os.getenv('LANQIAO_PASSWORD', '')
    LANQIAO_BASE_URL: str = os.getenv('LANQIAO_BASE_URL', 'https://saas.lanqiao.cn')
    WEEKLY_URL: str = os.getenv('WEEKLY_URL', 'https://saas.lanqiao.cn/saas/lyzyjsxy-lqb/student/evaluation/weekly/write/')

    # 课程配置（逗号分隔，可配置多门课）
    # 留空则自动从 SaaS 页面发现课程（推荐）
    COURSE_IDS: str = _normalize_separators(os.getenv('COURSE_IDS', ''))
    COURSE_NAMES: str = _normalize_separators(os.getenv('COURSE_NAMES', ''))
    
    # AI配置
    AI_PROVIDER: str = os.getenv('AI_PROVIDER', 'deepseek')
    OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')
    OPENAI_BASE_URL: str = os.getenv('OPENAI_BASE_URL', '')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', '')
    
    @classmethod
    def get_ai_config(cls) -> dict:
        """获取AI配置"""
        if cls.AI_PROVIDER and cls.AI_PROVIDER in MODEL_PRESETS:
            preset = MODEL_PRESETS[cls.AI_PROVIDER]
            return {
                "api_key": cls.OPENAI_API_KEY,
                "base_url": cls.OPENAI_BASE_URL or preset["base_url"],
                "model": cls.OPENAI_MODEL or preset["model"],
                "provider_name": preset["name"]
            }
        
        return {
            "api_key": cls.OPENAI_API_KEY,
            "base_url": cls.OPENAI_BASE_URL or "https://api.deepseek.com/v1",
            "model": cls.OPENAI_MODEL or "deepseek-chat",
            "provider_name": "自定义"
        }
    
    # 定时任务
    SUBMIT_DAY: int = int(os.getenv('SUBMIT_DAY', '5'))
    SUBMIT_HOUR: int = int(os.getenv('SUBMIT_HOUR', '18'))
    
    # 浏览器
    BROWSER_TYPE: str = os.getenv('BROWSER_TYPE', 'auto')
    HEADLESS: bool = os.getenv('HEADLESS', 'False').lower() == 'true'
    CHROMEDRIVER_PATH: str = os.getenv('CHROMEDRIVER_PATH', '')
    
    # 日志
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def get_course_info(cls) -> dict:
        """
        从 .env 解析课程配置，返回 COURSE_INFO 格式的字典
        如果 COURSE_IDS 为空，返回空字典（触发自动发现）

        环境变量格式：
          COURSE_IDS=61384,12345
          COURSE_NAMES=数据库技术,Linux基础

        返回：
          { "61384": { "name": "数据库技术", "sections_api": "...", "study_url": "..." },
            "12345": { "name": "Linux基础", ... } }
        """
        # 使用缓存避免重复解析
        if hasattr(cls, "_course_info_cache"):
            return cls._course_info_cache

        ids = [x.strip() for x in cls.COURSE_IDS.split(",") if x.strip()]

        # 未配置课程 ID → 返回空，由自动发现模块填充
        if not ids:
            cls._course_info_cache = {}
            return {}

        names = [x.strip() for x in cls.COURSE_NAMES.split(",") if x.strip()]

        # 名称数量不足时自动补齐
        while len(names) < len(ids):
            names.append(f"课程{ids[len(names)]}")

        course_info = {}
        for i, cid in enumerate(ids):
            name = names[i] if i < len(names) else f"课程{cid}"
            course_info[cid] = {
                "name": name,
                "sections_api": f"https://www.lanqiao.cn/api/v2/courses/{cid}/labs/?page_size=500",
                "study_url": f"https://www.lanqiao.cn/courses/{cid}/learning/",
            }

        cls._course_info_cache = course_info
        return course_info

    @classmethod
    def needs_discovery(cls) -> bool:
        """是否需要课程自动发现（COURSE_IDS 未配置时返回 True）"""
        return not cls.COURSE_IDS.strip()

    @classmethod
    def validate(cls) -> bool:
        """验证必要配置是否完整"""
        if not cls.LANQIAO_USERNAME:
            raise ValueError("请配置 LANQIAO_USERNAME（蓝桥平台手机号）")
        if not cls.LANQIAO_PASSWORD:
            raise ValueError("请配置 LANQIAO_PASSWORD（蓝桥平台密码）")
        if not cls.OPENAI_API_KEY:
            raise ValueError("请配置 OPENAI_API_KEY（AI接口密钥）")
        return True
    
    @classmethod
    def list_models(cls):
        """列出所有可用的预设模型"""
        print("\n可用的预设模型：")
        print("-" * 50)
        for key, value in MODEL_PRESETS.items():
            print(f"  {key:15} - {value['name']}")
        print("-" * 50)


# 全局配置实例
config = Config()
