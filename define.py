"""
课程数据结构定义
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Option:
    """选择题选项"""
    option_id: str
    text: str
    is_correct: bool


@dataclass
class Exercise:
    """练习题"""
    exercise_id: str
    question: str
    score: int
    type: str  # 单选、多选、判断、填空等
    answer: Optional[str] = None  # 简答题：参考答案
    options: List[Option] = field(default_factory=list)


@dataclass
class LeadingQuestion:
    """引导性问题"""
    question_id: str
    question: str


@dataclass
class Section:
    """小节"""
    section_id: str
    title: str
    order: int
    estimated_time: int  # 预计学习时间（分钟）
    video_url: str
    leading_questions: List[LeadingQuestion] = field(default_factory=list)
    exercises: List[Exercise] = field(default_factory=list)


@dataclass
class Chapter:
    """章"""
    chapter_id: str
    title: str
    order: int
    sections: List[Section] = field(default_factory=list)


@dataclass
class Course:
    """课程"""
    course_id: str
    title: str
    description: str
    icon_url: Optional[str] = ""
    chapters: List[Chapter] = field(default_factory=list)


def create_empty_course(title: str, description: str = "") -> dict:
    """
    创建一个空的课程结构（用于初始化工作区）
    
    Args:
        title: 课程标题（通常使用工作区名称）
        description: 课程描述
    
    Returns:
        课程结构的字典表示
    """
    import uuid
    
    course = {
        # 与课程库/导入约定一致：标准 UUID 字符串（含连字符），不用 .hex
        "course_id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "ai_persona": {
            "persona_id": str(uuid.uuid4()),
            "name": title,
            "prompt": "",
            "is_default_template": True
        },
        "category": "职业技能",
        "icon_url": "",
        "chapters": []
    }
    
    return course


# 示例课程结构（完整示例）
EXAMPLE_COURSE = {
    "course_id": "uuidv4",
    "title": "计算机原理通识",
    "description": "计算机原理通识课程，适合初学者学习",
    "category": "职业技能",
    "icon_url": "",
    "chapters": [
        {
            "chapter_id": "uuidv4",
            "title": "计算机组成硬件",
            "order": 0,
            "sections": [
                {
                    "section_id": "uuidv4",
                    "title": "家用计算机硬件组成",
                    "order": 0,
                    "estimated_time": 0,
                    "video_url": "",
                    "leading_questions": [
                        {
                            "question_id": "uuidv4",
                            "question": "家用计算机硬件组成有哪些？"
                        }
                    ],
                    "exercises": [
                        {
                            "exercise_id": "uuidv4",
                            "question": "以下哪个硬件是专门负责图形显示的？",
                            "score": 5,
                            "type": "单选",
                            "options": [
                                {
                                    "option_id": "uuidv4",
                                    "text": "显卡",
                                    "is_correct": True
                                },
                                {
                                    "option_id": "uuidv4",
                                    "text": "主板",
                                    "is_correct": False
                                },
                                {
                                    "option_id": "uuidv4",
                                    "text": "内存",
                                    "is_correct": False
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}

