// Utilities for formatting currency and large numbers

const PKR_RATE = 280;

export const formatCost = (usdAmount) => {
  if (usdAmount == null || isNaN(usdAmount)) return 'PKR 0.00';
  const pkrAmount = parseFloat(usdAmount) * PKR_RATE;
  return `PKR ${pkrAmount.toFixed(2)}`;
};

export const formatTokens = (count) => {
  if (count == null || isNaN(count)) return '0';
  return Number(count).toLocaleString('en-US');
};
