"use client";

type ProductRow = {
  id?: unknown;
  name?: unknown;
  price_cents?: unknown;
  image_url?: unknown;
  tags?: unknown;
};

function formatPrice(cents: unknown): string {
  if (typeof cents !== "number" || Number.isNaN(cents)) return "—";
  return `$${(cents / 100).toFixed(2)}`;
}

function parseProductRows(raw: unknown): ProductRow[] {
  if (!Array.isArray(raw)) return [];
  return raw as ProductRow[];
}

export function tryParseListProductsResult(resultText: string): {
  products: ProductRow[];
  total_products?: number;
  returned?: number;
} | null {
  try {
    const p = JSON.parse(resultText) as {
      products?: unknown;
      total_products?: unknown;
      returned?: unknown;
    };
    const products = parseProductRows(p.products);
    if (!products.length) return null;
    return {
      products,
      total_products: typeof p.total_products === "number" ? p.total_products : undefined,
      returned: typeof p.returned === "number" ? p.returned : undefined,
    };
  } catch {
    return null;
  }
}

export function tryParseGetProductResult(resultText: string): ProductRow | null {
  try {
    const p = JSON.parse(resultText) as { product?: unknown };
    const pr = p.product;
    if (!pr || typeof pr !== "object") return null;
    return pr as ProductRow;
  } catch {
    return null;
  }
}

function TagList({ tags }: { tags: unknown }) {
  if (!Array.isArray(tags) || tags.length === 0) return <span className="text-gray-400">—</span>;
  return (
    <span className="line-clamp-2" title={tags.map(String).join(", ")}>
      {tags.map(String).join(", ")}
    </span>
  );
}

export function ProductListToolTable({
  products,
  total_products,
  returned,
  metaHint,
}: {
  products: ProductRow[];
  total_products?: number;
  returned?: number;
  /** When set, replaces the default "Showing X of Y" line */
  metaHint?: string;
}) {
  const meta =
    metaHint ??
    (typeof total_products === "number" && typeof returned === "number"
      ? `Showing ${returned} of ${total_products} in catalog`
      : `Showing ${products.length} product${products.length === 1 ? "" : "s"}`);

  return (
    <div className="mt-2 space-y-1.5">
      <p className="text-[11px] text-gray-500 dark:text-gray-400">{meta}</p>
      <div className="overflow-x-auto rounded border border-gray-200 dark:border-gray-600">
        <table className="w-full text-left text-[11px] border-collapse">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-900/80 text-gray-600 dark:text-gray-300">
              <th className="px-2 py-1.5 font-medium w-14">Photo</th>
              <th className="px-2 py-1.5 font-medium">ID</th>
              <th className="px-2 py-1.5 font-medium min-w-[8rem]">Name</th>
              <th className="px-2 py-1.5 font-medium">Price</th>
              <th className="px-2 py-1.5 font-medium hidden sm:table-cell">Category</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p, idx) => {
              const id = p.id != null ? String(p.id) : `—${idx}`;
              const name = p.name != null ? String(p.name) : "—";
              const img = p.image_url != null ? String(p.image_url).trim() : "";
              return (
                <tr
                  key={`${id}-${idx}`}
                  className="border-t border-gray-100 dark:border-gray-700 align-middle"
                >
                  <td className="px-2 py-1.5">
                    {img ? (
                      <a href={img} target="_blank" rel="noreferrer" className="block">
                        <img
                          src={img}
                          alt=""
                          loading="lazy"
                          className="w-11 h-11 object-cover rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-900"
                        />
                      </a>
                    ) : (
                      <div className="w-11 h-11 rounded border border-dashed border-gray-300 dark:border-gray-600 flex items-center justify-center text-gray-400 text-[10px]">
                        —
                      </div>
                    )}
                  </td>
                  <td className="px-2 py-1.5 font-mono text-[10px]">{id}</td>
                  <td className="px-2 py-1.5">
                    <span className="line-clamp-2" title={name}>
                      {name}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 whitespace-nowrap">{formatPrice(p.price_cents)}</td>
                  <td className="px-2 py-1.5 hidden sm:table-cell max-w-[10rem]">
                    <TagList tags={p.tags} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ProductDetailToolTable({ product }: { product: ProductRow }) {
  return (
    <ProductListToolTable products={[product]} metaHint="Product detail" />
  );
}
