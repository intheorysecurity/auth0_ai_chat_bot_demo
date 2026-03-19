import { getAuthedJson } from "@/lib/api";

/**
 * Deterministic orders table for simple "show my orders" prompts (skips LLM + tool spam).
 */
export async function fetchOrdersListMarkdown(accessToken: string): Promise<string> {
  const [ordRes, prodRes] = await Promise.all([
    getAuthedJson<{ orders: Record<string, unknown>[] }>("/api/data/orders", accessToken),
    getAuthedJson<{ products: { id: string; name: string }[] }>("/api/data/products", accessToken),
  ]);

  const nameById = new Map(
    (prodRes.products || []).map((p) => [String(p.id), String(p.name)])
  );
  const orders = ordRes.orders || [];

  if (!orders.length) {
    return "You have no orders visible right now (or none match your access).";
  }

  const header =
    "| Order ID | Product | Qty | Total | Status | Buyer | Created |\n|:---|:---|---:|---:|:---|:---|:---|";
  const rows = orders.map((o) => {
    const id = String(o.id ?? "");
    const pid = String(o.product_id ?? "");
    const name = nameById.get(pid) ?? pid;
    const cents = o.total_cents;
    const total =
      typeof cents === "number" ? `$${(cents / 100).toFixed(2)}` : "?";
    const qty = o.quantity ?? "?";
    const status = String(o.status ?? "?");
    const buyer = String(o.buyer_email ?? o.buyer_sub ?? "—");
    const created =
      typeof o.created_at === "number"
        ? new Date((o.created_at as number) * 1000).toLocaleString()
        : "?";
    return `| ${id} | ${name} | ${qty} | ${total} | ${status} | ${buyer} | ${created} |`;
  });

  return `Here are the orders you can view:\n\n${header}\n${rows.join("\n")}`;
}
