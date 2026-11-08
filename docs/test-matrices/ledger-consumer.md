# ماتریس تست مصرف‌کننده: کلاینت دفترکل S2-LDG

وضعیت: کلاینت `s4_rsk/integrations/ledger_client.py` آزمون شده است ولی هنوز در `assessments.services` فراخوانی نمی‌شود (US-01B). پاسخ‌های Stub از مثال‌های `openapi/neighbors/s2_ldg.yaml` گرفته شده‌اند. اگر فایل واقعی S2 جایگزین شد، تست‌ها دوباره اجرا شوند.

| شناسه | سناریو | پاسخ Stub / ورودی | نتیجهٔ مورد انتظار | Edge | تست خودکار |
|---|---|---|---|---|---|
| L-01 | پاسخ موفق | 200 با دو بدهکاری | دو ورودی تجزیه‌شده، وضعیت OK، بدون تصمیم اجباری؛ درخواست شامل `direction=DEBIT`، `from` و `X-Correlation-ID` | خیر | `test_success_returns_parsed_debits_and_sends_the_draft_request` |
| L-02 | صفحه‌بندی | صفحهٔ اول با `next_cursor` | درخواست دوم با همان cursor و ادغام نتایج | بله | `test_pagination_follows_next_cursor_until_exhausted` |
| L-03 | حساب ناموجود | 404 Problem Details | `ACCOUNT_NOT_FOUND` و تصمیم اجباری REVIEW | بله | `test_unknown_account_forces_review_with_explicit_reason` |
| L-04 | Timeout | استثنای `ConnectTimeout` | `LEDGER_UNAVAILABLE` و REVIEW بدون پرتاب خطا | بله | `test_timeout_forces_review_instead_of_raising` |
| L-05 | خطای سرور | 503 Problem Details | `LEDGER_UNAVAILABLE` و REVIEW | بله | `test_server_error_forces_review` |
| L-06 | بدنهٔ ناقص | 200 بدون فیلد `amount` | خطا، نه اعتماد به داده؛ REVIEW | بله | `test_malformed_success_body_is_not_trusted` |
| L-07 | آدرس همسایه | `NEIGHBOR_BASE_URL` | درخواست به همان میزبان و پورت می‌رود | خیر | `test_neighbor_base_url_environment_variable_selects_the_host` |
| L-08 | آدرس تنظیم‌نشده | بدون متغیر محیطی | خطای روشن، نه آدرس حدسی | بله | `test_missing_neighbor_base_url_is_a_clear_error` |
| L-09 | خطای غیرمنتظرهٔ ۴xx | 403 | خطا، نه تاریخچهٔ خالی؛ تصمیم اجباری REVIEW | بله | `test_unexpected_client_error_is_not_treated_as_empty_history` |
| L-10 | زنجیرهٔ بی‌پایان cursor | هر صفحه `next_cursor` دارد | قطع پس از سقف صفحه‌ها با خطا | بله | `test_endless_cursor_chain_is_cut_off` |
| L-11 | توکن سرویس | کلاینت با `token` | هدر `Authorization: Bearer` ارسال می‌شود | خیر | `test_bearer_token_is_sent_when_configured` |
| L-12 | Contract Test روی Prism یا همسایهٔ واقعی | `NEIGHBOR_BASE_URL` | موفق و خطا با قرارداد همسایه می‌خوانند | خیر | `test_ledger_contract.py` (نشانگر `contract`) |

## پوشش‌نیافته‌ها

- احراز هویت سرویس‌به‌سرویس به S2: روش آن هنوز با تیم S2 توافق نشده؛ فقط ارسال هدر آزموده شده (L-11)، نه پذیرفته‌شدن توسط S2.
- retry با backoff: عمداً پیاده‌سازی نشده است؛ هر خطا یک سیگنال REVIEW است (طبق نمودار توالی جلسهٔ ۴).
