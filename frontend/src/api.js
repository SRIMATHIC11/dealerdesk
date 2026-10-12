export class ApiError extends Error {
  constructor(message, details = [], code = "", status = 0) {
    super(message);
    this.details = details;
    this.code = code;
    this.status = status;
  }
}

export async function api(path, options = {}) {
  const { body, ...rest } = options;
  let response;
  try {
    response = await fetch(`/api/${path}`, {
      ...rest,
      headers: { "Content-Type": "application/json", ...options.headers },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      "Cannot reach DealerDesk. Check the server connection and retry.",
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new ApiError(
      data.error?.message || `Request failed (${response.status}).`,
      data.error?.details || [],
      data.error?.code,
      response.status,
    );
  return data;
}

export const inr = (value) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(Number(value));
