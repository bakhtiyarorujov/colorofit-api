"""Lightweight localization for API error messages.

The mobile app sends the selected language via the ``Accept-Language`` header
(``en`` / ``az`` / ``ru``). Instead of returning raw English strings (or leaking
exception text), views return a stable machine-readable ``code`` plus a message
localized to the caller's language.

No .po/.mo compilation is needed — messages live in the ``MESSAGES`` table below,
which keeps deploys simple on PythonAnywhere.
"""

SUPPORTED_LANGUAGES = ("en", "az", "ru")
DEFAULT_LANGUAGE = "en"

# code -> {lang: message}
MESSAGES = {
    "server_error": {
        "en": "Something went wrong. Please try again.",
        "az": "Xəta baş verdi. Zəhmət olmasa yenidən cəhd edin.",
        "ru": "Произошла ошибка. Пожалуйста, попробуйте снова.",
    },
    # --- Authentication ---
    "token_required": {
        "en": "Token is required.",
        "az": "Token tələb olunur.",
        "ru": "Требуется токен.",
    },
    "invalid_token": {
        "en": "Invalid or expired token.",
        "az": "Yanlış və ya vaxtı keçmiş token.",
        "ru": "Недействительный или просроченный токен.",
    },
    "invalid_apple_token": {
        "en": "Invalid Apple token.",
        "az": "Yanlış Apple token.",
        "ru": "Недействительный токен Apple.",
    },
    "apple_unreachable": {
        "en": "Could not reach Apple to verify your sign-in. Please try again.",
        "az": "Apple girişini doğrulamaq mümkün olmadı. Zəhmət olmasa yenidən cəhd edin.",
        "ru": "Не удалось связаться с Apple для проверки входа. Пожалуйста, попробуйте снова.",
    },
    "email_missing_apple": {
        "en": "Email is not available from Apple sign-in.",
        "az": "Apple hesabından e-poçt əldə olunmadı.",
        "ru": "Не удалось получить email из входа через Apple.",
    },
    # --- Food recognition / recipes ---
    "image_too_large": {
        "en": "Image is too large. Maximum size is 8 MB.",
        "az": "Şəkil çox böyükdür. Maksimum ölçü 8 MB-dır.",
        "ru": "Изображение слишком большое. Максимальный размер — 8 МБ.",
    },
    "no_food_detected": {
        "en": "No food detected in the image. Please try another photo.",
        "az": "Şəkildə yemək aşkarlanmadı. Zəhmət olmasa başqa şəkil sınayın.",
        "ru": "На изображении еда не обнаружена. Попробуйте другое фото.",
    },
    "recognition_failed": {
        "en": "Could not process the recognition result. Please try again.",
        "az": "Tanıma nəticəsini emal etmək mümkün olmadı. Zəhmət olmasa yenidən cəhd edin.",
        "ru": "Не удалось обработать результат распознавания. Попробуйте снова.",
    },
    "recognition_unavailable": {
        "en": "Food recognition service is unavailable. Please try again later.",
        "az": "Yemək tanıma xidməti hazırda əlçatan deyil. Bir azdan yenidən cəhd edin.",
        "ru": "Сервис распознавания еды недоступен. Повторите попытку позже.",
    },
    "nutrition_unavailable": {
        "en": "Nutrition information is currently unavailable. Please try again later.",
        "az": "Qidalanma məlumatı hazırda əlçatan deyil. Bir azdan yenidən cəhd edin.",
        "ru": "Информация о питании сейчас недоступна. Повторите попытку позже.",
    },
    "recipe_processing_failed": {
        "en": "Could not process the recipe data. Please try again.",
        "az": "Resept məlumatını emal etmək mümkün olmadı. Zəhmət olmasa yenidən cəhd edin.",
        "ru": "Не удалось обработать данные рецепта. Попробуйте снова.",
    },
    # --- Water intake / stats ---
    "intake_type_required": {
        "en": "Please select a drink type first.",
        "az": "Əvvəlcə içki növünü seçin.",
        "ru": "Сначала выберите тип напитка.",
    },
    "date_range_required": {
        "en": "Both start and end dates are required.",
        "az": "Başlanğıc və bitmə tarixləri tələb olunur.",
        "ru": "Требуются даты начала и окончания.",
    },
    "invalid_date_format": {
        "en": "Invalid date format. Use YYYY-MM-DD.",
        "az": "Yanlış tarix formatı. YYYY-MM-DD istifadə edin.",
        "ru": "Неверный формат даты. Используйте ГГГГ-ММ-ДД.",
    },
    "start_after_end": {
        "en": "Start date cannot be after end date.",
        "az": "Başlanğıc tarixi bitmə tarixindən sonra ola bilməz.",
        "ru": "Дата начала не может быть позже даты окончания.",
    },
    # --- Generic (custom exception handler) ---
    "authentication_required": {
        "en": "Authentication required. Please sign in.",
        "az": "Giriş tələb olunur. Zəhmət olmasa daxil olun.",
        "ru": "Требуется авторизация. Пожалуйста, войдите.",
    },
    "permission_denied": {
        "en": "You don't have permission to do this.",
        "az": "Bunu etməyə icazəniz yoxdur.",
        "ru": "У вас нет прав для этого действия.",
    },
    "not_found": {
        "en": "Not found.",
        "az": "Tapılmadı.",
        "ru": "Не найдено.",
    },
    "method_not_allowed": {
        "en": "This action isn't allowed.",
        "az": "Bu əməliyyata icazə verilmir.",
        "ru": "Это действие не разрешено.",
    },
    "throttled": {
        "en": "Too many requests. Please slow down.",
        "az": "Çox sayda sorğu. Zəhmət olmasa bir az gözləyin.",
        "ru": "Слишком много запросов. Пожалуйста, подождите.",
    },
    "validation_error": {
        "en": "Please check the entered information.",
        "az": "Zəhmət olmasa daxil edilən məlumatları yoxlayın.",
        "ru": "Пожалуйста, проверьте введённые данные.",
    },
}


def resolve_language(request):
    """Pick a supported language from the request's ``Accept-Language`` header.

    Accepts simple codes (``az``) or full headers (``az-AZ,az;q=0.9,en;q=0.8``)
    and returns the first supported match, or the default.
    """
    if request is None:
        return DEFAULT_LANGUAGE
    header = request.META.get("HTTP_ACCEPT_LANGUAGE", "") or ""
    for part in header.split(","):
        code = part.split(";")[0].strip().lower().split("-")[0]
        if code in SUPPORTED_LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def translate(request, code, **fmt):
    """Return the localized message for ``code`` in the request's language.

    Falls back to English, then to the raw code if unknown. Optional ``**fmt``
    values are applied with ``str.format``.
    """
    lang = resolve_language(request)
    entry = MESSAGES.get(code)
    if not entry:
        return code
    message = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or code
    if fmt:
        try:
            message = message.format(**fmt)
        except (KeyError, IndexError, ValueError):
            pass
    return message


def error_payload(request, code, **extra):
    """Consistent error body: ``{"error": <localized>, "code": <code>, ...}``."""
    payload = {"error": translate(request, code), "code": code}
    payload.update(extra)
    return payload
