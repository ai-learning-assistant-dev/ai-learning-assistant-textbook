import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from insert_db import Course, Chapter, Section, Exercise, ExerciseOption, LeadingQuestion, Base


def export_course_to_json(course_id, output_dir='subtitles', db_url=None):
    """
    从PostgreSQL数据库导出课程数据到JSON文件
    
    参数:
        course_id: 课程ID（UUID字符串）
        output_dir: 输出目录，默认为 'subtitles'
        db_url: 数据库连接URL，格式: postgresql://username:password@host:port/database
    """
    # 创建数据库引擎和会话
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 查询课程
        course = session.query(Course).filter_by(course_id=course_id).first()
        
        if not course:
            print(f"错误: 未找到ID为 {course_id} 的课程")
            return False
        
        print(f"正在导出课程: {course.name}")
        
        # 构建课程数据字典
        course_data = {
            'id': str(course.course_id),
            'title': course.name,
            'description': course.description or '',
            'icon_url': course.icon_url or '',
            'chapters': []
        }
        
        # 添加 default_ai_persona_id（如果存在）
        if course.default_ai_persona_id:
            course_data['default_ai_persona_id'] = str(course.default_ai_persona_id)
        
        # 处理章节（按顺序排序）
        sorted_chapters = sorted(course.chapters, key=lambda x: x.chapter_order)
        for chapter in sorted_chapters:
            chapter_data = {
                'id': str(chapter.chapter_id).replace('-', ''),  # 移除横线
                'title': chapter.title,
                'order': chapter.chapter_order,
                'sections': []
            }
            
            # 处理小节（按顺序排序）
            sorted_sections = sorted(chapter.sections, key=lambda x: x.section_order)
            for section in sorted_sections:
                section_data = {
                    'id': str(section.section_id).replace('-', ''),  # 移除横线
                    'title': section.title,
                    'order': section.section_order,
                    'video_url': section.video_url or '',
                    'estimated_time': section.estimated_time or 0,
                    'srt_path': section.srt_path or '',
                    'knowledge_content': section.knowledge_content or '',
                    'knowledge_points': section.knowledge_points or {},
                    'video_subtitles': section.video_subtitles or [],
                    'exercises': [],
                    'leading_questions': []
                }
                
                # 处理练习题
                for exercise in section.exercises:
                    # 转换题目类型
                    type_map = {
                        '0': '单选',
                        '1': '多选',
                        '2': '简答'
                    }
                    exercise_type = type_map.get(exercise.type_status, '单选')
                    
                    exercise_data = {
                        'id': str(exercise.exercise_id).replace('-', ''),  # 移除横线
                        'question': exercise.question,
                        'type': exercise_type,
                        'score': exercise.score,
                        'options': []
                    }
                    
                    # 添加答案（如果存在）
                    if exercise.answer:
                        exercise_data['answer'] = exercise.answer
                    
                    # 添加图片（如果存在）
                    if exercise.image:
                        exercise_data['image'] = exercise.image
                    
                    # 处理选项
                    for option in exercise.options:
                        option_data = {
                            'id': str(option.option_id).replace('-', ''),  # 移除横线
                            'text': option.option_text,
                            'is_correct': option.is_correct
                        }
                        
                        # 添加图片（如果存在）
                        if option.image:
                            option_data['image'] = option.image
                        
                        exercise_data['options'].append(option_data)
                    
                    section_data['exercises'].append(exercise_data)
                
                # 处理引导问题
                for question in section.leading_questions:
                    question_data = {
                        'id': str(question.question_id).replace('-', ''),  # 移除横线
                        'question': question.question
                    }
                    section_data['leading_questions'].append(question_data)
                
                chapter_data['sections'].append(section_data)
            
            course_data['chapters'].append(chapter_data)
        
        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 在输出目录下创建课程目录
        course_dir = os.path.join(output_dir, course.name)
        if not os.path.exists(course_dir):
            os.makedirs(course_dir)
        
        # 写入JSON文件
        output_file = os.path.join(course_dir, 'course.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(course_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n成功导出课程到: {output_file}")
        print(f"- 章节数: {len(course_data['chapters'])}")
        for chapter in course_data['chapters']:
            print(f"  - {chapter['title']}: {len(chapter['sections'])} 个小节")
        
        return True
        
    except Exception as e:
        print(f"导出失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def list_all_courses(db_url):
    """
    列出数据库中所有的课程
    
    参数:
        db_url: 数据库连接URL
    """
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        courses = session.query(Course).all()
        
        if not courses:
            print("数据库中没有课程")
            return []
        
        print("\n数据库中的所有课程:")
        print("-" * 80)
        for i, course in enumerate(courses, 1):
            chapter_count = len(course.chapters)
            section_count = sum(len(chapter.sections) for chapter in course.chapters)
            print(f"{i}. [{course.course_id}]")
            print(f"   名称: {course.name}")
            print(f"   描述: {course.description or '无'}")
            print(f"   章节: {chapter_count} 个")
            print(f"   小节: {section_count} 个")
            print()
        
        return courses
        
    except Exception as e:
        print(f"查询失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
        
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
    
    # 导出配置
    OUTPUT_DIR = 'subtitles'     # 输出目录
    # COURSE_ID = '9c8a1c17-61a4-4081-939a-3a8687278bc8'  # 要导出的课程ID（可选）
    # ==================================================
    
    # 构建数据库连接URL
    DB_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    
    print("=" * 80)
    print("课程导出工具")
    print("=" * 80)
    
    # 先列出所有课程
    courses = list_all_courses(DB_URL)
    
    if not courses:
        print("\n没有可导出的课程")
        exit(1)
    
    # 让用户选择要导出的课程
    print("-" * 80)
    choice = input("\n请输入要导出的课程编号（或输入课程ID，输入 'all' 导出所有课程）: ").strip()
    
    if choice.lower() == 'all':
        # 导出所有课程
        print("\n开始导出所有课程...")
        success_count = 0
        for course in courses:
            print(f"\n正在导出: {course.name}")
            if export_course_to_json(str(course.course_id), OUTPUT_DIR, DB_URL):
                success_count += 1
        print(f"\n完成！成功导出 {success_count}/{len(courses)} 个课程")
    else:
        # 导出单个课程
        try:
            # 尝试作为编号解析
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(courses):
                    course_id = str(courses[index].course_id)
                else:
                    print("错误: 无效的课程编号")
                    exit(1)
            else:
                # 作为课程ID使用
                course_id = choice
            
            # 可选：自定义输出目录
            custom_dir = input(f"请输入输出目录（直接回车使用默认目录 '{OUTPUT_DIR}'）: ").strip()
            if custom_dir:
                OUTPUT_DIR = custom_dir
            
            print(f"\n开始导出课程...")
            print(f"课程ID: {course_id}")
            print(f"输出目录: {OUTPUT_DIR}\n")
            
            success = export_course_to_json(course_id, OUTPUT_DIR, DB_URL)
            
            if success:
                print("\n✓ 导出完成！")
            else:
                print("\n✗ 导出失败，请检查错误信息")
                
        except ValueError:
            print("错误: 无效的输入")
            exit(1)

