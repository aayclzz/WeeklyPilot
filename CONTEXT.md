# WeeklyPilot 项目上下文

## 项目概述
WeeklyPilot 是一个蓝桥SaaS平台自动化周报系统，帮助用户快速完成每周周报任务。

## 核心功能
1. 根据课程ID获取完整的课程目录结构
2. 通过可视化界面选择需要写入周报的章节和小节
3. AI 根据选择的内容生成客观、直白的周报
4. 自动填写到周报表单并提交

## 技术栈
- Python 3.8+
- Selenium (浏览器自动化)
- Flask (可视化选择界面)
- OpenAI API (AI 生成周报)

## 文件结构
```
WeeklyPilot/
├── run.bat          # Windows 启动脚本
├── run.sh           # macOS/Linux 启动脚本
├── main.py          # 主程序
├── .env.example     # 配置文件模板
├── requirements.txt # Python 依赖
├── src/             # 源代码
│   ├── config.py    # 配置管理
│   ├── browser.py   # 浏览器自动化
│   ├── ai_generator.py    # AI 周报生成
│   ├── course_catalog.py  # 课程目录获取
│   ├── selection_server.py # 可视化选择界面
│   └── style_templates.py # 周报风格模板
└── templates/       # HTML 模板
    ├── selector.html
    └── plan_selector.html
```

## 修复历史

### 2026-05-24: 修复 run.bat 语法错误
**问题**: run.bat 中的中文注释导致 cmd 解析错误，出现 "skipping was unexpected at this time" 错误。

**原因**: 
- `if not defined PY_VER ( ... )` 括号代码块中的中文注释被 cmd 误解
- 即使条件为 false，cmd 仍会解析整个括号代码块

**解决方案**:
1. 移除所有中文注释，改用英文注释
2. 使用 `goto` 替代括号代码块进行条件跳转
3. 避免在 `if` 语句中使用复杂的括号代码块

### 2026-05-24: 添加跨平台支持
**新增文件**:
- `run.sh`: macOS/Linux 启动脚本

**更新内容**:
- 更新 README.md，添加跨平台使用说明
- 更新 .gitignore，移除 README.md 的误忽略

## 配置说明

### .env 文件配置
```env
# 蓝桥平台账号（必填）
LANQIAO_USERNAME=你的手机号
LANQIAO_PASSWORD=你的密码

# AI 密钥（必填）
OPENAI_API_KEY=你的API密钥

# 课程配置（可选，留空则自动发现）
COURSE_IDS=61384,12345
COURSE_NAMES=数据库技术,Linux基础
```

### 支持的 AI 模型
- deepseek (推荐)
- qwen (通义千问)
- glm (智谱)
- moonshot (月之暗面)
- openai

## 使用方法

### Windows
```bash
run.bat              # 可视化选择模式
run.bat direct       # 直接输入模式
run.bat test 61384   # 测试模式
```

### macOS/Linux
```bash
./run.sh             # 可视化选择模式
./run.sh direct      # 直接输入模式
./run.sh test 61384  # 测试模式
```

### 通用
```bash
python main.py --select        # 可视化选择模式
python main.py --direct        # 直接输入模式
```

## 注意事项
1. 首次运行会自动创建 .env 文件并打开编辑器
2. 首次运行会自动安装 Python 依赖
3. 需要 Chrome/Edge/Firefox 浏览器
4. AI 生成的内容仅供参考，请务必审查后再提交

## GitHub 仓库
https://github.com/aayclzz/WeeklyPilot.git

## 推送到 GitHub
```bash
git add .
git commit -m "your commit message"
git push origin main
```

如果 HTTPS 推送失败，可以尝试：
1. 配置代理
2. 使用 SSH 方式
3. 使用 GitHub CLI
