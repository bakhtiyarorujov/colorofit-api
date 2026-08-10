"""Custom DRF exception handler.

Turns DRF/Django exceptions into a consistent, localized shape:

    {"error": "<localized message>", "code": "<stable code>"}

Validation errors additionally carry the per-field details under ``fields`` so
the client can still map them if needed. Unhandled server errors are logged in
full server-side but return only a generic localized message — no stack traces
or raw exception text ever reach the client.
"""

import logging

from rest_framework import exceptions as drf_exc
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .i18n import error_payload

logger = logging.getLogger(__name__)


def _code_for(exc):
    if isinstance(exc, (drf_exc.NotAuthenticated, drf_exc.AuthenticationFailed)):
        return "authentication_required"
    if isinstance(exc, drf_exc.PermissionDenied):
        return "permission_denied"
    if isinstance(exc, drf_exc.NotFound):
        return "not_found"
    if isinstance(exc, drf_exc.MethodNotAllowed):
        return "method_not_allowed"
    if isinstance(exc, drf_exc.Throttled):
        return "throttled"
    if isinstance(exc, (drf_exc.ValidationError, drf_exc.ParseError)):
        return "validation_error"
    return None


def custom_exception_handler(exc, context):
    request = context.get("request") if context else None
    response = drf_exception_handler(exc, context)

    # Non-DRF exception → DRF returns None and Django would render a 500.
    # Log the real error, return a clean localized message instead.
    if response is None:
        logger.exception("Unhandled server error: %s", exc)
        return Response(error_payload(request, "server_error"), status=500)

    code = _code_for(exc)
    if code is None:
        # A DRF exception we don't specifically map — keep its status, but still
        # present a consistent, non-leaky body.
        return Response(
            error_payload(request, "server_error"), status=response.status_code
        )

    payload = error_payload(request, code)
    if code == "validation_error":
        # Preserve the field-level details for clients that use them.
        payload["fields"] = response.data
    response.data = payload
    return response
