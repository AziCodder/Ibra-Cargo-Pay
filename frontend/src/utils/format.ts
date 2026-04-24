const CURRENCY_SYMBOL: Record<string, string> = {
  CNY: '¥',
  USD: '$',
  RUB: '₽',
};

/** Форматирование числа как валюты с символом */
export function fmt(value: string | number, currency: string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  const formatted = num.toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${CURRENCY_SYMBOL[currency] ?? currency}${formatted}`;
}
