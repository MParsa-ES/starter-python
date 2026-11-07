# راهنمای آزمون API قوانین ریسک

این مراحل برای محیط توسعه و داده آزمایشی است؛ POST و PATCH داده واقعی ایجاد یا تغییر می‌دهند. اجرای تست خودکار را روی PostgreSQL آزمایشی جداگانه انجام دهید. تست API با ابزار مرورگر یا PowerShell جایگزین تست واحد و integration خودکار نیست.

## آماده‌سازی

1. از ریشه پروژه `docker compose up -d --build` را اجرا کنید. فایل‌های migration جدید باید اجرا شوند؛ در صورت لزوم `docker compose exec -w /app/s4_rsk s4-rsk python manage.py migrate` را اجرا کنید.
2. مطابق [راهنمای JWT](jwt-authentication.md) کاربر فعال بسازید و در Django admin گروه دقیق `manager` را به او اختصاص دهید. superuser بودن به‌تنهایی کافی نیست.
3. `http://localhost:8084/api/docs/` را باز کنید. در `POST /api/v1/auth/token/` نام کاربری و رمز را وارد کنید و access را از پاسخ بردارید. در Authorize مقدار access را وارد کنید. در هدر درخواست باید `Authorization: Bearer <access>` ارسال شود. توکن را در Git و تصویر قرار ندهید.
4. برای پایان اعتبار access، با refresh فعلی `POST /api/v1/auth/token/refresh/` را اجرا و access و refresh جدید را جایگزین کنید. جزئیات و خروج در راهنمای JWT آمده است.

## گردش آزمون در Swagger

1. `GET /api/v1/risk-rules` را با Try it out و Execute اجرا کنید. پاسخ 200 و `items` و `next_cursor` است. `limit` اندازه صفحه است و `cursor` پاسخ قبلی را برای صفحه بعد می‌دهید.
2. `POST /api/v1/risk-rules` را اجرا کنید. `Idempotency-Key` اختیاری و از نوع UUID است. برای retry امن یک UUID جدید برای هر عملیات منطقی تولید کنید؛ تکرار همان کلید با همان بدنه پاسخ 201 اولیه را برمی‌گرداند و بدنه یا کاربر متفاوت 409 با کد `IDEMPOTENCY_KEY_REUSED` می‌دهد. بدون کلید، تکرار POST یک قانون جدید می‌سازد.

```json
{"name":"Demo limit","type":"AMOUNT_LIMIT","parameters":{"max_amount":100},"enabled":false}
```

شناسه `id` و `revision` پاسخ را نگه دارید. `effective_at` اختیاری است و اگر ارائه شود باید تاریخ و زمان معتبر باشد.

3. `PATCH /api/v1/risk-rules/{rule_id}` را با id و revision آخر اجرا کنید:

```json
{"expected_revision":1,"parameters":{"max_amount":200}}
```

باید 200 و revision برابر ۲ دریافت کنید. حداقل یک فیلد قابل ویرایش لازم است؛ `type`، `actor` و `revision` قابل ارسال برای ویرایش نیستند. ارسال مجدد revision قدیمی باید 409 بدهد.

4. `GET /api/v1/risk-rules/{rule_id}/audit` را اجرا کنید: نسخه‌های ۲ و ۱ به ترتیب نزولی نمایش داده می‌شوند؛ actor شناسه کاربر احراز هویت‌شده و before/after وضعیت‌های ثبت‌شده هستند.
5. جداگانه مقدار ۰، مقدار بیش از `9223372036854775807`، بدنه ناقص، کاربر بدون manager و درخواست بدون توکن را تست کنید. به‌ترتیب خطای 400، 400، 400، 403 و 401 انتظار می‌رود. پاسخ خطا `application/problem+json` دارد. UUID معتبر ولی ناموجود برای PATCH یا audit پاسخ 404 می‌دهد. ارسال UUID نامعتبر در مسیر ممکن است پیش از رسیدن به view نیز 404 بدهد.

## نمونه PowerShell

پس از گرفتن access در متغیر `$access`، دستورهای زیر را اجرا کنید. برای تولید کلید از PowerShell استفاده کنید و در تکرار همان عملیات `$key` را عوض نکنید:

```powershell
$base = 'http://localhost:8084/api/v1'
$headers = @{ Authorization = "Bearer $access" }
$key = [guid]::NewGuid().ToString()
$createHeaders = @{ Authorization = "Bearer $access"; 'Idempotency-Key' = $key }
$body = @{ name='Demo limit'; type='AMOUNT_LIMIT'; parameters=@{ max_amount=100 }; enabled=$false } | ConvertTo-Json -Depth 5
$rule = Invoke-RestMethod -Method Post -Uri "$base/risk-rules" -Headers $createHeaders -ContentType 'application/json' -Body $body
$id = $rule.id
$patch = @{ expected_revision=$rule.revision; parameters=@{ max_amount=200 } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Patch -Uri "$base/risk-rules/$id" -Headers $headers -ContentType 'application/json' -Body $patch
Invoke-RestMethod -Method Get -Uri "$base/risk-rules/$id/audit" -Headers $headers
```

## تست خودکار و migration

در PowerShell از ریشه پروژه `cd s4_rsk` و سپس `..\.venv\Scripts\python.exe -m pytest --create-db` را اجرا کنید. تنظیمات مشترک در `s4_rsk/pytest.ini` قرار دارد و `--reuse-db` فعال است؛ پس از migration تازه `--create-db` دیتابیس **تست** را بازسازی می‌کند. هرگز آن را به دیتابیس غیرآزمایشی اشاره ندهید. برای اجرا بدون تغییر پوشه از ریشه می‌توانید `.\.venv\Scripts\python.exe -m pytest -c s4_rsk/pytest.ini s4_rsk --create-db` را اجرا کنید. تست subprocess مربوط به manage.py عمداً پوشه `s4_rsk` را به‌عنوان working directory تنظیم می‌کند.

تاریخچه تنها برای تغییرات مسیر سرویس تضمین می‌شود؛ تغییر مستقیم ORM/SQL قانون را دور می‌زند. trigger PostgreSQL از UPDATE و DELETE معمولی روی تاریخچه جلوگیری می‌کند اما از TRUNCATE یا غیرفعال‌کردن trigger توسط مالک جلوگیری نمی‌کند. در production دسترسی دیتابیس و فرآیند migration را تفکیک و محدود کنید. داده‌های قدیمی گذشته‌نگر بازسازی نشده‌اند.
