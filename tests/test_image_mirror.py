from src.image_mirror import extract_urls


def test_extract_urls_single():
    assert extract_urls("https://a.com/1.jpg") == ["https://a.com/1.jpg"]


def test_extract_urls_multiple_separated():
    text = "https://a.com/1.jpg, https://b.com/2.png;https://c.com/x"
    assert extract_urls(text) == [
        "https://a.com/1.jpg",
        "https://b.com/2.png",
        "https://c.com/x",
    ]


def test_extract_urls_dedupes():
    assert extract_urls("https://a.com/x https://a.com/x") == ["https://a.com/x"]


def test_extract_urls_no_http_returns_empty():
    assert extract_urls("/local/path/img.jpg") == []
    assert extract_urls("") == []
