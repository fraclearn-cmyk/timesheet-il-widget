from app.integrations.http_transport import (
    build_amocrm_async_transport,
    build_amocrm_sync_transport,
)


def test_async_transport_binds_configured_local_address() -> None:
    transport = build_amocrm_async_transport("192.0.2.10")

    assert transport is not None
    assert transport._pool._local_address == "192.0.2.10"


def test_sync_transport_binds_configured_local_address() -> None:
    transport = build_amocrm_sync_transport("192.0.2.11")

    assert transport is not None
    assert transport._pool._local_address == "192.0.2.11"
