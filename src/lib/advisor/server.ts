/**
 * What the advisor's API routes share on the server: the user store, the model, and who is asking.
 */
import { validUserId } from "../store/types.ts";
import { FileStore } from "../store/file.ts";
import { readSlipImage, type ImageType } from "../slip/vision.ts";
import { ADVISOR_MODEL, callClaude } from "./claude.ts";
import { demoEnabled, demoModel, demoReadImage } from "./demo-model.ts";
import { loadAlgorithmData } from "./server-data.ts";
import type { ServiceDeps } from "./service.ts";

let store: FileStore | null = null;
export function userStore(): FileStore {
  store ??= new FileStore();
  return store;
}

/** Everything a turn needs. In demo mode the model and the screenshot reader are scripted stand-ins. */
export function deps(): ServiceDeps {
  const demo = demoEnabled();
  return {
    store: userStore(),
    callModel: demo ? demoModel : callClaude,
    model: demo ? "demo" : ADVISOR_MODEL,
    algo: loadAlgorithmData(),
    readImage: demo ? demoReadImage : (image) => readSlipImage({ data: image.data, mediaType: image.mediaType as ImageType }),
    // demo mode has no payments to check, so it chats on the Pro plan unless told otherwise
    env: demo && !process.env.ADVISOR_DEV_TIER ? { ...process.env, ADVISOR_DEV_TIER: "pro" } : process.env,
  };
}

/**
 * The user a request is for. Until logins exist this is an id the browser made up and keeps, sent in a header.
 * It identifies a browser, not a person, and proves nothing: sign-in replaces it.
 */
export function userIdFrom(request: Request): string | null {
  const id = request.headers.get("x-godseye-user");
  return validUserId(id) ? id : null;
}
