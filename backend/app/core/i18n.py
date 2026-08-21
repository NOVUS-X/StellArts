"""
Lightweight i18n support for the FastAPI backend.

Parses the ``Accept-Language`` header and provides translated error
messages for the supported locales (English, Spanish, French).
"""

from __future__ import annotations

import re

from fastapi import Request

SUPPORTED_LOCALES = ("en", "es", "fr")
DEFAULT_LOCALE = "en"


_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "internal_error": "Internal server error",
        "not_found": "The requested resource was not found",
        "unauthorized": "Authentication required",
        "forbidden": "You do not have permission to access this resource",
        "bad_request": "Bad request",
        "conflict": "The request conflicts with the current state of the resource",
        "rate_limit": "Rate limit exceeded. Please try again later",
        "validation_error": "Request validation failed",
        "email_already_registered": "An account with this email already exists",
        "invalid_credentials": "Invalid email or password",
        "token_expired": "Your session has expired. Please log in again",
        "account_disabled": "This account has been disabled",
        "not_found_detail": "The resource you are looking for could not be found",
        "method_not_allowed": "The HTTP method is not allowed for this endpoint",
        "request_too_large": "The request payload is too large",
        "service_unavailable": "Service temporarily unavailable. Please try again later",
    },
    "es": {
        "internal_error": "Error interno del servidor",
        "not_found": "El recurso solicitado no fue encontrado",
        "unauthorized": "Se requiere autenticación",
        "forbidden": "No tiene permiso para acceder a este recurso",
        "bad_request": "Solicitud incorrecta",
        "conflict": "La solicitud entra en conflicto con el estado actual del recurso",
        "rate_limit": "Límite de velocidad excedido. Por favor, inténtelo de nuevo más tarde",
        "validation_error": "Error de validación de la solicitud",
        "email_already_registered": "Ya existe una cuenta con este correo electrónico",
        "invalid_credentials": "Correo electrónico o contraseña inválidos",
        "token_expired": "Su sesión ha expirado. Por favor, inicie sesión de nuevo",
        "account_disabled": "Esta cuenta ha sido deshabilitada",
        "not_found_detail": "El recurso que busca no pudo ser encontrado",
        "method_not_allowed": "El método HTTP no está permitido para este endpoint",
        "request_too_large": "La carga de la solicitud es demasiado grande",
        "service_unavailable": "Servicio temporalmente no disponible. Por favor, inténtelo de nuevo más tarde",
    },
    "fr": {
        "internal_error": "Erreur interne du serveur",
        "not_found": "La ressource demandée est introuvable",
        "unauthorized": "Authentification requise",
        "forbidden": "Vous n'avez pas la permission d'accéder à cette ressource",
        "bad_request": "Requête invalide",
        "conflict": "La requête est en conflit avec l'état actuel de la ressource",
        "rate_limit": "Limite de débit dépassée. Veuillez réessayer plus tard",
        "validation_error": "Échec de la validation de la requête",
        "email_already_registered": "Un compte avec cet e-mail existe déjà",
        "invalid_credentials": "E-mail ou mot de passe invalide",
        "token_expired": "Votre session a expiré. Veuillez vous connecter à nouveau",
        "account_disabled": "Ce compte a été désactivé",
        "not_found_detail": "La ressource que vous recherchez est introuvable",
        "method_not_allowed": "La méthode HTTP n'est pas autorisée pour ce point de terminaison",
        "request_too_large": "La charge de la requête est trop volumineuse",
        "service_unavailable": "Service temporairement indisponible. Veuillez réessayer plus tard",
    },
}


def _parse_accept_language(header: str) -> list[tuple[str, float]]:
    """Parse an ``Accept-Language`` header into ``(locale, quality)`` pairs.

    Example header: ``"es-MX,es;q=0.9,en;q=0.8,fr;q=0.7"``
    Returns: ``[("es-MX", 1.0), ("es", 0.9), ("en", 0.8), ("fr", 0.7)]``
    """
    result: list[tuple[str, float]] = []
    if not header:
        return result

    for part in header.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.match(r"^([a-zA-Z-]+)(?:;q=([\d.]+))?$", part)
        if match:
            locale = match.group(1)
            quality = float(match.group(2)) if match.group(2) else 1.0
            result.append((locale, quality))

    result.sort(key=lambda x: x[1], reverse=True)
    return result


def resolve_locale(header: str | None) -> str:
    """Resolve the best matching locale from an ``Accept-Language`` header.

    Returns one of the ``SUPPORTED_LOCALES`` or ``DEFAULT_LOCALE``.
    """
    if not header:
        return DEFAULT_LOCALE

    parsed = _parse_accept_language(header)
    for locale, _quality in parsed:
        base = locale.split("-")[0].lower()
        if base in SUPPORTED_LOCALES:
            return base

    return DEFAULT_LOCALE


def get_locale_from_request(request: Request) -> str:
    """Extract the locale from the request's ``Accept-Language`` header."""
    accept_language = request.headers.get("accept-language")
    return resolve_locale(accept_language)


def translate(key: str, locale: str | None = None) -> str:
    """Return the translated message for *key* in the given *locale*.

    Falls back to English if the key is missing in the requested locale.
    """
    locale = locale or DEFAULT_LOCALE
    messages = _MESSAGES.get(locale, _MESSAGES[DEFAULT_LOCALE])
    return messages.get(key, _MESSAGES[DEFAULT_LOCALE].get(key, key))
