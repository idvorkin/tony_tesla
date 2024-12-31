import os
import pytest
import json
from blog_server import BlogReader, read_blog_post, UrlInfo
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_response():
    """Mock response for requests"""
    mock = MagicMock()
    mock.text = "# Test Content"
    mock.json.return_value = {
        "url_info": {
            "/test": {
                "url": "/test",
                "title": "Test Post",
                "description": "Test Description",
                "markdown_path": "_d/test.md"
            }
        }
    }
    return mock

def test_read_blog_post(mock_response):
    """Test reading a blog post from GitHub"""
    with patch('requests.get', return_value=mock_response):
        content = read_blog_post("_d/test.md")
        assert content == "# Test Content"

def test_blog_reader_get_url_info(mock_response):
    """Test getting URL info from the blog reader"""
    with patch('requests.get', return_value=mock_response):
        reader = BlogReader()
        url_info = reader.get_url_info()
        
        assert isinstance(url_info, dict)
        assert "/test" in url_info
        assert isinstance(url_info["/test"], UrlInfo)
        assert url_info["/test"].url == "/test"
        assert url_info["/test"].title == "Test Post"
        assert url_info["/test"].description == "Test Description"
        assert url_info["/test"].markdown_path == "_d/test.md"

def test_url_info_model():
    """Test UrlInfo model initialization and validation"""
    info = UrlInfo(
        url="/test",
        title="Test Post",
        description="Test Description",
        markdown_path="_d/test.md"
    )
    
    assert info.url == "/test"
    assert info.title == "Test Post"
    assert info.description == "Test Description"
    assert info.markdown_path == "_d/test.md"
    assert info.redirect_url is None  # Optional field

def test_url_info_model_minimal():
    """Test UrlInfo model with minimal required fields"""
    info = UrlInfo(url="/test")
    
    assert info.url == "/test"
    assert info.title == ""  # Default value
    assert info.description == ""  # Default value
    assert info.markdown_path is None  # Optional field
    assert info.redirect_url is None  # Optional field
