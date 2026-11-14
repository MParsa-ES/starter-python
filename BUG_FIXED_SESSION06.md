# BUG_FIXED_SESSION06.md

## سرویس و اعضای تیم
- **سرویس:** `S4-RSK` (سرویس ارزیابی ریسک و تقلب - Risk & Fraud Decisioning)
- **اعضای تیم:**
  - ابوالفضل تاجیک (`40331013`)
  - محمد پارسا اسماعیلی
  - علی جوهری طهرانی

## مخزن تمرین
- **مخزن تمرین جلسه ۶:** `LabBank-S4-Session06`
- **بخش مورد بررسی:** آمار تصمیم‌های ریسک (`GET /api/v1/risk-statistics?start=<UTC>&end=<UTC>`) در ماژول `s4_rsk/dashboard/`

---

## رفتار اشتباه و علت اصلی (Root Cause)

### ۱. مشاهده و بازتولید رفتار نادرست
طبق قرارداد OpenAPI سرویس (`openapi/s4_rsk.yaml`)، مستندات سریالایزر و راهنمای جلسه ۶ (`SESSION_06_GUIDE.md`)، بازه‌ی زمانی آمار در مسیر `GET /api/v1/risk-statistics` از نوع **نیمه‌باز `[start, end)`** تعریف شده است (`start <= evaluated_at < end`):
- زمان شروع (`start`) داخل بازه قرار دارد (Inclusive).
- زمان پایان (`end`) خارج از بازه قرار دارد (Exclusive).
- در نتیجه، رکوردی که زمان ارزیابی آن دقیقاً برابر با زمان پایان بازه باشد (`evaluated_at == end`) نباید در آمار آن بازه شمرده شود؛ همچنین زمانی که `start == end` باشد، بازه تهی است و شمارش تمام تصمیم‌ها باید `0` برگردد.

**رفتار نادرست مشاهده‌شده:**
رکورد واقع بر مرز انتهایی `end` به اشتباه در آمار شمرده می‌شد و بازه‌ی زمانی برای رکوردهای لب مرز به‌درستی فیلتر نمی‌شد.

### ۲. تحلیل علت اصلی (Root Cause) و شواهد دیباگ
با نوشتن ۳ تست بازتولید بر روی مرزهای `start` و `end` و دنبال کردن مسیر اجرای درخواست تا لایه‌ی داده (`dashboard/selectors.py`)، مشخص شد که در تابع `count_decisions_by_type` و کوئری SQL تولیدشده توسط ORM، به جای عملگر کوچک‌تر اکید (`__lt`)، از عملگر کوچک‌تر یا مساوی (`__lte`) برای مرز انتهایی استفاده شده است:

```python
qs = RiskAssessment.objects.filter(
    evaluated_at__gte=start,
    evaluated_at__lte=end  # <-- BUG: translates to evaluated_at <= end instead of evaluated_at < end
).values('decision').annotate(count=Count('decision'))
```
همچنین چون تست‌های `test_services.py` و `test_views.py` این سلکتور را با `monkeypatch` شبیه‌سازی کرده بودند و در `test_selectors.py` تستی دقیقاً روی مرز `end` وجود نداشت، این باگ در تست‌های قبلی پنهان مانده بود.

---

## اصلاح انجام شده (Bug Fix & Refactoring)

### ۱. اصلاح باگ (Bug Fix)
در فایل `s4_rsk/dashboard/selectors.py`، فیلتر `evaluated_at__lte=end` به `evaluated_at__lt=end` اصلاح شد تا بازه‌ی نیمه‌باز `[start, end)` در سطح پایگاه داده به‌درستی اعمال شود.

### ۲. شناسایی Code Smell و بازآرایی (Refactoring)
- **Code Smell شناسایی‌شده (Primitive Obsession / Magic Strings):** در `s4_rsk/dashboard/services.py`، ثابت `DECISION_TYPES = ("APPROVE", "REVIEW", "REJECT")` به صورت دستی تعریف شده بود، در حالی که `DecisionType` در `assessments.models` منبع واحد حقیقت برای انواع تصمیم است.
- **بازآرایی انجام‌شده:** مقدار `DECISION_TYPES` از `tuple(DecisionType.values)` خوانده شد. از آنجا که خروجی این مقدار همان سه رشته قبلی است، ساختار JSON پاسخ در API کاملاً بدون تغییر باقی ماند. همچنین در `test_selectors.py`، برای جلوگیری از آپدیت‌های تکراری با `save(update_fields=["evaluated_at"])`، قابلیت پاس دادن `evaluated_at` به تابع `create_assessment` اضافه شد.

---

## تست ها و نتیجه اجرا

### ۱. تست پیش از اصلاح (شکست تست‌های بازتولید)
```text
dashboard/test_selectors.py::test_count_decisions_by_type_is_half_open_includes_start_excludes_end FAILED
dashboard/test_selectors.py::test_count_decisions_by_type_empty_when_start_equals_end_at_record_timestamp FAILED
dashboard/test_selectors.py::test_risk_statistics_endpoint_excludes_record_on_end_boundary FAILED

E       AssertionError: assert {'APPROVE': 1, 'REJECT': 1, 'REVIEW': 1} == {'APPROVE': 1, 'REVIEW': 1}
```

### ۲. تست پس از اصلاح و بازآرایی
```text
dashboard/test_selectors.py::test_count_decisions_by_type_is_half_open_includes_start_excludes_end PASSED
dashboard/test_selectors.py::test_count_decisions_by_type_empty_when_start_equals_end_at_record_timestamp PASSED
dashboard/test_selectors.py::test_risk_statistics_endpoint_excludes_record_on_end_boundary PASSED
======================================== 22 passed in 1.25s ========================================
```

### ۳. نتیجه کل تست ها (Regression Suite)
اجرای بررسی Linter و کل مجموعه تست‌های پروژه:
```text
$ ruff check --fix .
Found 3 errors (3 fixed, 0 remaining).

$ pytest -v
======================================== 131 passed in 10.77s ========================================
```

---

## فایل های تغییر یافته
در مخزن تمرین جلسه ۶ (`LabBank-S4-Session06`):
- `s4_rsk/dashboard/selectors.py`: تغییر `__lte` به `__lt`.
- `s4_rsk/dashboard/services.py`: استفاده از `DecisionType.values` به جای مقادیر سخت‌کد شده.
- `s4_rsk/dashboard/test_selectors.py`: افزودن ۳ تست بازتولید باگ در لبه‌های بازه و بهبود تابع Helper.

در مخزن اصلی تیم (`starter-python`):
- `BUG_FIXED_SESSION06.md`: ثبت این گزارش در ریشهٔ مخزن.

---

## نتیجه نهایی
باگِ مرز انتهاییِ بازه‌ی زمانی با ۳ تست بازتولید مشخص شد، شرط پایگاه داده اصلاح و Code Smell از بین رفت؛ بدون ایجاد Regression در سایر بخش‌ها، تمامی ۱۳۱ تست با موفقیت اجرا شدند.