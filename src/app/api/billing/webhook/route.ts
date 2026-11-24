import { userStore } from "@/lib/advisor/server";
import { BillingError, handleStripeWebhook } from "@/lib/billing/stripe";

/** Stripe calls this when a subscription starts, changes or ends. See src/lib/billing/stripe.ts. */
export async function POST(request: Request) {
  const body = await request.text(); // the signature covers the exact bytes, so do not parse first
  try {
    const result = await handleStripeWebhook({ body, signature: request.headers.get("stripe-signature"), store: userStore() });
    return Response.json(result);
  } catch (error) {
    if (error instanceof BillingError) return Response.json({ error: error.message }, { status: error.status });
    console.error("billing webhook failed", error);
    return Response.json({ error: "The webhook could not be processed." }, { status: 500 });
  }
}
