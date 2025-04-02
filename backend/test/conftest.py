"""
测试配置文件，包含共享的测试夹具
"""
import pytest
from flask import Flask
from backend.app import app

@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client 