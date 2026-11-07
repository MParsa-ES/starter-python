// نمایش خطاهای بک‌اند با قالب RFC 9457 (Content-Type: application/problem+json).
// بک‌اند S4-RSK این فیلدها را برمی‌گرداند: type, title, status, code, detail, correlation_id.

export type ProblemDetailsBody = {
  type?: string;
  title: string;
  status: number;
  code?: string;
  detail?: string;
  correlation_id?: string;
};

// اگر پاسخ خطا از نوع problem+json بود بدنه‌اش را برمی‌گرداند، وگرنه null.
export async function readProblem(res: Response): Promise<ProblemDetailsBody | null> {
  const type = res.headers.get("Content-Type") ?? "";
  if (!type.includes("application/problem+json")) return null;
  try {
    const body = (await res.json()) as Partial<ProblemDetailsBody>;
    if (typeof body.title !== "string") return null;
    return { ...body, title: body.title, status: body.status ?? res.status };
  } catch {
    return null;
  }
}
