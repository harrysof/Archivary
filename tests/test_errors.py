from requests.exceptions import HTTPError

from archivary.core.errors import describe_exception


def test_collection_access_denied_is_explained():
    exc = HTTPError(
        " error uploading file to item, Access Denied - You lack sufficient "
        "privileges to write to those collections"
    )
    friendly = describe_exception(exc)
    assert friendly.title == "Cannot write to that collection"
    assert any("Collection" in hint for hint in friendly.hints)


def test_item_already_exists_is_explained():
    friendly = describe_exception(HTTPError("item already exists"))
    assert friendly.title == "Item already exists"


def test_generic_http_error_still_falls_back():
    friendly = describe_exception(HTTPError("weird failure"))
    assert friendly.title == "Request failed"
