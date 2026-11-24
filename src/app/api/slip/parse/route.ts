/* POST a bet slip screenshot (multipart form, field "image"); get back the draft the user confirms.
   Nothing is graded here: grading runs only after the user has confirmed the legs. */
import { toDraft } from "@/lib/slip/schema";
import { IMAGE_TYPES, MAX_IMAGE_BYTES, SlipReadError, readSlipImage, type ImageType } from "@/lib/slip/vision";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let file: File | null = null;
  try {
    const form = await request.formData();
    const f = form.get("image");
    if (f instanceof File) file = f;
  } catch {
    /* not a form: handled below */
  }
  if (!file) return Response.json({ error: "Send the screenshot as a form field named image." }, { status: 400 });
  if (!(IMAGE_TYPES as readonly string[]).includes(file.type))
    return Response.json({ error: "That file is not a PNG, JPEG, WebP or GIF image." }, { status: 415 });
  if (file.size > MAX_IMAGE_BYTES) return Response.json({ error: "That image is larger than 5 MB. Crop it to the slip and try again." }, { status: 413 });

  try {
    const parsed = await readSlipImage({ data: Buffer.from(await file.arrayBuffer()), mediaType: file.type as ImageType });
    return Response.json({ draft: toDraft(parsed) });
  } catch (error) {
    if (error instanceof SlipReadError) return Response.json({ error: error.message }, { status: error.status });
    console.error("slip parse failed", error);
    return Response.json({ error: "Something went wrong reading that screenshot. Try again." }, { status: 500 });
  }
}
