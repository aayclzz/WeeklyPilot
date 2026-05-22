"""
可视化选择界面服务
提供课程目录API和选择界面
"""

import json
import socket
import threading
import webbrowser
from pathlib import Path
from typing import Optional
from flask import Flask, render_template, jsonify, request
from werkzeug.serving import make_server

from src.config import config
from src.logger import logger
from src.course_catalog import catalog_fetcher, CourseCatalog


app = Flask(__name__, 
            template_folder=str(config.PROJECT_ROOT / "templates"),
            static_folder=str(config.PROJECT_ROOT / "static") if (config.PROJECT_ROOT / "static").exists() else None)

# 存储用户选择
_user_selection = {}
_selection_event = threading.Event()

# 存储下周计划
_plan_selection = {}
_plan_event = threading.Event()


def is_port_available(port: int) -> bool:
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('localhost', port))
            return True
        except OSError:
            return False


@app.route('/')
def index():
    """主页"""
    return render_template('selector.html')


@app.route('/api/catalog/<course_id>')
def get_catalog(course_id):
    """获取单个课程目录API"""
    try:
        catalog = catalog_fetcher.fetch_by_id(course_id, use_cache=True)
        if not catalog:
            return jsonify({"error": "无法获取课程目录"}), 404
        
        return jsonify(catalog.to_dict())
    except Exception as e:
        logger.error(f"获取目录失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/all-catalogs')
def get_all_catalogs():
    """获取所有课程目录API"""
    try:
        course_ids = [x.strip() for x in config.COURSE_IDS.split(",") if x.strip()]
        course_names = [x.strip() for x in config.COURSE_NAMES.split(",") if x.strip()]
        
        if not course_ids:
            return jsonify({"error": "未配置课程ID"}), 400
        
        # 确保名称数量匹配
        while len(course_names) < len(course_ids):
            course_names.append(f"课程{course_ids[len(course_names)]}")
        
        catalogs = []
        for i, course_id in enumerate(course_ids):
            catalog = catalog_fetcher.fetch_by_id(course_id, use_cache=True)
            if catalog:
                catalogs.append(catalog.to_dict())
            else:
                logger.warning(f"无法获取课程 {course_id} 的目录")
        
        return jsonify({
            "courses": catalogs,
            "total": len(catalogs)
        })
    except Exception as e:
        logger.error(f"获取所有目录失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/selection', methods=['POST'])
def save_selection():
    """保存用户选择"""
    global _user_selection
    try:
        data = request.get_json()
        _user_selection = data
        _selection_event.set()
        logger.info(f"收到用户选择: {len(data.get('selected', []))} 项")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"保存选择失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/selection')
def get_selection():
    """获取当前选择"""
    return jsonify(_user_selection)


@app.route('/plan')
def plan_selector():
    """下周计划选择页面"""
    return render_template('plan_selector.html')


@app.route('/api/plan', methods=['POST'])
def save_plan():
    """保存下周计划"""
    global _plan_selection
    try:
        data = request.get_json()
        _plan_selection = data
        _plan_event.set()
        logger.info(f"收到下周计划: {len(data.get('plan_items', []))} 项")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"保存计划失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/plan')
def get_plan():
    """获取当前计划"""
    return jsonify(_plan_selection)


class SelectionServer:
    """选择界面服务器（支持优雅关闭）"""
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.server_thread = None
        self._server = None  # werkzeug server 实例，用于关闭
    
    def _find_available_port(self, start_port: int = 8765, max_attempts: int = 10) -> int:
        """查找可用端口"""
        for port in range(start_port, start_port + max_attempts):
            if is_port_available(port):
                return port
        raise RuntimeError(f"无法找到可用端口（尝试了 {start_port}-{start_port + max_attempts - 1}）")
    
    def _stop_server(self):
        """停止当前运行的服务器"""
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
    
    def start(self, course_id: str, course_name: str = "") -> Optional[dict]:
        """
        启动选择界面，等待用户选择
        
        Args:
            course_id: 课程ID
            course_name: 课程名称（可选）
            
        Returns:
            用户选择的结果，超时返回 None
        """
        global _user_selection, _selection_event
        
        # 停止上一个服务器实例（如果有）
        self._stop_server()
        
        # 重置状态
        _user_selection = {}
        _selection_event.clear()
        
        # 查找可用端口
        try:
            self.port = self._find_available_port(self.port)
        except RuntimeError as e:
            logger.error(str(e))
            return None
        
        # 使用 werkzeug make_server 创建可控的服务器
        self._server = make_server('localhost', self.port, app, threaded=True)
        
        self.server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.server_thread.start()
        
        # 打开浏览器
        url = f"http://localhost:{self.port}?course_id={course_id}"
        logger.info(f"正在打开选择界面: {url}")
        webbrowser.open(url)
        
        # 等待用户选择（最多等待5分钟）
        print("\n" + "=" * 60)
        print("请在浏览器中选择需要写入周报的章节和小节")
        print("选择完成后点击「确认选择」按钮")
        print("=" * 60)
        
        _selection_event.wait(timeout=300)
        
        # 选择完成，停止服务器
        self._stop_server()
        
        if _user_selection:
            logger.info(f"用户选择了 {len(_user_selection.get('selected', []))} 项")
            return _user_selection
        else:
            logger.warning("用户未完成选择或超时")
            return None
    
    def start_plan(self, course_id: str, course_name: str = "") -> Optional[dict]:
        """
        启动下周计划选择界面
        
        Args:
            course_id: 课程ID
            course_name: 课程名称（可选）
            
        Returns:
            用户选择的计划，超时返回 None
        """
        global _plan_selection, _plan_event
        
        # 停止上一个服务器实例（如果有）
        self._stop_server()
        
        # 重置状态
        _plan_selection = {}
        _plan_event.clear()
        
        # 查找可用端口
        try:
            self.port = self._find_available_port(self.port)
        except RuntimeError as e:
            logger.error(str(e))
            return None
        
        # 使用 werkzeug make_server 创建可控的服务器
        self._server = make_server('localhost', self.port, app, threaded=True)
        
        self.server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.server_thread.start()
        
        # 打开浏览器
        url = f"http://localhost:{self.port}/plan?course_id={course_id}"
        logger.info(f"正在打开计划选择界面: {url}")
        webbrowser.open(url)
        
        # 等待用户选择（最多等待5分钟）
        print("\n" + "=" * 60)
        print("请在浏览器中安排下周学习计划")
        print("将学习内容拖拽到对应日期")
        print("=" * 60)
        
        _plan_event.wait(timeout=300)
        
        # 选择完成，停止服务器
        self._stop_server()
        
        if _plan_selection:
            logger.info(f"用户安排了 {len(_plan_selection.get('plan_items', []))} 项计划")
            return _plan_selection
        else:
            logger.warning("用户未完成计划安排或超时")
            return None
    
    def stop(self):
        """停止服务器"""
        self._stop_server()


# 全局实例
selection_server = SelectionServer()


def open_selection_ui(course_id: str, course_name: str = "") -> Optional[dict]:
    """
    打开选择界面的便捷函数
    
    Args:
        course_id: 课程ID
        course_name: 课程名称
        
    Returns:
        用户选择结果
    """
    return selection_server.start(course_id, course_name)


def open_plan_ui(course_id: str, course_name: str = "") -> Optional[dict]:
    """
    打开下周计划选择界面的便捷函数
    
    Args:
        course_id: 课程ID
        course_name: 课程名称
        
    Returns:
        用户选择的计划
    """
    return selection_server.start_plan(course_id, course_name)
