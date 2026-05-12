/** Sets up MSW's service worker for in-browser interception. */
import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
