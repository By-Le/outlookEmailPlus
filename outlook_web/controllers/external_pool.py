from __future__ import annotations

from typing import Any

from flask import jsonify, request

from outlook_web.repositories import settings as settings_repo
from outlook_web.security.auth import api_key_required
from outlook_web.security.external_api_guard import external_api_guards
from outlook_web.services import external_api as external_api_service
from outlook_web.services.pool import (
    PoolServiceError,
    claim_random,
    complete_claim,
    get_pool_stats,
    release_claim,
)


def _audit(
    endpoint: str, status: str, *, details: dict[str, Any], email_addr: str = ""
) -> None:
    external_api_service.audit_external_api_access(
        action="external_api_access",
        email_addr=email_addr,
        endpoint=endpoint,
        status=status,
        details=details,
    )


def _pool_error_code(error_code: str) -> str:
    return str(error_code or "INTERNAL_ERROR").upper()


def _error_response(endpoint: str, exc: PoolServiceError):
    code = _pool_error_code(exc.error_code)
    _audit(endpoint, "error", details={"code": code})
    return jsonify(external_api_service.fail(code, str(exc))), exc.http_status


def _check_pool_external_enabled(endpoint: str):
    if settings_repo.get_pool_external_enabled():
        return None
    _audit(
        endpoint,
        "error",
        details={"code": "FEATURE_DISABLED", "feature": "external_pool"},
    )
    return (
        jsonify(
            external_api_service.fail(
                "FEATURE_DISABLED",
                "功能 external_pool 当前未启用",
                data={"feature": "external_pool"},
            )
        ),
        403,
    )


@api_key_required
@external_api_guards()
def api_external_pool_claim_random():
    endpoint = "/api/external/pool/claim-random"
    disabled_resp = _check_pool_external_enabled(endpoint)
    if disabled_resp is not None:
        return disabled_resp
    body = request.get_json(silent=True) or {}
    caller_id = body.get("caller_id", "")
    task_id = body.get("task_id", "")
    provider = body.get("provider")

    try:
        account = claim_random(
            caller_id=caller_id,
            task_id=task_id,
            provider=provider,
        )
        data = {
            "account_id": account["id"],
            "email": account["email"],
            "claim_token": account["claim_token"],
            "lease_expires_at": account["lease_expires_at"],
        }
        _audit(
            endpoint,
            "ok",
            details={"provider": provider or "", "account_id": data["account_id"]},
        )
        return jsonify(external_api_service.ok(data))
    except PoolServiceError as exc:
        return _error_response(endpoint, exc)
    except Exception as exc:
        _audit(
            endpoint,
            "error",
            details={"code": "INTERNAL_ERROR", "err": type(exc).__name__},
        )
        return jsonify(external_api_service.fail("INTERNAL_ERROR", "服务内部错误")), 500


@api_key_required
@external_api_guards()
def api_external_pool_claim_release():
    endpoint = "/api/external/pool/claim-release"
    disabled_resp = _check_pool_external_enabled(endpoint)
    if disabled_resp is not None:
        return disabled_resp
    body = request.get_json(silent=True) or {}
    account_id = body.get("account_id")
    claim_token = body.get("claim_token", "")
    caller_id = body.get("caller_id", "")
    task_id = body.get("task_id", "")
    reason = body.get("reason")

    if account_id is None:
        _audit(endpoint, "error", details={"code": "ACCOUNT_ID_MISSING"})
        return jsonify(
            external_api_service.fail("ACCOUNT_ID_MISSING", "account_id 不能为空")
        ), 400
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        _audit(endpoint, "error", details={"code": "ACCOUNT_ID_INVALID"})
        return jsonify(
            external_api_service.fail("ACCOUNT_ID_INVALID", "account_id 必须为整数")
        ), 400

    try:
        release_claim(
            account_id=account_id,
            claim_token=claim_token,
            caller_id=caller_id,
            task_id=task_id,
            reason=reason,
        )
        _audit(endpoint, "ok", details={"account_id": account_id})
        return jsonify(
            external_api_service.ok(
                {"account_id": account_id, "pool_status": "available"}
            )
        )
    except PoolServiceError as exc:
        return _error_response(endpoint, exc)
    except Exception as exc:
        _audit(
            endpoint,
            "error",
            details={"code": "INTERNAL_ERROR", "err": type(exc).__name__},
        )
        return jsonify(external_api_service.fail("INTERNAL_ERROR", "服务内部错误")), 500


@api_key_required
@external_api_guards()
def api_external_pool_claim_complete():
    endpoint = "/api/external/pool/claim-complete"
    disabled_resp = _check_pool_external_enabled(endpoint)
    if disabled_resp is not None:
        return disabled_resp
    body = request.get_json(silent=True) or {}
    account_id = body.get("account_id")
    claim_token = body.get("claim_token", "")
    caller_id = body.get("caller_id", "")
    task_id = body.get("task_id", "")
    result = body.get("result", "")
    detail = body.get("detail")

    if account_id is None:
        _audit(endpoint, "error", details={"code": "ACCOUNT_ID_MISSING"})
        return jsonify(
            external_api_service.fail("ACCOUNT_ID_MISSING", "account_id 不能为空")
        ), 400
    try:
        account_id = int(account_id)
    except (TypeError, ValueError):
        _audit(endpoint, "error", details={"code": "ACCOUNT_ID_INVALID"})
        return jsonify(
            external_api_service.fail("ACCOUNT_ID_INVALID", "account_id 必须为整数")
        ), 400

    try:
        new_status = complete_claim(
            account_id=account_id,
            claim_token=claim_token,
            caller_id=caller_id,
            task_id=task_id,
            result=result,
            detail=detail,
        )
        _audit(
            endpoint,
            "ok",
            details={
                "account_id": account_id,
                "result": result,
                "pool_status": new_status,
            },
        )
        return jsonify(
            external_api_service.ok(
                {"account_id": account_id, "pool_status": new_status}
            )
        )
    except PoolServiceError as exc:
        return _error_response(endpoint, exc)
    except Exception as exc:
        _audit(
            endpoint,
            "error",
            details={"code": "INTERNAL_ERROR", "err": type(exc).__name__},
        )
        return jsonify(external_api_service.fail("INTERNAL_ERROR", "服务内部错误")), 500


@api_key_required
@external_api_guards()
def api_external_pool_stats():
    endpoint = "/api/external/pool/stats"
    disabled_resp = _check_pool_external_enabled(endpoint)
    if disabled_resp is not None:
        return disabled_resp
    try:
        stats = get_pool_stats()
        _audit(endpoint, "ok", details={"snapshot": True})
        return jsonify(external_api_service.ok(stats))
    except Exception as exc:
        _audit(
            endpoint,
            "error",
            details={"code": "INTERNAL_ERROR", "err": type(exc).__name__},
        )
        return jsonify(external_api_service.fail("INTERNAL_ERROR", "服务内部错误")), 500
