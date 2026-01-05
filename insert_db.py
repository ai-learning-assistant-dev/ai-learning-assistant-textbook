import json
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Text, UUID, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from uuid import uuid4
import uuid

Base = declarative_base()


# 定义数据库模型
class Course(Base):
    __tablename__ = 'courses'
    
    course_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    icon_url = Column(Text, nullable=False, default='')
    description = Column(Text)
    default_ai_persona_id = Column(UUID(as_uuid=True))
    
    chapters = relationship('Chapter', back_populates='course', cascade='all, delete-orphan')


class Chapter(Base):
    __tablename__ = 'chapters'
    
    chapter_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey('courses.course_id'), nullable=False)
    title = Column(String(255), nullable=False)
    chapter_order = Column(Integer, nullable=False)
    
    course = relationship('Course', back_populates='chapters')
    sections = relationship('Section', back_populates='chapter', cascade='all, delete-orphan')


class Section(Base):
    __tablename__ = 'sections'
    
    section_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(255), nullable=False)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey('chapters.chapter_id'), nullable=False)
    video_url = Column(Text)
    knowledge_points = Column(JSON)
    video_subtitles = Column(JSON)
    srt_path = Column(String(512))
    knowledge_content = Column(JSON)
    estimated_time = Column(Integer)
    section_order = Column(Integer, nullable=False)
    
    chapter = relationship('Chapter', back_populates='sections')
    exercises = relationship('Exercise', back_populates='section', cascade='all, delete-orphan')
    leading_questions = relationship('LeadingQuestion', back_populates='section', cascade='all, delete-orphan')


class Exercise(Base):
    __tablename__ = 'exercises'
    
    exercise_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    section_id = Column(UUID(as_uuid=True), ForeignKey('sections.section_id'))
    question = Column(Text, nullable=False)
    type_status = Column(String(50), nullable=False)
    score = Column(Integer, nullable=False, default=1)
    answer = Column(Text)
    image = Column(Text)
    
    section = relationship('Section', back_populates='exercises')
    options = relationship('ExerciseOption', back_populates='exercise', cascade='all, delete-orphan')


class ExerciseOption(Base):
    __tablename__ = 'exercise_options'
    
    option_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    exercise_id = Column(UUID(as_uuid=True), ForeignKey('exercises.exercise_id'), nullable=False)
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    image = Column(Text)
    
    exercise = relationship('Exercise', back_populates='options')


class LeadingQuestion(Base):
    __tablename__ = 'leading_question'
    
    question_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    section_id = Column(UUID(as_uuid=True), ForeignKey('sections.section_id'), nullable=False)
    question = Column(Text, nullable=False)
    
    section = relationship('Section', back_populates='leading_questions')


def import_course_from_json(json_file_path, db_url):
    """
    从JSON文件导入课程数据到PostgreSQL数据库
    
    参数:
        json_file_path: JSON文件路径
        db_url: 数据库连接URL，格式: postgresql://username:password@host:port/database
    """
    # 创建数据库引擎和会话
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 创建课程对象
        course = Course(
            course_id=uuid.UUID(data['id']),
            name=data['title'],
            icon_url='',  # JSON中没有此字段，使用默认值
            description=data.get('description', '')
        )
        
        # 处理章节
        for chapter_data in data['chapters']:
            chapter = Chapter(
                chapter_id=uuid.UUID(chapter_data['id']),
                title=chapter_data['title'],
                chapter_order=chapter_data['order']
            )
            
            # 处理小节
            for section_data in chapter_data['sections']:
                section = Section(
                    section_id=uuid.UUID(section_data['id']),
                    title=section_data['title'],
                    video_url=section_data.get('video_url'),
                    estimated_time=section_data.get('estimated_time'),
                    section_order=section_data['order']
                )
                
                # 处理练习题
                for exercise_data in section_data.get('exercises', []):
                    exercise = Exercise(
                        exercise_id=uuid.UUID(exercise_data['id']),
                        question=exercise_data['question'],
                        type_status=exercise_data['type'],
                        score=exercise_data.get('score', 1)
                    )
                    
                    # 处理选项
                    for option_data in exercise_data.get('options', []):
                        option = ExerciseOption(
                            option_id=uuid.UUID(option_data['id']),
                            option_text=option_data['text'],
                            is_correct=option_data['is_correct']
                        )
                        exercise.options.append(option)
                    
                    section.exercises.append(exercise)
                
                # 处理引导问题
                for question_data in section_data.get('leading_questions', []):
                    leading_question = LeadingQuestion(
                        question_id=uuid.UUID(question_data['id']),
                        question=question_data['question']
                    )
                    section.leading_questions.append(leading_question)
                
                chapter.sections.append(section)
            
            course.chapters.append(chapter)
        
        # 添加到数据库
        session.add(course)
        session.commit()
        
        print(f"成功导入课程: {course.name}")
        print(f"- 章节数: {len(course.chapters)}")
        for chapter in course.chapters:
            print(f"  - {chapter.title}: {len(chapter.sections)} 个小节")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


if __name__ == '__main__':
    # 配置数据库连接
    # 格式: postgresql://用户名:密码@主机:端口/数据库名
    DB_URL = 'postgresql://postgres:your_password@localhost:5432/your_database'
    
    # JSON文件路径
    JSON_FILE = 'subtitles/计算机网络/course.json'
    
    # 执行导入
    print("开始导入课程数据...")
    success = import_course_from_json(JSON_FILE, DB_URL)
    
    if success:
        print("✓ 导入完成！")
    else:
        print("✗ 导入失败，请检查错误信息")

