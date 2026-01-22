#!/usr/bin/env python
"""系统验证脚本。

测试所有核心功能是否正常工作。
"""

import requests
import json
import time
from pathlib import Path

API_BASE = "http://localhost:8000"
TOKEN_FILE = Path(__file__).parent / ".admin_token"


class TestSuite:
    def __init__(self):
        self.token = self.load_token()
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.passed = 0
        self.failed = 0
    
    def load_token(self) -> str:
        """加载 token。"""
        if not TOKEN_FILE.exists():
            raise FileNotFoundError(f"Token file not found: {TOKEN_FILE}")
        return TOKEN_FILE.read_text().strip()
    
    def test(self, name: str, func):
        """执行测试。"""
        print(f"\n{'='*60}")
        print(f"▶️  测试: {name}")
        print(f"{'='*60}")
        
        try:
            func()
            print(f"✅ 通过: {name}")
            self.passed += 1
        except AssertionError as e:
            print(f"❌ 失败: {name}")
            print(f"   原因: {e}")
            self.failed += 1
        except Exception as e:
            print(f"❌ 错误: {name}")
            print(f"   异常: {e}")
            self.failed += 1
    
    def assert_status(self, response, expected: int):
        """断言状态码。"""
        if response.status_code != expected:
            raise AssertionError(
                f"Expected status {expected}, got {response.status_code}\n"
                f"Response: {response.text}"
            )
    
    # ===== 测试用例 =====
    
    def test_auth_me(self):
        """测试获取当前用户信息。"""
        response = requests.get(f"{API_BASE}/auth/me", headers=self.headers)
        self.assert_status(response, 200)
        
        data = response.json()
        assert "user_id" in data
        assert "scopes" in data
        print(f"   用户ID: {data['user_id']}")
    
    def test_create_tool(self):
        """测试创建工具。"""
        tool = {
            "id": "test_echo",
            "name": "测试Echo",
            "description": "测试工具",
            "risk_level": "read",
            "executor": "host",
            "command": ["echo", "Hello from test"],
            "args_schema": {},
            "timeout_sec": 10
        }
        
        response = requests.post(
            f"{API_BASE}/tools",
            headers=self.headers,
            json=tool
        )
        self.assert_status(response, 200)
        print(f"   工具ID: {tool['id']}")
    
    def test_list_tools(self):
        """测试列出工具。"""
        response = requests.get(f"{API_BASE}/tools", headers=self.headers)
        self.assert_status(response, 200)
        
        data = response.json()
        assert "tools" in data
        print(f"   工具数量: {data['count']}")
    
    def test_execute_low_risk_tool(self):
        """测试执行低风险工具（无需审批）。"""
        # 确保工具存在
        self.test_create_tool()
        
        # 执行工具
        response = requests.post(
            f"{API_BASE}/runs",
            headers=self.headers,
            json={
                "tool_id": "test_echo",
                "args": {}
            }
        )
        self.assert_status(response, 200)
        
        data = response.json()
        assert "run_id" in data
        assert data.get("status") in ("queued", "pending_approval")
        print(f"   运行ID: {data['run_id']}")
        print(f"   状态: {data['status']}")
    
    def test_create_high_risk_tool(self):
        """测试创建高风险工具。"""
        tool = {
            "id": "test_high_risk",
            "name": "高风险测试",
            "description": "需要审批的工具",
            "risk_level": "exec_high",
            "executor": "host",
            "command": ["echo", "High risk operation"],
            "args_schema": {},
            "timeout_sec": 10
        }
        
        response = requests.post(
            f"{API_BASE}/tools",
            headers=self.headers,
            json=tool
        )
        self.assert_status(response, 200)
    
    def test_execute_high_risk_tool(self):
        """测试执行高风险工具（需审批）。"""
        # 确保工具存在
        self.test_create_high_risk_tool()
        
        # 执行工具
        response = requests.post(
            f"{API_BASE}/runs",
            headers=self.headers,
            json={
                "tool_id": "test_high_risk",
                "args": {}
            }
        )
        self.assert_status(response, 200)
        
        data = response.json()
        assert data.get("status") == "pending_approval"
        assert "approval_id" in data
        print(f"   运行ID: {data['run_id']}")
        print(f"   审批ID: {data['approval_id']}")
    
    def test_list_approvals(self):
        """测试列出审批请求。"""
        response = requests.get(
            f"{API_BASE}/approvals?status=pending",
            headers=self.headers
        )
        self.assert_status(response, 200)
        
        data = response.json()
        assert "approvals" in data
        print(f"   待审批数量: {data['count']}")
    
    def test_audit_log(self):
        """测试审计日志。"""
        response = requests.get(
            f"{API_BASE}/audit?limit=10",
            headers=self.headers
        )
        self.assert_status(response, 200)
        
        data = response.json()
        assert "events" in data
        print(f"   审计事件数量: {data['count']}")
    
    def test_disable_tool(self):
        """测试禁用工具。"""
        response = requests.post(
            f"{API_BASE}/tools/test_echo/disable",
            headers=self.headers
        )
        self.assert_status(response, 200)
        print(f"   已禁用工具: test_echo")
    
    def test_token_management(self):
        """测试 Token 管理。"""
        # 列出 tokens
        response = requests.get(f"{API_BASE}/auth/tokens", headers=self.headers)
        self.assert_status(response, 200)
        
        data = response.json()
        assert "tokens" in data
        print(f"   Token 数量: {len(data['tokens'])}")
    
    def run_all(self):
        """运行所有测试。"""
        print("""
╔══════════════════════════════════════════════════════════╗
║  Automation Hub - 系统验证                                ║
╚══════════════════════════════════════════════════════════╝
""")
        
        # 认证测试
        self.test("获取当前用户信息", self.test_auth_me)
        self.test("Token 管理", self.test_token_management)
        
        # 工具管理测试
        self.test("创建工具", self.test_create_tool)
        self.test("列出工具", self.test_list_tools)
        self.test("禁用工具", self.test_disable_tool)
        
        # 执行测试
        self.test("执行低风险工具", self.test_execute_low_risk_tool)
        self.test("创建高风险工具", self.test_create_high_risk_tool)
        self.test("执行高风险工具", self.test_execute_high_risk_tool)
        
        # 审批测试
        self.test("列出审批请求", self.test_list_approvals)
        
        # 审计测试
        self.test("查询审计日志", self.test_audit_log)
        
        # 显示结果
        print(f"\n{'='*60}")
        print(f"测试完成")
        print(f"{'='*60}")
        print(f"✅ 通过: {self.passed}")
        print(f"❌ 失败: {self.failed}")
        print(f"{'='*60}")
        
        if self.failed == 0:
            print("\n🎉 所有测试通过！系统运行正常。")
            return 0
        else:
            print(f"\n⚠️  {self.failed} 个测试失败，请检查错误信息。")
            return 1


if __name__ == "__main__":
    import sys
    
    try:
        suite = TestSuite()
        sys.exit(suite.run_all())
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\n请先执行系统初始化：")
        print("1. python quickstart.py")
        print("2. 调用 /auth/bootstrap")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 API 服务")
        print("\n请确保 API 服务正在运行：")
        print("uvicorn api.main:app --reload")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
