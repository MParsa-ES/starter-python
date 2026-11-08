# راهنمای احراز هویت JWT در S4-RSK

API از Bearer JWT استفاده می‌کند. ورود به پنل Django همچنان session و CSRF خود را دارد؛ ورود به پنل به معنی دریافت توکن API نیست. ارتباط S3 پیش‌نویس است: `contracts/s3-s4-jwt-draft.md`.

## آماده‌سازی

1. از ریشه مخزن `docker compose up -d --build` را اجرا کنید. وابستگی جدید در `requirements.txt` ثبت شده است.
2. مهاجرت‌های جدید از جمله blacklist باید اجرا شوند: `docker compose exec -w /app/s4_rsk s4-rsk python manage.py migrate`.
3. در محیط توسعه یک مدیر بسازید: `docker compose exec -w /app/s4_rsk s4-rsk python manage.py createsuperuser`. رمز را به صورت تعاملی وارد کنید و در مخزن ننویسید.
4. به `http://localhost:8084/admin/` وارد شوید. در Groups یک گروه دقیقاً با نام `manager` بسازید، سپس در Users آن را به کاربر تخصیص دهید. داشتن superuser به تنهایی دسترسی به قوانین را نمی‌دهد.
5. برای ساخت کاربر معمولی در پنل Users > Add user را بزنید؛ نقش مناسب را فقط مدیر به کاربر تخصیص می‌دهد. برای حساب سرویس پرداخت گروه جداگانه `payment_service` لازم است و به آن `manager` ندهید.

## ورود و Swagger

1. `http://localhost:8084/api/docs/` را باز کنید.
2. مسیر `POST /api/v1/auth/token/` را با username و password اجرا کنید. خروجی access و refresh دارد. این دو را محرمانه نگه دارید.
3. در Authorize مقدار access را وارد کنید؛ درخواست‌ها با `Authorization: Bearer <access>` ارسال می‌شوند. `GET /api/v1/risk-rules` برای manager است.
4. access پنج دقیقه عمر دارد. برای دریافت جفت جدید، `POST /api/v1/auth/token/refresh/` را با بدنه `{"refresh":"<refresh>"}` اجرا کنید و هر دو توکن جدید را جایگزین کنید. refresh قبلی پس از چرخش باطل می‌شود.
5. برای خروج `POST /api/v1/auth/token/logout/` را با refresh جاری اجرا کنید. این کار refresh را باطل می‌کند؛ access صادرشده تا پایان اعتبار پنج دقیقه‌ای معتبر می‌ماند.

توکن نامعتبر یا فاقد اعتبار 401 و کاربر بدون نقش مورد نیاز 403 می‌گیرد. تغییر رمز عبور و غیرفعال‌شدن کاربر اعتبار توکن را هنگام احراز هویت بررسی می‌کند. از انتشار توکن، قرار دادن آن در Git، لاگ، URL یا تصاویر صفحه خودداری کنید. در محیط واقعی HTTPS الزامی است؛ در مرورگر از ذخیره طولانی‌مدت توکن در localStorage خودداری کنید.

کلید امضا از `JWT_SIGNING_KEY` خوانده می‌شود؛ فقط در حالت توسعه در نبود آن از `SECRET_KEY` استفاده می‌شود. با `DEBUG=False` کلید مستقل الزامی است. کلید تصادفی را در secret manager قرار دهید، نه در مخزن. issuer و audience به `labbank-s4-rsk` و `labbank-s4-rsk-api` محدودند. نرخ درخواست مسیرهای توکن در هر فرایند با cache پیش‌فرض محدود است؛ برای چند worker و استقرار واقعی cache مشترک، محدودسازی در gateway و پایش لازم است. برای پاک‌سازی blacklist منقضی، `python manage.py flushexpiredtokens` را به صورت دوره‌ای اجرا کنید.
