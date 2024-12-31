import pytest
from unittest.mock import Mock, patch
import json
from blog_server import BlogReader, read_blog_post, UrlInfo, blog_handler_logic


@pytest.fixture
def mock_requests():
    with patch('blog_server.requests') as mock:
        yield mock

@pytest.fixture
def sample_url_info():
    return {
        "/test-url": {
            "url": "/test-url",
            "title": "Test Title",
            "description": "Test Description",
            "markdown_path": "test.md",
            "redirect_url": ""
        }
    }

@pytest.fixture
def mock_blog_reader(sample_url_info):
    with patch('blog_server.BlogReader') as mock:
        instance = mock.return_value
        instance.get_url_info.return_value = {
            k: UrlInfo(**v) for k, v in sample_url_info.items()
        }
        yield instance

def test_read_blog_post(mock_requests):
    # Arrange
    mock_response = Mock()
    mock_response.text = "# Test Blog Content"
    mock_requests.get.return_value = mock_response
    
    # Act
    result = read_blog_post("test.md")
    
    # Assert
    assert result == "# Test Blog Content"
    mock_requests.get.assert_called_once()

def test_read_blog_post_error(mock_requests):
    # Arrange
    mock_requests.get.side_effect = Exception("Network error")
    
    # Act & Assert
    with pytest.raises(Exception) as exc:
        read_blog_post("test.md")
    assert "Error fetching blog post" in str(exc.value)

def test_blog_reader_get_url_info(mock_requests):
    # Arrange
    mock_response = Mock()
    mock_response.json.return_value = {
        "url_info": {
            "/test": {
                "url": "/test",
                "title": "Test",
                "description": "Test desc",
                "markdown_path": "test.md"
            }
        }
    }
    mock_requests.get.return_value = mock_response
    reader = BlogReader()
    
    # Act
    result = reader.get_url_info()
    
    # Assert
    assert isinstance(result, dict)
    assert isinstance(result["/test"], UrlInfo)
    assert result["/test"].title == "Test"

@pytest.mark.parametrize("action,expected_content", [
    ("random_blog", {"title": "Test Title", "url": "https://idvork.in/test-url"}),
    ("blog_info", {"url": "https://idvork.in/test-url", "title": "Test Title", "description": "Test Description", "markdown_path": "test.md"}),
    ("blog_post_from_path", {"content": "# Test Content", "markdown_path": "test.md"}),
    ("random_blog_url_only", {"title": "Test Title", "url": "https://idvork.in/test-url"})
])
def test_blog_handler_actions(mock_blog_reader, mock_requests, action, expected_content):
    # Arrange
    mock_response = Mock()
    mock_response.text = "# Test Content"
    mock_requests.get.return_value = mock_response
    
    params = {
        "message": {
            "toolCalls": [{
                "id": "test-id",
                "function": {
                    "name": action,
                    "arguments": '{"markdown_path": "test.md"}'
                }
            }]
        }
    }
    headers = {"X-VAPI-Secret": "test-secret"}
    
    # Act
    with patch('blog_server.raise_if_not_authorized'):
        result = blog_handler_logic(params, headers)
    
    # Assert
    assert isinstance(result, dict)
    assert "results" in result
    assert isinstance(result["results"], list)
    assert len(result["results"]) > 0
    result_str = result["results"][0]["result"]
    for key in expected_content:
        assert key in result_str

def test_blog_handler_unknown_action():
    # Arrange
    params = {
        "message": {
            "toolCalls": [{
                "id": "test-id",
                "function": {
                    "name": "unknown_action",
                    "arguments": '{}' 
                }
            }]
        }
    }
    headers = {"X-VAPI-Secret": "test-secret"}
    
    # Act
    with patch('blog_server.raise_if_not_authorized'):
        result = blog_handler_logic(params, headers)
    
    # Assert
    assert "Unknown action" in result["results"][0]["result"]
