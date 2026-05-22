"""
AI内容生成模块
基于用户选择的学习内容生成周报
直白、客观、无感情色彩的风格
模拟新手水平，不使用括号解释
"""

from typing import Dict, List, Optional
from openai import OpenAI
from src.config import config
from src.logger import logger
from src.style_templates import get_style_prompt


class WeeklyGenerator:
    """周报内容生成器"""
    
    # 需要过滤的小节类型（下周计划中不应出现）
    FILTERED_ITEM_TYPES = [
        "video",           # 视频
        "doc",             # 文档
        "lab",             # 实验
        "course_challenge", # 挑战
        "challenge",       # 挑战
        "learn",           # 学一学
        "practice",        # 练一练
        "experiment",      # 实验
    ]
    
    def __init__(self):
        """初始化AI客户端（延迟初始化）"""
        self._client = None
        self._ai_config = None
    
    @property
    def ai_config(self):
        """获取AI配置"""
        if self._ai_config is None:
            self._ai_config = config.get_ai_config()
        return self._ai_config
    
    @property
    def client(self):
        """延迟初始化客户端"""
        if self._client is None:
            api_key = self.ai_config.get("api_key", "")
            if not api_key:
                raise ValueError("请在 .env 文件中配置 OPENAI_API_KEY")
            
            self._client = OpenAI(
                api_key=api_key,
                base_url=self.ai_config["base_url"]
            )
            logger.info(f"AI客户端初始化成功")
            logger.info(f"  模型提供商：{self.ai_config['provider_name']}")
            logger.info(f"  模型名称：{self.ai_config['model']}")
        return self._client
    
    @property
    def model(self):
        return self.ai_config["model"]
    
    def _call_ai(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        """调用AI接口生成内容（含重试机制）"""
        import time
        
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1500
                )
                content = response.choices[0].message.content.strip()
                # 记录 token 用量
                if hasattr(response, 'usage') and response.usage:
                    logger.debug(f"Token 用量 — prompt: {response.usage.prompt_tokens}, "
                                 f"completion: {response.usage.completion_tokens}, "
                                 f"total: {response.usage.total_tokens}")
                return content
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # API Key 无效等不可重试的错误，直接抛出
                if "401" in error_msg or "invalid" in error_msg.lower():
                    logger.error("="*50)
                    logger.error("API Key 无效！请检查：")
                    logger.error("1. .env 文件中的 OPENAI_API_KEY 是否正确")
                    logger.error("2. API Key 是否过期或余额不足")
                    logger.error(f"3. 当前模型：{self.ai_config['provider_name']} - {self.model}")
                    logger.error("="*50)
                    raise
                
                # 可重试的错误（网络超时、限频等）
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(f"AI 调用失败（第 {attempt + 1} 次），{wait_time}秒后重试：{e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"AI 调用失败（已重试 {max_retries} 次）：{e}")
        
        raise last_error or RuntimeError("AI 调用失败：未知错误")
    
    def generate_from_selection(
        self,
        course_name: str,
        selected_items: List[dict],
        plan_items: Optional[List[dict]] = None,
    ) -> Dict[str, str]:
        """
        基于用户选择的内容生成完整周报
        
        Args:
            course_name: 课程名称
            selected_items: 用户选择的学习项列表
            plan_items: 用户选择的下周计划项列表（可选）
        
        Returns:
            {"summary": "...", "problem": "...", "solution": "...", "plan": "..."}
        """
        logger.info(f"开始生成周报，课程：{course_name}，选择项数：{len(selected_items)}")
        
        # 过滤掉挑战类型
        filtered_items = [
            item for item in selected_items 
            if item.get("item_type") not in ["course_challenge", "challenge"]
        ]
        
        if not filtered_items:
            logger.warning("过滤挑战后无可用内容")
            filtered_items = selected_items
        
        # 构建内容描述
        content_desc = self._build_content_description(course_name, filtered_items)
        
        # 依次生成各部分
        summary = self.generate_summary(course_name, content_desc)
        problems = self.generate_problems(course_name, summary)
        solutions = self.generate_solutions(problems)
        
        # 生成下周计划（如果有选择的计划项）
        if plan_items:
            plan = self.generate_plan_from_selection(course_name, plan_items)
        else:
            plan = self.generate_plan(course_name, filtered_items)
        
        result = {
            "summary": summary,
            "problem": problems,
            "solution": solutions,
            "plan": plan,
        }
        
        logger.info("周报内容生成完成")
        return result
    
    def _build_content_description(self, course_name: str, items: List[dict]) -> str:
        """构建学习内容描述"""
        # 提取所有学习项名称
        item_names = []
        for item in items:
            name = item.get("item_name", "")
            if name and name not in item_names:
                item_names.append(name)
        
        # 构建简洁描述
        lines = [f"课程：{course_name}", "学习内容："]
        for i, name in enumerate(item_names, 1):
            lines.append(f"{i}. {name}")
        
        return "\n".join(lines)
    
    def generate_summary(self, course_name: str, content_desc: str) -> str:
        """生成总结部分"""
        logger.info("开始生成总结")
        
        style_prompt = get_style_prompt("summary")
        
        user_prompt = f"""本周学习的内容如下：

{content_desc}

请根据上述学习内容，生成周报的"总结"部分。要求：
1. 以"本周学习{course_name}课程，学习内容如下："开头
2. 将所有知识点写成一段连贯的文字
3. 使用数字序号标注每个知识点
4. 有语法的内容要写出完整语法
5. 适当解释一些专业名词
6. 不要使用括号来解释
7. 不要使用"我"、"我们"等第一人称代词
8. 不要提及"挑战" """

        system_prompt = (
            "你是一个周报生成助手。根据提供的学习内容生成详细的总结，"
            "写成一段连贯的文字，有语法的写出完整语法，适当解释专业名词，"
            "不使用括号，不使用第一人称代词。"
        )
        return self._call_ai(system_prompt, style_prompt + "\n\n" + user_prompt)
    
    def generate_problems(self, course_name: str, summary: str) -> str:
        """生成所遇问题部分"""
        logger.info("开始生成所遇问题")
        
        style_prompt = get_style_prompt("problem")
        
        user_prompt = f"""本周学习课程：{course_name}

已生成的总结内容：
{summary}

请根据上述学习内容，生成2-3个可能遇到的问题。要求：
1. 模拟新手水平，不要太专业
2. 问题描述简单直白
3. 不要使用括号
4. 不要使用'我'、'我们'
5. 不要有个人情感"""

        system_prompt = "你是一个周报生成助手。模拟新手水平生成简单的问题描述，不使用括号，不使用第一人称代词。"
        return self._call_ai(system_prompt, style_prompt + "\n\n" + user_prompt)
    
    def generate_solutions(self, problems: str) -> str:
        """生成解决方案部分"""
        logger.info("开始生成解决方案")
        
        style_prompt = get_style_prompt("solution")
        
        user_prompt = f"""已生成的所遇问题：
{problems}

请根据上述问题，生成对应的解决方案。要求：
1. 与问题一一对应
2. 模拟新手水平，不要太专业
3. 解决方案简单实用
4. 不要使用括号
5. 不要使用'我'、'我们'
6. 不要有个人情感"""

        system_prompt = "你是一个周报生成助手。模拟新手水平生成简单的解决方案，不使用括号，不使用第一人称代词。"
        return self._call_ai(system_prompt, style_prompt + "\n\n" + user_prompt)
    
    def generate_plan(self, course_name: str, items: List[dict]) -> str:
        """生成下周计划"""
        logger.info("开始生成下周计划")
        
        style_prompt = get_style_prompt("plan")
        
        # 过滤掉不需要的类型（视频、文档、实验、挑战等）
        filtered_items = [
            item for item in items
            if item.get("item_type") not in self.FILTERED_ITEM_TYPES
        ]
        
        # 如果过滤后没有内容，使用原始列表
        if not filtered_items:
            logger.warning("过滤后无可用内容，使用原始列表")
            filtered_items = items
        
        # 提取学习内容，按章节分组
        chapters = {}
        for item in filtered_items:
            ch_name = item.get("chapter_name", "")
            item_name = item.get("item_name", "")
            item_type = item.get("item_type", "")
            if ch_name and item_name:
                if ch_name not in chapters:
                    chapters[ch_name] = []
                # 只添加不在过滤列表中的内容
                if item_name not in chapters[ch_name]:
                    chapters[ch_name].append(item_name)
        
        # 构建详细的内容描述
        content_lines = []
        for ch_name, ch_items in chapters.items():
            content_lines.append(f"{ch_name}：{'、'.join(ch_items[:3])}")
        
        content_desc = "\n".join(content_lines) if content_lines else "相关课程内容"
        
        user_prompt = f"""下周继续学习课程：{course_name}

可能学习的内容方向：
{content_desc}

请生成下周的学习计划，要求：
1. 以"周一~周末"的固定时间轴格式呈现
2. 每天的内容要具体，写出要学习的知识点名称
3. 周末固定为"复习之前所学过的内容，预习下周要学习的内容"
4. 不要使用括号
5. 不要使用'我'、'我们'
6. 每天学习1-2个知识点
7. 不要提及"学一学"、"练一练"、"实验"、"挑战"、"视频"、"文档"等小节类型
8. 只写知识点名称，不要包含小节类型"""

        system_prompt = "你是一个周报生成助手。生成具体的学习计划，每天写出要学习的知识点名称，周末统一写'复习之前所学过的内容，预习下周要学习的内容'，不使用括号，不使用第一人称代词。不要提及'学一学'、'练一练'、'实验'、'挑战'、'视频'、'文档'等小节类型，只写知识点名称。"
        return self._call_ai(system_prompt, style_prompt + "\n\n" + user_prompt)
    
    def generate_plan_from_selection(self, course_name: str, plan_items: List[dict]) -> str:
        """基于用户选择的内容生成下周计划"""
        logger.info("开始生成下周计划（基于用户选择）")
        
        # 过滤掉不需要的类型（视频、文档、实验、挑战等）
        filtered_plan_items = [
            item for item in plan_items
            if item.get("item_type") not in self.FILTERED_ITEM_TYPES
        ]
        
        # 如果过滤后没有内容，使用原始列表
        if not filtered_plan_items:
            logger.warning("过滤后无可用计划内容，使用原始列表")
            filtered_plan_items = plan_items
        
        # 按天分组（工作日 + 周末）
        weekdays = ["周一", "周二", "周三", "周四", "周五"]
        weekend_days = ["周六", "周日"]
        plan_by_day = {day: [] for day in weekdays + weekend_days}
        
        for item in filtered_plan_items:
            day = item.get("day", "")
            name = item.get("item_name", "")
            if day in plan_by_day and name:
                plan_by_day[day].append(name)
        
        # 收集周末内容（周六 + 周日合并）
        weekend_items = []
        for day in weekend_days:
            weekend_items.extend(plan_by_day[day])
        # 去重
        weekend_items = list(dict.fromkeys(weekend_items))
        
        # 构建计划文本 - 严格遵守风格规范
        lines = []
        for i, day in enumerate(weekdays):
            if plan_by_day[day]:
                content = "、".join(plan_by_day[day])
                if i == 0:
                    lines.append(f"{day}：学习蓝桥云课中{course_name}的{content}")
                else:
                    prev_day = weekdays[i-1]
                    lines.append(f"{day}：学习蓝桥云课中{course_name}的{content}，复习{prev_day}所学过的内容")
            else:
                if i == 0:
                    lines.append(f"{day}：学习蓝桥云课中{course_name}的相关内容")
                else:
                    prev_day = weekdays[i-1]
                    lines.append(f"{day}：学习蓝桥云课中{course_name}的相关内容，复习{prev_day}所学过的内容")
        
        # 添加周末（如果有安排具体内容则展示，否则用默认文案）
        if weekend_items:
            content = "、".join(weekend_items)
            lines.append(f"周末：复习之前所学过的内容，预习下周要学习的内容，练习{content}")
        else:
            lines.append("周末：复习之前所学过的内容，预习下周要学习的内容")
        
        return "\n".join(lines)
    
    @staticmethod
    def _has_numbered_list(text: str) -> bool:
        """检查文本是否包含数字序号列表（兼容 '1.' 和 '1、' 格式）"""
        import re
        return bool(re.search(r'(?:^|\n)\s*1[.、．]', text))

    def validate_style(self, content: Dict[str, str], courses: List[str]) -> Dict[str, bool]:
        """校验生成内容是否符合风格要求"""
        logger.info("开始校验内容风格...")
        
        results = {}
        
        # 检查总结
        summary = content.get("summary", "")
        results["summary"] = (
            not any(word in summary for word in ["我", "我们", "挑战", "（", "）"]) and
            any(c in summary for c in courses) and
            self._has_numbered_list(summary)
        )
        
        # 检查问题
        problem = content.get("problem", "")
        results["problem"] = (
            self._has_numbered_list(problem) and
            not any(word in problem for word in ["我", "我们", "挑战", "（", "）"])
        )
        
        # 检查解决方案
        solution = content.get("solution", "")
        results["solution"] = (
            self._has_numbered_list(solution) and
            not any(word in solution for word in ["我", "我们", "（", "）"])
        )
        
        # 检查计划
        plan = content.get("plan", "")
        results["plan"] = (
            "周一" in plan and "周二" in plan and "周三" in plan and "周四" in plan and "周五" in plan and
            "周末" in plan and
            not any(word in plan for word in ["我", "我们", "（", "）"])
        )
        
        for field_name, passed in results.items():
            status = "✅ 通过" if passed else "❌ 未通过"
            logger.info(f"  {field_name}: {status}")
        
        return results


# 全局生成器实例
generator = WeeklyGenerator()
