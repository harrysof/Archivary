from archivary.core.credentials import CredentialStore
from archivary.core.jobs import JobQueue
from archivary.core.settings import SettingsStore
from archivary.services.ia_service import IAService
from archivary.ui.context import AppContext
from archivary.ui.main_window import TAB_ORDER, MainWindow


def test_main_window_builds_all_tabs(qapp, tmp_path):
    context = AppContext(
        CredentialStore(profiles_file=tmp_path / "profiles.json"),
        SettingsStore(tmp_path / "settings.json"),
        IAService(),
        JobQueue(),
    )
    window = MainWindow(context)
    assert window.stack.count() == len(TAB_ORDER)
    expected = {key for key, _label, _factory in TAB_ORDER}
    assert set(window._tabs) == expected


def test_navigation_helpers_do_not_crash(qapp, tmp_path):
    context = AppContext(
        CredentialStore(profiles_file=tmp_path / "profiles.json"),
        SettingsStore(tmp_path / "settings.json"),
        IAService(),
        JobQueue(),
    )
    window = MainWindow(context)
    window.open_download("some_id")
    assert window.stack.currentWidget() is window._tabs["download"]
    assert window._tabs["download"].identifier_edit.text() == "some_id"
    window.switch_to("metadata")
    assert window.stack.currentWidget() is window._tabs["metadata"]
    window.switch_to("list")
    assert window.stack.currentWidget() is window._tabs["list"]
