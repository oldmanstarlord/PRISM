from backend.app.core.config import Settings


def test_database_url_normalizes_driver_ssl_and_reserved_password_characters() -> None:
    settings = Settings(
        database_url=("postgresql://postgres.project:secret@6969@pooler.supabase.com:5432/postgres")
    )

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert "secret%406969" in settings.database_url
    assert "@pooler.supabase.com:5432" in settings.database_url
    assert "sslmode=require" in settings.database_url


def test_database_url_does_not_double_encode_password() -> None:
    settings = Settings(
        database_url=(
            "postgresql+psycopg://postgres.project:secret%406969@"
            "pooler.supabase.com:5432/postgres?sslmode=require"
        )
    )

    assert "secret%406969" in settings.database_url
    assert "%2540" not in settings.database_url
