"""
课程目录获取模块
根据课程ID获取完整的课程目录结构，包括章节、小节、实验等
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

from src.config import config
from src.logger import logger


@dataclass
class LabItem:
    """实验/练习项"""
    id: int
    name: str
    type: str  # video, doc, lab, course_challenge 等
    description: str = ""
    duration: str = ""
    

@dataclass
class Section:
    """小节"""
    id: int
    name: str
    items: List[LabItem] = field(default_factory=list)
    

@dataclass
class Chapter:
    """章节"""
    id: int
    name: str
    sections: List[Section] = field(default_factory=list)


@dataclass
class CourseCatalog:
    """课程目录"""
    course_id: str
    course_name: str
    chapters: List[Chapter] = field(default_factory=list)
    fetch_time: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    def get_all_items(self) -> List[dict]:
        """获取所有实验项（扁平化）"""
        items = []
        for ch in self.chapters:
            for sec in ch.sections:
                for lab in sec.items:
                    items.append({
                        "chapter_id": ch.id,
                        "chapter_name": ch.name,
                        "section_id": sec.id,
                        "section_name": sec.name,
                        "item_id": lab.id,
                        "item_name": lab.name,
                        "item_type": lab.type,
                    })
        return items


class CourseCatalogFetcher:
    """课程目录获取器"""
    
    # 缓存目录
    CACHE_DIR: Path = config.PROJECT_ROOT / "data" / "catalogs"
    
    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def fetch_by_id(self, course_id: str, use_cache: bool = True) -> Optional[CourseCatalog]:
        """
        根据课程ID获取完整目录
        
        Args:
            course_id: 课程ID
            use_cache: 是否使用缓存
            
        Returns:
            CourseCatalog 对象，失败返回 None
        """
        # 尝试从缓存读取
        if use_cache:
            cached = self._load_cache(course_id)
            if cached:
                logger.info(f"使用缓存的课程目录：{cached.course_name}")
                return cached
        
        logger.info(f"正在获取课程 {course_id} 的目录...")
        
        # 1. 获取课程基本信息
        course_info = self._fetch_course_info(course_id)
        if not course_info:
            logger.error(f"无法获取课程 {course_id} 的信息")
            return None
        
        # 2. 获取课程结构（章节、小节、实验）
        stages = self._fetch_course_stages(course_id)
        if not stages:
            logger.error(f"无法获取课程 {course_id} 的结构")
            return None
        
        # 3. 解析为目录结构
        catalog = self._parse_to_catalog(course_id, course_info, stages)
        
        # 4. 保存缓存
        self._save_cache(catalog)
        
        logger.info(f"课程目录获取成功：{catalog.course_name}，共 {len(catalog.chapters)} 章")
        return catalog
    
    def _fetch_course_info(self, course_id: str) -> Optional[dict]:
        """获取课程基本信息"""
        try:
            url = f"https://www.lanqiao.cn/api/v2/courses/{course_id}/"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data
        except Exception as e:
            logger.warning(f"获取课程信息失败：{e}")
            return None
    
    def _fetch_course_stages(self, course_id: str) -> Optional[list]:
        """获取课程结构（stages），支持分页"""
        all_results = []
        page = 1
        page_size = 500
        
        try:
            while True:
                url = f"https://www.lanqiao.cn/api/v2/courses/{course_id}/labs/?page_size={page_size}&page={page}"
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    # API 可能返回 {"results": [...]} 或直接 [...]
                    if isinstance(data, list):
                        results = data
                    else:
                        results = data.get("results", data.get("data", []))
                    
                    if not results:
                        break
                    
                    all_results.extend(results)
                    
                    # 如果返回数量少于 page_size，说明已是最后一页
                    if len(results) < page_size:
                        break
                    
                    page += 1
            
            return all_results if all_results else None
        except Exception as e:
            logger.warning(f"获取课程结构失败：{e}")
            # 如果已获取部分数据，仍返回
            return all_results if all_results else None
    
    def _parse_to_catalog(self, course_id: str, course_info: dict, stages: list) -> CourseCatalog:
        """将API返回解析为目录结构"""
        course_name = course_info.get("name", f"课程{course_id}")
        
        catalog = CourseCatalog(
            course_id=course_id,
            course_name=course_name,
            fetch_time=datetime.now().isoformat()
        )
        
        chapter_order = 0
        for stage in stages:
            # 跳过默认阶段
            if stage.get("is_default"):
                continue
            
            chapter_order += 1
            chapter = Chapter(
                id=stage.get("id", chapter_order),
                name=stage.get("name", f"章节{chapter_order}")
            )
            
            section_order = 0
            for sub_stage in stage.get("sub_stages", []):
                if sub_stage.get("is_default"):
                    continue
                
                section_order += 1
                section = Section(
                    id=sub_stage.get("id", section_order),
                    name=sub_stage.get("name", f"小节{section_order}")
                )
                
                for lab in sub_stage.get("labs", []):
                    lab_item = LabItem(
                        id=lab.get("id", 0),
                        name=lab.get("name", ""),
                        type=lab.get("type", "unknown"),
                        description=lab.get("description", ""),
                        duration=lab.get("duration", "")
                    )
                    section.items.append(lab_item)
                
                chapter.sections.append(section)
            
            catalog.chapters.append(chapter)
        
        return catalog
    
    def _load_cache(self, course_id: str) -> Optional[CourseCatalog]:
        """加载缓存"""
        cache_file = self.CACHE_DIR / f"{course_id}.json"
        if not cache_file.exists():
            return None
        
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            
            catalog = CourseCatalog(
                course_id=data["course_id"],
                course_name=data["course_name"],
                fetch_time=data.get("fetch_time", "")
            )
            
            for ch_data in data.get("chapters", []):
                chapter = Chapter(
                    id=ch_data["id"],
                    name=ch_data["name"]
                )
                for sec_data in ch_data.get("sections", []):
                    section = Section(
                        id=sec_data["id"],
                        name=sec_data["name"]
                    )
                    for lab_data in sec_data.get("items", []):
                        lab = LabItem(
                            id=lab_data["id"],
                            name=lab_data["name"],
                            type=lab_data.get("type", "unknown"),
                            description=lab_data.get("description", ""),
                            duration=lab_data.get("duration", "")
                        )
                        section.items.append(lab)
                    chapter.sections.append(section)
                catalog.chapters.append(chapter)
            
            return catalog
        except Exception as e:
            logger.warning(f"加载缓存失败：{e}")
            return None
    
    def _save_cache(self, catalog: CourseCatalog):
        """保存缓存"""
        cache_file = self.CACHE_DIR / f"{catalog.course_id}.json"
        try:
            cache_file.write_text(
                json.dumps(catalog.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.debug(f"课程目录已缓存：{cache_file}")
        except Exception as e:
            logger.warning(f"保存缓存失败：{e}")
    
    def clear_cache(self, course_id: str = None):
        """清除缓存"""
        if course_id:
            cache_file = self.CACHE_DIR / f"{course_id}.json"
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"已清除课程 {course_id} 的缓存")
        else:
            for f in self.CACHE_DIR.glob("*.json"):
                f.unlink()
            logger.info("已清除所有课程目录缓存")


# 全局实例
catalog_fetcher = CourseCatalogFetcher()
