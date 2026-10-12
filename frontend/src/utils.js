export const uid = () =>
  globalThis.crypto?.randomUUID?.() ||
  `${Date.now()}-${Math.random().toString(36).slice(2)}`;
export const quantity = (value) =>
  Number.isInteger(Number(value)) && Number(value) > 0;
