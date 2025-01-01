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
            },
            "/vim-tips": {
                "url": "/vim-tips",
                "title": "Vim Tips",
                "description": "Tips for Vim",
                "markdown_path": "_d/vim_tips.md"
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

def test_url_to_markdown_path(mock_response):
    """Test converting URLs to markdown paths"""
    with patch('requests.get', return_value=mock_response):
        reader = BlogReader()
        
        # Test with relative URL
        assert reader.url_to_markdown_path("/test") == "_d/test.md"
        
        # Test with full URL
        assert reader.url_to_markdown_path("https://idvork.in/test") == "_d/test.md"
        
        # Test with non-existent URL
        assert reader.url_to_markdown_path("/nonexistent") is None
        
        # Test with empty URL
        assert reader.url_to_markdown_path("") is None
        
        # Test with vim-tips URL
        assert reader.url_to_markdown_path("/vim-tips") == "_d/vim_tips.md"
        assert reader.url_to_markdown_path("https://idvork.in/vim-tips") == "_d/vim_tips.md"

def test_read_blog_post_full_path(mock_response):
    """Test reading a blog post using a full markdown path"""
    with patch('requests.get', return_value=mock_response):
        content = read_blog_post("_d/vim_tips.md")
        assert content == "# Test Content"
