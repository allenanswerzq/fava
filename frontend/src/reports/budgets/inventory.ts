import type { BudgetInventory } from "../../api/validators.ts";

export const subtract = (
  left: BudgetInventory,
  right: BudgetInventory,
): BudgetInventory =>
  Object.fromEntries(
    [...new Set([...Object.keys(left), ...Object.keys(right)])].map(
      (currency) => [currency, (left[currency] ?? 0) - (right[currency] ?? 0)],
    ),
  );

export const ratio = (
  budget: BudgetInventory,
  actual: BudgetInventory,
): number | null => {
  const currencies = [
    ...new Set([...Object.keys(budget), ...Object.keys(actual)]),
  ];
  if (currencies.length !== 1) {
    return null;
  }
  const currency = currencies[0];
  if (currency == null) {
    return null;
  }
  const limit = budget[currency];
  if (limit == null || limit === 0) {
    return null;
  }
  return (actual[currency] ?? 0) / limit;
};

export const usage = (
  budget: BudgetInventory,
  actual: BudgetInventory,
): string => {
  const value = ratio(budget, actual);
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
};
