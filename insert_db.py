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
    knowledge_content = Column(Text)
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
        
        course_id = uuid.UUID(data['id'])
        
        # 先删除数据库中已存在的该课程及其关联数据
        existing_course = session.query(Course).filter_by(course_id=course_id).first()
        if existing_course:
            print(f"检测到已存在的课程: {existing_course.name}，正在删除旧数据...")
            # 由于设置了级联删除，删除课程会自动删除所有关联的章节、小节、练习题和选项
            session.delete(existing_course)
            session.commit()
            print("旧数据删除完成")
        
        # 创建课程对象
        course = Course(
            course_id=course_id,
            name=data['title'],
            icon_url=data.get('icon_url', ''),
            description=data.get('description', ''),
            default_ai_persona_id=uuid.UUID(data['default_ai_persona_id']) if data.get('default_ai_persona_id') else None
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
                    video_url=section_data.get('video_url', ''),
                    estimated_time=section_data.get('estimated_time', 0),
                    section_order=section_data['order'],
                    knowledge_points=section_data.get('knowledge_points', {}),
                    video_subtitles=section_data.get('video_subtitles', []),
                    knowledge_content=section_data.get('knowledge_content', ''),
                    srt_path=section_data.get('srt_path', '')
                )
                
                # 处理练习题
                for exercise_data in section_data.get('exercises', []):
                    type_status = '0'
                    match exercise_data['type']:
                        case '单选':
                            type_status = '0'
                        case '多选':
                            type_status = '1'
                        case '简答':
                            type_status = '2'
                    exercise = Exercise(
                        exercise_id=uuid.UUID(exercise_data['id']),
                        question=exercise_data['question'],
                        type_status=type_status,
                        score=exercise_data.get('score', 1),
                        answer=exercise_data.get('answer', None),
                        image=exercise_data.get('image', None)
                    )
                    
                    # 处理选项
                    for option_data in exercise_data.get('options', []):
                        option = ExerciseOption(
                            option_id=uuid.UUID(option_data['id']),
                            option_text=option_data['text'],
                            is_correct=option_data['is_correct'],
                            image=option_data.get('image', '')
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
    # ==================== 数据库配置 ====================
    # 请在这里直接修改你的数据库连接信息
    DB_HOST = 'localhost'        # 数据库主机
    DB_PORT = '5432'             # 数据库端口
    DB_NAME = 'ai_learning_assistant'  # 数据库名称
    DB_USER = 'postgres'         # 数据库用户名
    DB_PASSWORD = 'KLNb923u4_odfh89'  # 数据库密码（请修改）
    
    # JSON文件路径
    JSON_FILE = 'subtitles/运动学基础/course.json'
    # ==================================================
    
    # 构建数据库连接URL
    DB_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    # 执行导入
    print("开始导入课程数据...")
    print(f"数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"用户: {DB_USER}")
    print(f"文件: {JSON_FILE}\n")
    
    success = import_course_from_json(JSON_FILE, DB_URL)
    
    if success:
        print("\n✓ 导入完成！")
    else:
        print("\n✗ 导入失败，请检查错误信息")


