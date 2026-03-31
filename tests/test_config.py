class TestConfig:
    def test_default_config(self, tmp_path):
        from dualentry_cli.config import Config

        config = Config(config_dir=tmp_path)
        from dualentry_cli._build_info import DEFAULT_API_URL

        assert config.api_url == DEFAULT_API_URL
        assert config.output == "table"

    def test_load_config_from_file(self, tmp_path):
        from dualentry_cli.config import Config

        config_file = tmp_path / "config.toml"
        config_file.write_text('[default]\napi_url = "https://custom.example.com"\noutput = "json"\n\n[auth]\norganization_id = 123\nuser_email = "test@example.com"\n')
        config = Config(config_dir=tmp_path)
        assert config.api_url == "https://custom.example.com"
        assert config.output == "json"
        assert config.organization_id == 123
        assert config.user_email == "test@example.com"

    def test_save_config(self, tmp_path):
        from dualentry_cli.config import Config

        config = Config(config_dir=tmp_path)
        config.organization_id = 456
        config.user_email = "user@test.com"
        config.save()
        config2 = Config(config_dir=tmp_path)
        assert config2.organization_id == 456
        assert config2.user_email == "user@test.com"
