"""测试 settings 模块中动态 provider 名称获取函数

验证 get_supported_temp_mail_provider_names()、is_supported_temp_mail_provider_name()
和 validate_temp_mail_provider_name() 三个函数在注册表不同状态下的行为。

测试通过直接操作 outlook_web.temp_mail_registry._REGISTRY 注入/清理测试数据，
每个测试前后确保注册表状态干净。
"""
from __future__ import annotations

import pytest


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture()
def clean_registry():
    """每个测试前后保存/恢复 _REGISTRY 快照，确保测试隔离。"""
    from outlook_web.temp_mail_registry import _REGISTRY

    snapshot = dict(_REGISTRY)
    _REGISTRY.clear()
    yield _REGISTRY
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


@pytest.fixture()
def registry_with_builtin(clean_registry):
    """预填充内置 provider 的注册表。"""
    clean_registry["cloudflare_temp_mail"] = type("CF", (), {})
    clean_registry["custom_domain_temp_mail"] = type("Custom", (), {})
    return clean_registry


# ── 1. get_supported_temp_mail_provider_names ─────────────


class TestGetSupportedTempMailProviderNames:
    """测试动态获取已注册 provider 名称集合。"""

    def test_returns_empty_set_when_registry_is_empty(self, clean_registry):
        """注册表为空时，函数应返回空集合。"""
        from outlook_web.repositories.settings import get_supported_temp_mail_provider_names

        result = get_supported_temp_mail_provider_names()
        assert result == set()

    def test_returns_builtin_provider_names(self, registry_with_builtin):
        """注册表中有内置 provider 时，函数应返回正确的名称集合。"""
        from outlook_web.repositories.settings import get_supported_temp_mail_provider_names

        result = get_supported_temp_mail_provider_names()
        assert result == {"cloudflare_temp_mail", "custom_domain_temp_mail"}

    def test_includes_dynamically_added_plugin_provider(self, registry_with_builtin):
        """动态添加插件 provider 后，函数应包含新增名称。"""
        from outlook_web.repositories.settings import get_supported_temp_mail_provider_names

        registry_with_builtin["my_plugin_provider"] = type("Plugin", (), {})

        result = get_supported_temp_mail_provider_names()
        assert "my_plugin_provider" in result
        assert "cloudflare_temp_mail" in result

    def test_returns_copy_not_reference(self, registry_with_builtin):
        """返回值应为注册表键的副本，修改返回值不影响注册表。"""
        from outlook_web.repositories.settings import get_supported_temp_mail_provider_names

        result = get_supported_temp_mail_provider_names()
        result.add("fake_provider")
        assert "fake_provider" not in registry_with_builtin

    def test_reflects_registry_removal(self, registry_with_builtin):
        """从注册表中移除 provider 后，函数不再包含该名称。"""
        from outlook_web.repositories.settings import get_supported_temp_mail_provider_names

        del registry_with_builtin["cloudflare_temp_mail"]

        result = get_supported_temp_mail_provider_names()
        assert "cloudflare_temp_mail" not in result
        assert "custom_domain_temp_mail" in result


# ── 2. is_supported_temp_mail_provider_name ───────────────


class TestIsSupportedTempMailProviderName:
    """测试判断 provider 名称是否已注册。"""

    def test_returns_true_for_registered_name(self, registry_with_builtin):
        """已注册名称应返回 True。"""
        from outlook_web.repositories.settings import is_supported_temp_mail_provider_name

        assert is_supported_temp_mail_provider_name("cloudflare_temp_mail") is True
        assert is_supported_temp_mail_provider_name("custom_domain_temp_mail") is True

    def test_returns_false_for_unregistered_name(self, registry_with_builtin):
        """未注册名称应返回 False。"""
        from outlook_web.repositories.settings import is_supported_temp_mail_provider_name

        assert is_supported_temp_mail_provider_name("nonexistent_provider") is False

    def test_returns_false_when_registry_is_empty(self, clean_registry):
        """注册表为空时，任何名称都应返回 False。"""
        from outlook_web.repositories.settings import is_supported_temp_mail_provider_name

        assert is_supported_temp_mail_provider_name("any_provider") is False

    def test_returns_true_for_newly_added_plugin(self, registry_with_builtin):
        """动态添加插件 provider 后，is_supported 应识别新名称。"""
        from outlook_web.repositories.settings import is_supported_temp_mail_provider_name

        registry_with_builtin["new_plugin"] = type("New", (), {})

        assert is_supported_temp_mail_provider_name("new_plugin") is True

    def test_returns_false_after_provider_removed(self, registry_with_builtin):
        """provider 被移除后，is_supported 应返回 False。"""
        from outlook_web.repositories.settings import is_supported_temp_mail_provider_name

        del registry_with_builtin["cloudflare_temp_mail"]

        assert is_supported_temp_mail_provider_name("cloudflare_temp_mail") is False

    def test_none_input_returns_false_in_empty_registry(self, clean_registry):
        """None 输入在空注册表时应返回 False。"""
        from outlook_web.repositories.settings import is_supported_temp_mail_provider_name

        assert is_supported_temp_mail_provider_name(None) is False


# ── 3. validate_temp_mail_provider_name ───────────────────


class TestValidateTempMailProviderName:
    """测试验证并归一化 provider 名称。"""

    def test_returns_name_for_valid_provider(self, registry_with_builtin):
        """有效名称应原样返回该名称。"""
        from outlook_web.repositories.settings import validate_temp_mail_provider_name

        assert validate_temp_mail_provider_name("cloudflare_temp_mail") == "cloudflare_temp_mail"

    def test_raises_value_error_for_invalid_provider(self, registry_with_builtin):
        """无效名称应抛出 ValueError。"""
        from outlook_web.repositories.settings import validate_temp_mail_provider_name

        with pytest.raises(ValueError, match="临时邮箱 Provider 配置无效"):
            validate_temp_mail_provider_name("nonexistent_provider")

    def test_raises_value_error_when_registry_is_empty(self, clean_registry):
        """注册表为空时，任何名称都应抛出 ValueError。"""
        from outlook_web.repositories.settings import validate_temp_mail_provider_name

        with pytest.raises(ValueError, match="临时邮箱 Provider 配置无效"):
            validate_temp_mail_provider_name("any_provider")

    def test_validates_newly_added_plugin(self, registry_with_builtin):
        """动态添加的插件 provider 应通过验证。"""
        from outlook_web.repositories.settings import validate_temp_mail_provider_name

        registry_with_builtin["plugin_provider"] = type("Plugin", (), {})

        assert validate_temp_mail_provider_name("plugin_provider") == "plugin_provider"

    def test_raises_after_provider_removed(self, registry_with_builtin):
        """provider 被移除后，验证应抛出 ValueError。"""
        from outlook_web.repositories.settings import validate_temp_mail_provider_name

        del registry_with_builtin["cloudflare_temp_mail"]

        with pytest.raises(ValueError, match="临时邮箱 Provider 配置无效"):
            validate_temp_mail_provider_name("cloudflare_temp_mail")
