// Format a monthly price given in USD cents, e.g. 2900 -> "$29/mo", 0 -> "Free".
export function formatPrice(cents: number): string {
  if (cents === 0) return "Free";
  const dollars = cents / 100;
  const display = Number.isInteger(dollars) ? dollars.toString() : dollars.toFixed(2);
  return `$${display}/mo`;
}
