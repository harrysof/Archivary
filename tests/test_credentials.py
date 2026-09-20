import pytest

from archivary.core import credentials
from archivary.core.credentials import CredentialStore, EncryptedFileSecretStore, Profile


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(credentials, "KEYRING_IMPORTED", False)
    monkeypatch.setattr(credentials, "CRYPTO_AVAILABLE", False)
    credential_store = CredentialStore(profiles_file=tmp_path / "profiles.json")
    credential_store._fallback = EncryptedFileSecretStore(tmp_path / "secrets.enc")
    return credential_store


def test_save_and_load_profile(store):
    store.save_profile(
        Profile(
            name="main",
            access_key="ACCESS",
            secret_key="SECRET",
            email="me@example.com",
            screenname="tester",
        )
    )
    loaded = store.get_profile("main")
    assert loaded is not None
    assert loaded.access_key == "ACCESS"
    assert loaded.secret_key == "SECRET"
    assert loaded.screenname == "tester"
    assert store.active_name == "main"


def test_active_profile_switching(store):
    store.save_profile(Profile(name="a", access_key="1", secret_key="1"))
    store.save_profile(Profile(name="b", access_key="2", secret_key="2"))
    store.set_active("b")
    assert store.active_profile().access_key == "2"


def test_delete_profile_clears_secret(store):
    store.save_profile(Profile(name="a", access_key="1", secret_key="1"))
    store.delete_profile("a")
    assert store.get_profile("a") is None
    assert store.active_name == ""


def test_profile_public_dict_hides_secrets(store):
    profile = Profile(name="a", access_key="1", secret_key="2")
    public = profile.public_dict()
    assert "access_key" not in public
    assert "secret_key" not in public
    assert public["name"] == "a"
