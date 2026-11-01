import createClient from "openapi-fetch";
import type { paths } from "./schema";

// The frontend talks to the backend only through this typed client.
// Its types come from openapi/s4_rsk.yaml (npm run gen:api).
// In development Vite forwards /api to the Django service (see vite.config.ts).
export const api = createClient<paths>({ baseUrl: "/api/v1" });
