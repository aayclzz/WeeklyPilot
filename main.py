"""
蓝桥SaaS平台自动化周报系统 - 主程序
V4.1 — 可视化章节选择 + 兼容性增强
"""

import sys
import argparse
from datetime import date
from pathlib import Path
from typing import List

# 修复 Windows 终端 emoji 编码问题
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 添加src到路径（使用绝对路径，确保从任意工作目录运行都能正确 import）
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config, Config
from src.logger import logger
from src.ai_generator import generator
from src.browser import browser
from src.course_catalog import catalog_fetcher
from src.selection_server import open_selection_ui, open_plan_ui


def run_select_mode():
    """
    可视化选择模式：
    1. 用户输入课程ID
    2. 获取课程目录
    3. 打开可视化选择界面
    4. 基于选择生成周报
    5. 填写并提交
    """
    logger.info("=" * 50)
    logger.info("可视化选择模式")
    logger.info("=" * 50)
    
    try:
        # 1. 获取课程ID（优先使用 .env 配置）
        course_id = _get_course_id()
        if not course_id:
            return False
        
        # 2. 获取课程目录
        logger.info(f"正在获取课程 {course_id} 的目录...")
        catalog = catalog_fetcher.fetch_by_id(course_id, use_cache=True)
        
        if not catalog:
            logger.error("无法获取课程目录，请检查课程ID是否正确")
            return False
        
        logger.info(f"课程：{catalog.course_name}")
        logger.info(f"共 {len(catalog.chapters)} 章")
        
        # 3. 打开可视化选择界面
        logger.info("正在打开可视化选择界面...")
        selection = open_selection_ui(course_id, catalog.course_name)
        
        if not selection or not selection.get("selected"):
            logger.warning("用户未完成选择或取消了选择")
            return False
        
        selected_items = selection["selected"]
        course_name = selection.get("course_name", catalog.course_name)
        logger.info(f"用户选择了 {len(selected_items)} 项")
        
        # 4. 打开下周计划选择界面
        logger.info("正在打开下周计划选择界面...")
        plan_selection = open_plan_ui(course_id, catalog.course_name)
        
        plan_items = None
        if plan_selection and plan_selection.get("plan_items"):
            plan_items = plan_selection["plan_items"]
            logger.info(f"用户安排了 {len(plan_items)} 项下周计划")
        else:
            logger.info("用户未安排下周计划，将自动生成")
        
        # 5. AI生成周报
        logger.info("正在生成周报...")
        try:
            weekly_content = generator.generate_from_selection(
                course_name=course_name,
                selected_items=selected_items,
                plan_items=plan_items,
            )
        except Exception as e:
            logger.warning(f"AI生成失败：{e}")
            weekly_content = _fallback_content_from_selection(course_name, selected_items)
        
        # 6. 显示生成结果
        print("\n" + "=" * 60)
        print("📋 生成的周报内容：")
        print("=" * 60)
        print(f"\n【总结】\n{weekly_content['summary']}")
        print(f"\n【所遇问题】\n{weekly_content['problem']}")
        print(f"\n【解决方案】\n{weekly_content['solution']}")
        print(f"\n【下周计划】\n{weekly_content['plan']}")
        print("=" * 60)
        
        # 7. 风格校验
        validation = generator.validate_style(weekly_content, [course_name])
        print("\n【风格校验】")
        for field_name, passed in validation.items():
            print(f"  {field_name}: {'✅ 通过' if passed else '❌ 未通过'}")
        
        # 8. 保存到文件
        reports_dir = config.PROJECT_ROOT / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"weekly_{date.today().isoformat()}.md"
        _save_report_file(report_file, date.today().isoformat(), weekly_content)
        logger.info(f"周报已保存到：{report_file}")
        
        # 9. 自动打开蓝桥平台并填写周报
        print("\n" + "=" * 60)
        print("🚀 正在打开蓝桥平台...")
        print("=" * 60)
        
        return _submit_to_lanqiao(weekly_content, course_name)
    
    except Exception as e:
        logger.error(f"执行异常：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_direct_mode():
    """
    直接输入模式（不使用可视化界面）：
    1. 获取课程ID
    2. 显示课程目录
    3. 用户选择章节/小节编号
    4. 基于选择生成周报
    """
    logger.info("=" * 50)
    logger.info("直接输入模式")
    logger.info("=" * 50)
    
    try:
        # 1. 获取课程ID（优先使用 .env 配置）
        course_id = _get_course_id()
        if not course_id:
            return False
        
        # 2. 获取课程目录
        logger.info(f"正在获取课程 {course_id} 的目录...")
        catalog = catalog_fetcher.fetch_by_id(course_id, use_cache=True)
        
        if not catalog:
            logger.error("无法获取课程目录")
            return False
        
        # 3. 显示目录结构
        print(f"\n📚 课程：{catalog.course_name}")
        print("=" * 60)
        
        all_items = []
        item_idx = 0
        
        for ch_idx, chapter in enumerate(catalog.chapters):
            print(f"\n【第{ch_idx+1}章】{chapter.name}")
            for sec_idx, section in enumerate(chapter.sections):
                print(f"  {ch_idx+1}.{sec_idx+1} {section.name}")
                for lab in section.items:
                    item_idx += 1
                    all_items.append({
                        "chapter_name": chapter.name,
                        "section_name": section.name,
                        "item_name": lab.name,
                        "item_type": lab.type,
                    })
                    type_mark = {"video": "📹", "doc": "📄", "lab": "🔬"}.get(lab.type, "📝")
                    print(f"    [{item_idx}] {type_mark} {lab.name}")
        
        print("\n" + "=" * 60)
        
        # 4. 用户选择
        selection_input = input(
            "\n请输入要包含的小节编号（用逗号分隔，如 1,3,5-8）: "
        ).strip()
        
        if not selection_input:
            logger.warning("未输入选择")
            return False
        
        # 解析选择
        selected_indices = _parse_selection(selection_input, len(all_items))
        selected_items = [all_items[i-1] for i in selected_indices if 0 < i <= len(all_items)]
        
        if not selected_items:
            logger.warning("未选择任何有效项")
            return False
        
        logger.info(f"选择了 {len(selected_items)} 项")
        
        # 5. AI生成周报
        logger.info("正在生成周报...")
        course_name = catalog.course_name
        
        try:
            weekly_content = generator.generate_from_selection(
                course_name=course_name,
                selected_items=selected_items,
            )
        except Exception as e:
            logger.warning(f"AI生成失败：{e}")
            weekly_content = _fallback_content_from_selection(course_name, selected_items)
        
        # 6. 显示生成结果
        print("\n" + "=" * 60)
        print("📋 生成的周报内容：")
        print("=" * 60)
        print(f"\n【总结】\n{weekly_content['summary']}")
        print(f"\n【所遇问题】\n{weekly_content['problem']}")
        print(f"\n【解决方案】\n{weekly_content['solution']}")
        print(f"\n【下周计划】\n{weekly_content['plan']}")
        print("=" * 60)
        
        # 7. 风格校验
        validation = generator.validate_style(weekly_content, [course_name])
        print("\n【风格校验】")
        for field_name, passed in validation.items():
            print(f"  {field_name}: {'✅ 通过' if passed else '❌ 未通过'}")
        
        # 8. 保存到文件
        reports_dir = config.PROJECT_ROOT / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"weekly_{date.today().isoformat()}.md"
        _save_report_file(report_file, date.today().isoformat(), weekly_content)
        logger.info(f"周报已保存到：{report_file}")
        
        # 9. 询问是否提交
        submit = input("\n是否提交到蓝桥平台？(y/n): ").strip().lower()
        if submit == 'y':
            return _submit_to_lanqiao(weekly_content, course_name)
        else:
            print(f"\n📄 周报已保存到：{report_file}")
            return True
    
    except Exception as e:
        logger.error(f"执行异常：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_test_mode(course_id: str = None):
    """
    测试模式：仅生成内容，不提交
    """
    logger.info("=" * 50)
    logger.info("测试模式（仅生成，不提交）")
    logger.info("=" * 50)
    
    try:
        if not course_id:
            course_id = _get_course_id()
        
        if not course_id:
            return False
        
        # 获取课程目录
        catalog = catalog_fetcher.fetch_by_id(course_id, use_cache=True)
        if not catalog:
            logger.error("无法获取课程目录")
            return False
        
        # 使用前3个item作为测试数据
        all_items = catalog.get_all_items()[:3]
        if not all_items:
            logger.error("课程目录为空")
            return False
        
        logger.info(f"使用 {len(all_items)} 项进行测试")
        
        # 生成周报
        weekly_content = generator.generate_from_selection(
            course_name=catalog.course_name,
            selected_items=all_items,
        )
        
        # 显示结果
        print("\n" + "=" * 60)
        print("📋 测试生成的周报内容：")
        print("=" * 60)
        print(f"\n【总结】\n{weekly_content['summary']}")
        print(f"\n【所遇问题】\n{weekly_content['problem']}")
        print(f"\n【解决方案】\n{weekly_content['solution']}")
        print(f"\n【下周计划】\n{weekly_content['plan']}")
        print("=" * 60)
        
        return True
    
    except Exception as e:
        logger.error(f"测试异常：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_catalog_mode(course_id: str = None):
    """
    目录查看模式：仅显示课程目录结构
    """
    logger.info("=" * 50)
    logger.info("课程目录查看模式")
    logger.info("=" * 50)
    
    try:
        if not course_id:
            course_id = _get_course_id()
        
        if not course_id:
            return False
        
        # 获取课程目录
        catalog = catalog_fetcher.fetch_by_id(course_id, use_cache=False)
        if not catalog:
            logger.error("无法获取课程目录")
            return False
        
        # 显示目录结构
        print(f"\n📚 课程：{catalog.course_name}")
        print(f"   课程ID：{catalog.course_id}")
        print(f"   获取时间：{catalog.fetch_time}")
        print("=" * 60)
        
        total_sections = 0
        total_items = 0
        
        for ch_idx, chapter in enumerate(catalog.chapters):
            print(f"\n【第{ch_idx+1}章】{chapter.name}")
            for sec_idx, section in enumerate(chapter.sections):
                total_sections += 1
                total_items += len(section.items)
                print(f"  {ch_idx+1}.{sec_idx+1} {section.name} ({len(section.items)}项)")
                for lab in section.items:
                    type_mark = {"video": "📹", "doc": "📄", "lab": "🔬"}.get(lab.type, "📝")
                    print(f"      {type_mark} {lab.name}")
        
        print("\n" + "=" * 60)
        print(f"📊 统计：{len(catalog.chapters)}章 · {total_sections}节 · {total_items}项")
        
        return True
    
    except Exception as e:
        logger.error(f"查看异常：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def _parse_selection(selection_str: str, max_idx: int) -> List[int]:
    """解析用户输入的选择范围"""
    indices = []
    parts = selection_str.split(",")
    
    for part in parts:
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-")
                start = int(start.strip())
                end = int(end.strip())
                indices.extend(range(start, end + 1))
            except ValueError:
                continue
        else:
            try:
                indices.append(int(part))
            except ValueError:
                continue
    
    # 去重并过滤有效范围
    return sorted(set(i for i in indices if 1 <= i <= max_idx))


def _get_course_id() -> str:
    """
    获取课程ID
    优先使用 .env 中配置的 COURSE_IDS，如果未配置则提示用户输入
    """
    # 从配置中获取课程ID列表
    course_ids = [x.strip() for x in config.COURSE_IDS.split(",") if x.strip()]
    course_names = [x.strip() for x in config.COURSE_NAMES.split(",") if x.strip()]
    
    if course_ids:
        # 自动使用第一个课程ID
        course_id = course_ids[0]
        course_name = course_names[0] if course_names else f"课程{course_id}"
        logger.info(f"使用配置的课程ID：{course_id}（{course_name}）")
        return course_id
    
    # 未配置课程ID，提示用户输入
    print("\n⚠️  未在 .env 中配置 COURSE_IDS")
    print("提示：在蓝桥云课打开课程页面，URL 中的数字就是课程ID")
    print("例如：https://www.lanqiao.cn/courses/61384/ 中的 61384")
    course_id = input("\n请输入课程ID: ").strip()
    if not course_id:
        logger.error("未输入课程ID")
        return None
    return course_id


def _fallback_content_from_selection(course_name: str, items: List[dict]) -> dict:
    """生成降级内容"""
    item_names = [item.get("item_name", "") for item in items[:5]]
    items_text = "\n".join(f"{i+1}. {name}" for i, name in enumerate(item_names) if name)
    
    return {
        "summary": f"本周学习{course_name}课程，学习内容如下：\n{items_text}",
        "problem": f"1. {course_name}内容较多，短期内无法完全掌握\n2. 部分知识点容易混淆\n3. 某些概念理解需要加强",
        "solution": "1. 通过实践练习巩固所学知识\n2. 查阅相关资料加深理解\n3. 针对薄弱环节进行专项练习",
        "plan": "周一：学习新课程内容\n周二：学习新内容，复习周一所学\n周三：学习新内容，复习周二所学\n周四：学习新内容，复习周三所学\n周五：学习新内容，复习周四所学\n周末：复习之前所学过的内容，预习下周要学习的内容"
    }


def _save_report_file(filepath: Path, week_label: str, content: dict):
    """将周报内容保存为 Markdown 文件"""
    text = f"""# 周报 — {week_label}

## 总结

{content.get('summary', '')}

## 所遇问题

{content.get('problem', '')}

## 解决方案

{content.get('solution', '')}

## 下周计划

{content.get('plan', '')}
"""
    filepath.write_text(text, encoding="utf-8")


def _submit_to_lanqiao(weekly_content: dict, course_name: str) -> bool:
    """
    提交周报到蓝桥平台
    流程：
    1. 自动登录蓝桥平台
    2. 进入周报界面
    3. 自动填写周报内容
    4. 等待用户手动选择周报时间和关联课程
    5. 用户确认后手动提交
    """
    try:
        # 验证配置
        Config.validate()
        
        # 登录
        logger.info("正在登录蓝桥平台...")
        if not browser.login():
            logger.error("登录失败")
            return False
        
        # 进入周报界面并填写表单
        logger.info("正在进入周报界面并填写内容...")
        if not browser.fill_weekly_form(weekly_content):
            logger.error("填写表单失败")
            return False
        
        # 提示用户手动操作
        print("\n" + "=" * 60)
        print("✅ 周报内容已自动填写完成！")
        print("=" * 60)
        print("\n请在浏览器中完成以下操作：")
        print("  1. 选择周报时间")
        print("  2. 选择关联课程")
        print("  3. 检查填写的内容")
        print("  4. 点击「提交」按钮")
        print("\n完成后按回车键关闭浏览器。")
        print("=" * 60)
        
        # 等待用户确认（支持 Ctrl+C 取消）
        try:
            input("\n按回车键关闭浏览器...")
        except KeyboardInterrupt:
            print("\n操作已取消")
        
        logger.info("🎉 周报提交流程完成！")
        return True
    
    except KeyboardInterrupt:
        print("\n操作已取消")
        return False
    except Exception as e:
        logger.error(f"提交异常：{e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        browser.close()


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description="蓝桥SaaS平台自动化周报系统 V4.1 — 可视化选择版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--select", action="store_true", help="可视化选择模式（推荐）")
    parser.add_argument("--direct", action="store_true", help="直接输入模式（命令行选择）")
    parser.add_argument("--test", action="store_true", help="测试模式：仅生成内容，不提交")
    parser.add_argument("--catalog", action="store_true", help="查看课程目录结构")
    parser.add_argument("--course-id", type=str, default="", help="课程ID（配合 --test 或 --catalog 使用）")
    parser.add_argument("--clear-cache", action="store_true", help="清除课程目录缓存")
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║     蓝桥SaaS平台自动化周报系统 V4.1                          ║
║     可视化章节选择 · 基于选择内容生成                         ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    if args.clear_cache:
        catalog_fetcher.clear_cache()
        print("✅ 缓存已清除")
    elif args.catalog:
        run_catalog_mode(args.course_id or None)
    elif args.test:
        run_test_mode(args.course_id or None)
    elif args.direct:
        run_direct_mode()
    else:
        # 默认使用可视化选择模式
        run_select_mode()


if __name__ == "__main__":
    main()
