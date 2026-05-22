"""
用户周报风格模板库
直白、客观、无感情色彩的写作风格
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class CourseKnowledge:
    """课程知识点模板"""
    course_name: str
    keywords: List[str] = field(default_factory=list)
    sample_knowledge: List[str] = field(default_factory=list)


@dataclass
class WeeklyStyle:
    """周报风格配置"""
    
    summary_header: str = "本周学习{courses}课程，学习内容如下："
    
    # 课程知识点库
    course_knowledge_base: Dict[str, CourseKnowledge] = field(default_factory=lambda: {
        "数据库技术": CourseKnowledge(
            course_name="数据库技术",
            keywords=["SQL", "查询", "表", "数据库", "MySQL"],
            sample_knowledge=[
                "SELECT 查询语句",
                "WHERE 条件过滤",
                "ORDER BY 排序",
                "GROUP BY 分组",
                "INSERT 插入数据",
                "UPDATE 更新数据",
                "DELETE 删除数据"
            ]
        ),
        "国产操作系统": CourseKnowledge(
            course_name="国产操作系统",
            keywords=["命令", "终端", "Linux", "find", "grep"],
            sample_knowledge=[
                "find 查找文件",
                "grep 文本搜索",
                "chmod 权限设置",
                "算数运算符"
            ]
        ),
        "智能体开发": CourseKnowledge(
            course_name="智能体开发",
            keywords=["AI", "模型", "提示词", "API"],
            sample_knowledge=[
                "智能体概念",
                "提示词工程",
                "API调用"
            ]
        ),
        "网页设计基础": CourseKnowledge(
            course_name="网页设计基础",
            keywords=["HTML", "CSS", "JavaScript"],
            sample_knowledge=[
                "HTML基础标签",
                "CSS选择器",
                "CSS Flex布局"
            ]
        )
    })


# 全局风格实例
weekly_style = WeeklyStyle()


def get_style_prompt(field_name: str) -> str:
    """获取指定字段的风格提示词"""
    
    prompts = {
        "summary": """按照以下要求生成周报"总结"部分：

【格式要求】
- 以"本周学习XX课程，学习内容如下："开头
- 将所有知识点写成一段连贯的文字
- 使用数字序号标注每个知识点
- 有语法的内容要写出完整语法
- 适当解释一些专业名词
- 不要使用括号来解释
- 不要使用"我"、"我们"等第一人称代词

【内容要求】
- 知识点要有实质内容，不能太简短
- SQL语法要写出完整语句格式
- 命令要写出基本用法
- 选择性解释关键概念

【示例格式】
本周学习数据库技术课程，学习内容如下：1、SELECT查询语句，用于从数据库表中检索数据，基本格式为SELECT 列名 FROM 表名；2、WHERE条件过滤，用于筛选满足条件的记录，支持比较运算符和逻辑运算符；3、ORDER BY排序，可以对查询结果按指定列进行升序或降序排列；4、GROUP BY分组查询，通常与聚合函数配合使用，用于统计汇总数据。

【重要约束】
- 写成一段，不要分行
- 不要使用括号
- 不要使用"我"、"我们"
- 不要提及"挑战" """,

        "problem": """按照以下要求生成周报"所遇问题"部分：

【格式要求】
- 使用数字序号列出2-3个问题
- 问题描述简单直白
- 不使用"我"、"我们"
- 不要使用括号
- 不要有个人情感

【示例格式】
1. SQL语法记不住，容易搞混
2. 多表查询不太会写
3. 分组查询和聚合函数配合不好用

【重要约束】
- 问题要简单
- 不要太专业
- 不要使用括号
- 不要使用"我"、"我们" """,

        "solution": """按照以下要求生成周报"解决方案"部分：

【格式要求】
- 与问题一一对应
- 解决方案简单实用
- 不使用"我"、"我们"
- 不要使用括号
- 不要有个人情感

【风格要求】
- 模拟新手水平，用最简单的话说
- 方案要简短，一句话说完
- 用"多看"、"多练"、"多实践"这种重复表达
- 用"多抽课下时间练"、"多抽课下时间背"这种说法
- 不要太具体，就说多看多练就行
- 可以适当重复，像新手一样

【示例格式】
1. 多看几遍，多抽课下时间背
2. 多练，多实践，多抽课下时间练
3. 多看，多练，多抽课下时间背

【重要约束】
- 方案要简短，一句话
- 不要太具体，就说多看多练
- 不要使用括号
- 不要使用"我"、"我们" """,

        "plan": """按照以下要求生成周报"下周计划"部分：

【格式要求】
- 以"周一~周末"的固定时间轴格式呈现
- 每天的内容要具体，写出要学习的知识点名称
- 格式为"学习蓝桥云课中XX课程的XX知识点"
- 周二到周五要加上"复习前一天所学过的内容"
- 周末固定为"复习之前所学过的内容，预习下周要学习的内容"
- 不使用"我"、"我们"
- 不要使用括号

【内容要求】
- 只写知识点名称，不要包含小节类型
- 不要提及"学一学"、"练一练"、"实验"、"挑战"、"视频"、"文档"等小节类型
- 专注于具体的知识点内容

【示例格式】
周一：学习蓝桥云课中数据库技术的自然连接
周二：学习蓝桥云课中数据库技术的关系型数据库的第一范式，复习周一所学过的内容
周三：学习蓝桥云课中数据库技术的关系型数据库的第二范式，复习周二所学过的内容
周四：学习蓝桥云课中数据库技术的关系型数据库的第三范式，复习周三所学过的内容
周五：学习蓝桥云课中数据库技术的视图和索引，复习周四所学过的内容
周末：复习之前所学过的内容，预习下周要学习的内容

【重要约束】
- 每天内容要具体
- 写出知识点名称
- 按照示例格式书写
- 不要使用括号
- 不要使用"我"、"我们"
- 不要提及"学一学"、"练一练"、"实验"、"挑战"、"视频"、"文档"等小节类型 """
    }
    
    return prompts.get(field_name, "")


def get_course_knowledge(course_name: str) -> CourseKnowledge:
    """获取指定课程的知识点库"""
    style = weekly_style
    for key, value in style.course_knowledge_base.items():
        if key in course_name or course_name in key:
            return value
    return CourseKnowledge(course_name=course_name, sample_knowledge=[f"{course_name}相关知识点"])
