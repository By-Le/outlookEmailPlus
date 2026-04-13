from __future__ import annotations

from flask import Blueprint

from outlook_web.controllers import token_tool as token_tool_controller


def create_blueprint() -> Blueprint:
    """创建 token_tool Blueprint"""
    bp = Blueprint("token_tool", __name__)

    bp.add_url_rule(
        "/token-tool",
        view_func=token_tool_controller.render_page,
        methods=["GET"],
    )
    bp.add_url_rule(
        "/api/token-tool/prepare",
        view_func=token_tool_controller.prepare_oauth,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/token-tool/callback",
        view_func=token_tool_controller.handle_callback,
        methods=["GET"],
    )
    bp.add_url_rule(
        "/api/token-tool/exchange",
        view_func=token_tool_controller.exchange_token,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/api/token-tool/save",
        view_func=token_tool_controller.save_to_account,
        methods=["POST"],
    )
    bp.add_url_rule(
        "/api/token-tool/accounts",
        view_func=token_tool_controller.get_account_list,
        methods=["GET"],
    )
    bp.add_url_rule(
        "/api/token-tool/config",
        view_func=token_tool_controller.get_config,
        methods=["GET"],
    )
    bp.add_url_rule(
        "/api/token-tool/config",
        endpoint="save_config",
        view_func=token_tool_controller.save_config,
        methods=["POST"],
    )

    return bp
