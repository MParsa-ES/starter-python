# ماتریس تست (Test Matrix) - داشبورد ریسک (US-03)

| شناسه تست | شرح سناریو | نوع مسیر | دسته‌بندی | وضعیت پوشش | تست متناظر / دلیل عدم پوشش |
|---|---|---|---|---|---|
| `TC-001` | دریافت آمار با بازه زمانی معتبر (`start` < `end`) و محاسبه درست تصمیم‌ها | مسیر اصلی | بک‌اند (Unit) | پوشش داده شده | `test_valid_range_returns_statistics`, `test_valid_range_is_accepted` |
| `TC-002` | تکمیل انواع تصمیم‌های غایب در خروجی دیتابیس با مقدار صفر | مسیر اصلی | بک‌اند (Unit) | پوشش داده شده | `test_missing_decision_types_are_filled_with_zero` |
| `TC-003` | درخواست آمار با بازه زمانی برعکس (`start` > `end`) - دریافت خطای 400 | Edge Case | بک‌اند (Unit) | پوشش داده شده | `test_reversed_range_returns_400_problem_details`, `test_reversed_range_is_rejected` |
| `TC-004` | درخواست آمار بدون پارامترهای اجباری یا با فرمت نامعتبر - دریافت خطای 400 | Edge Case | بک‌اند (Unit) | پوشش داده شده | `test_missing_parameters_return_400`, `test_missing_or_malformed_values_are_rejected` |
| `TC-005` | درخواست آمار با بازه زمانی خالی (`start` == `end`) - دریافت مقادیر صفر | Edge Case | بک‌اند (Unit) | پوشش داده شده | `test_empty_range_gives_all_zeros`, `test_start_equal_to_end_is_an_empty_but_valid_range` |
| `TC-006` | وجود هدر `X-Correlation-ID` در پاسخ موفق سیستم | مسیر اصلی | بک‌اند (Unit) | پوشش داده شده | `test_response_carries_the_correlation_header` |
| `TC-007` | شمارش واقعی تصمیم‌ها و فیلتر بازه زمانی روی دیتابیس PostgreSQL | مسیر اصلی | بک‌اند (Integration) | پوشش داده شده | `test_count_decisions_by_type_groups_correctly`, `test_count_decisions_by_type_respects_time_range` |
| `TC-008` | شمارش واقعی آیتم‌های باز در صف بررسی دستی (`queue_size_now`) از دیتابیس | مسیر اصلی | بک‌اند (Integration) | هنوز تست ندارد | وابسته به مدل `ManualReviewItem` (استوری US-04A) که هنوز پیاده‌سازی نشده است. |
| `TC-009` | نمایش داشبورد و فراخوانی خودکار API با تغییر فیلتر تاریخ | مسیر اصلی | فرانت‌اند | هنوز تست ندارد | بخش فرانت‌اند داشبورد (US-03B) در این اسپرینت برنامه‌ریزی نشده است. |
| `TC-010` | نمایش واضح خطای اعتبارسنجی بک‌اند (Problem Details) در رابط کاربری | Edge Case | فرانت‌اند | هنوز تست ندارد | کامپوننت فرانت‌اند داشبورد هنوز توسعه داده نشده است. |