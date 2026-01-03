"""
工作区管理 API 测试示例
演示如何创建和删除真实的文件夹
"""

import requests
import time

base_url = "http://localhost:5000"

def test_workspace_operations():
    print("=" * 60)
    print("工作区管理测试（包含真实文件夹操作）")
    print("=" * 60)
    
    # 1. 创建工作区（会创建真实文件夹）
    print("\n1️⃣  创建工作区 '测试项目A'...")
    response = requests.post(
        f"{base_url}/api/workspace",
        json={
            "name": "测试项目A",
            "path": "workspace/test_project_a"
        }
    )
    result = response.json()
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {result}")
    if result.get('success'):
        print(f"   ✅ 文件夹已创建: {result['workspace']['path']}")
        print(f"   ✅ 完整路径: {result.get('full_path')}")
    
    time.sleep(0.5)
    
    # 2. 创建第二个工作区
    print("\n2️⃣  创建工作区 '测试项目B'...")
    response = requests.post(
        f"{base_url}/api/workspace",
        json={
            "name": "测试项目B",
            "path": "workspace/test_project_b"
        }
    )
    result = response.json()
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {result}")
    if result.get('success'):
        print(f"   ✅ 文件夹已创建: {result['workspace']['path']}")
    
    time.sleep(0.5)
    
    # 3. 尝试创建重名工作区（应该失败）
    print("\n3️⃣  尝试创建重名工作区（应该失败）...")
    response = requests.post(
        f"{base_url}/api/workspace",
        json={
            "name": "测试项目A",
            "path": "workspace/test_project_a_duplicate"
        }
    )
    result = response.json()
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {result}")
    if not result.get('success'):
        print(f"   ✅ 正确拒绝: {result['error']}")
    
    time.sleep(0.5)
    
    # 4. 获取所有工作区
    print("\n4️⃣  获取所有工作区列表...")
    response = requests.get(f"{base_url}/api/workspace")
    result = response.json()
    print(f"   状态码: {response.status_code}")
    if result.get('success'):
        workspaces = result['workspaces']
        print(f"   ✅ 共有 {len(workspaces)} 个工作区:")
        for ws in workspaces:
            print(f"      - {ws['name']} -> {ws['path']}")
    
    time.sleep(0.5)
    
    # 5. 删除工作区（会删除真实文件夹）
    print("\n5️⃣  删除工作区 '测试项目A'（会删除文件夹）...")
    response = requests.delete(f"{base_url}/api/workspace/测试项目A")
    result = response.json()
    print(f"   状态码: {response.status_code}")
    print(f"   响应: {result}")
    if result.get('success'):
        print(f"   ✅ {result['message']}")
        print(f"   ✅ 已删除路径: {result.get('deleted_path')}")
    
    time.sleep(0.5)
    
    # 6. 验证删除
    print("\n6️⃣  验证删除后的列表...")
    response = requests.get(f"{base_url}/api/workspace")
    result = response.json()
    if result.get('success'):
        workspaces = result['workspaces']
        print(f"   ✅ 剩余 {len(workspaces)} 个工作区:")
        for ws in workspaces:
            print(f"      - {ws['name']} -> {ws['path']}")
    
    # 7. 清理：删除所有测试工作区
    print("\n7️⃣  清理所有测试工作区...")
    response = requests.delete(f"{base_url}/api/workspace/测试项目B")
    result = response.json()
    if result.get('success'):
        print(f"   ✅ {result['message']}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_workspace_operations()
    except requests.exceptions.ConnectionError:
        print("❌ 错误: 无法连接到服务器")
        print("请确保服务器正在运行: python app.py")
    except Exception as e:
        print(f"❌ 错误: {e}")

