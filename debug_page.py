"""
调试脚本：查看周报页面的实际 HTML 结构
用于排查表单元素找不到的问题
"""

import sys
import time
from pathlib import Path

# 使用绝对路径，确保从任意工作目录运行都能正确 import
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.browser import browser
from selenium.webdriver.common.by import By

def debug_page():
    """调试页面结构"""
    print("=" * 60)
    print("开始调试周报页面结构")
    print("=" * 60)

    # 登录
    if not browser.login():
        print("登录失败")
        return

    print(f"\n当前URL: {browser.driver.current_url}")
    print(f"页面标题: {browser.driver.title}")

    # 等待页面加载
    time.sleep(5)

    # 1. 检查是否有 iframe
    iframes = browser.driver.find_elements(By.TAG_NAME, "iframe")
    print(f"\n找到 {len(iframes)} 个 iframe:")
    for i, iframe in enumerate(iframes):
        src = iframe.get_attribute("src") or "无src"
        name = iframe.get_attribute("name") or "无name"
        iframe_id = iframe.get_attribute("id") or "无id"
        print(f"  [{i}] src={src[:80]}, name={name}, id={iframe_id}")

    # 2. 检查 textarea
    textareas = browser.driver.find_elements(By.TAG_NAME, "textarea")
    print(f"\n找到 {len(textareas)} 个 textarea:")
    for i, ta in enumerate(textareas):
        placeholder = ta.get_attribute("placeholder") or "无"
        name = ta.get_attribute("name") or "无"
        print(f"  [{i}] name={name}, placeholder={placeholder[:50]}")

    # 3. 检查 contenteditable
    editables = browser.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
    print(f"\n找到 {len(editables)} 个 contenteditable:")
    for i, el in enumerate(editables):
        tag = el.tag_name
        class_name = el.get_attribute("class") or "无"
        print(f"  [{i}] tag={tag}, class={class_name[:60]}")

    # 4. 检查 input
    inputs = browser.driver.find_elements(By.TAG_NAME, "input")
    print(f"\n找到 {len(inputs)} 个 input:")
    for i, inp in enumerate(inputs):
        inp_type = inp.get_attribute("type") or "无"
        placeholder = inp.get_attribute("placeholder") or "无"
        name = inp.get_attribute("name") or "无"
        print(f"  [{i}] type={inp_type}, name={name}, placeholder={placeholder[:50]}")

    # 5. 检查 div 编辑器
    editors = browser.driver.find_elements(By.CSS_SELECTOR, ".ql-editor, .w-e-text, [class*='editor'], [class*='Editor']")
    print(f"\n找到 {len(editors)} 个编辑器元素:")
    for i, el in enumerate(editors):
        tag = el.tag_name
        class_name = el.get_attribute("class") or "无"
        print(f"  [{i}] tag={tag}, class={class_name[:80]}")

    # 6. 检查 Vue 组件
    vue_components = browser.driver.find_elements(By.CSS_SELECTOR, "[class*='vue'], [class*='Vue'], [data-v-]")
    print(f"\n找到 {len(vue_components)} 个 Vue 组件元素")

    # 7. 输出页面源码的关键部分
    page_source = browser.driver.page_source
    print(f"\n页面源码长度: {len(page_source)} 字符")

    # 查找表单相关关键词
    keywords = ["textarea", "contenteditable", "ql-editor", "w-e-text", "editor", "form", "submit", "提交", "保存"]
    print("\n页面源码中的关键词:")
    for kw in keywords:
        count = page_source.lower().count(kw.lower())
        if count > 0:
            print(f"  '{kw}': 出现 {count} 次")

    # 8. 如果有 iframe，进入 iframe 再检查
    if iframes:
        print("\n" + "=" * 60)
        print("进入 iframe 检查...")
        for i, iframe in enumerate(iframes):
            try:
                browser.driver.switch_to.frame(iframe)
                print(f"\n--- iframe [{i}] ---")

                tas = browser.driver.find_elements(By.TAG_NAME, "textarea")
                print(f"  textarea: {len(tas)} 个")

                editables = browser.driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']")
                print(f"  contenteditable: {len(editables)} 个")

                editors = browser.driver.find_elements(By.CSS_SELECTOR, ".ql-editor, .w-e-text, [class*='editor']")
                print(f"  编辑器: {len(editors)} 个")

                inputs = browser.driver.find_elements(By.TAG_NAME, "input")
                print(f"  input: {len(inputs)} 个")

                browser.driver.switch_to.default_content()
            except Exception as e:
                print(f"  进入 iframe 失败: {e}")
                browser.driver.switch_to.default_content()

    # 9. 保存页面源码到文件
    debug_file = config.PROJECT_ROOT / "data" / "page_debug.html"
    debug_file.parent.mkdir(parents=True, exist_ok=True)
    debug_file.write_text(page_source, encoding="utf-8")
    print(f"\n页面源码已保存到: {debug_file}")

    browser.close()
    print("\n调试完成！")

if __name__ == "__main__":
    debug_page()
