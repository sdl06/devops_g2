// All Staff UI calls to the backend services live here.
//
// Locally, the base URLs are empty: requests go to the Vite dev server, which
// forwards them to the services (see the proxy in vite.config.js).
// For Azure, set VITE_BILL_URL and VITE_SPLIT_URL at build time to the
// services' public addresses. Nothing else in the app needs to change.

const BILL_URL = import.meta.env.VITE_BILL_URL || '';
const SPLIT_URL = import.meta.env.VITE_SPLIT_URL || '';
const STAFF_TOKEN = import.meta.env.VITE_STAFF_TOKEN || '';

// Send one request and return the JSON reply.
// Errors from the services look like {"error": "message"}; we throw that
// message so screens can show it. Network failures (service down) get a
// friendly message instead of a raw browser error.
async function request(base, path, { method = 'GET', body, headers = {} } = {}) {
  let response;
  try {
    response = await fetch(base + path, {
      method,
      headers: body === undefined ? headers : { 'Content-Type': 'application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    const error = new Error('The service is unreachable. Please try again in a moment.');
    error.status = 0;
    throw error;
  }

  if (response.status === 204) return null; // successful delete, no body

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(data?.error || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

const bill = (path, options) => request(BILL_URL, path, options);
const split = (path, options) => request(SPLIT_URL, path, options);

// ---------- Tables ----------
export const getTables = () => bill('/tables');
export const createTable = (name) => bill('/tables', { method: 'POST', body: { name } });
export const renameTable = (id, name) => bill(`/tables/${id}`, { method: 'PUT', body: { name } });
export const deleteTable = (id) => bill(`/tables/${id}`, { method: 'DELETE' });

// ---------- Dishes (menu) ----------
// dish = { name, price_cents }
export const getDishes = () => bill('/dishes');
export const createDish = (dish) => bill('/dishes', { method: 'POST', body: dish });
export const updateDish = (id, dish) => bill(`/dishes/${id}`, { method: 'PUT', body: dish });
export const deleteDish = (id) => bill(`/dishes/${id}`, { method: 'DELETE' });
// recipe = [{ ingredient_id, amount }]
export const setRecipe = (id, recipe) =>
  bill(`/dishes/${id}/ingredients`, { method: 'PUT', body: recipe });

// ---------- Ingredients (stock) ----------
// ingredient = { name, unit, stock, surplus_level }
export const getIngredients = () => bill('/ingredients');
export const createIngredient = (ingredient) =>
  bill('/ingredients', { method: 'POST', body: ingredient });
export const updateIngredient = (id, ingredient) =>
  bill(`/ingredients/${id}`, { method: 'PUT', body: ingredient });
export const deleteIngredient = (id) => bill(`/ingredients/${id}`, { method: 'DELETE' });

// ---------- Bills ----------
// filters = { status: 'open', table_id: 1 } (both optional)
export const getBills = (filters = {}) => {
  const query = new URLSearchParams(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''),
  ).toString();
  return bill(`/bills${query ? `?${query}` : ''}`);
};
export const getBill = (id) => bill(`/bills/${id}`);
export const createBill = (tableId) => bill('/bills', { method: 'POST', body: { table_id: tableId } });
export const deleteBill = (id) => bill(`/bills/${id}`, { method: 'DELETE' }); // drafts only
export const openBill = (id) => bill(`/bills/${id}/open`, { method: 'POST' });
export const closeBill = (id) => bill(`/bills/${id}/close`, { method: 'POST' });

// ---------- Bill items ----------
export const addItem = (billId, dishId, quantity) =>
  bill(`/bills/${billId}/items`, { method: 'POST', body: { dish_id: dishId, quantity } });
export const updateItem = (billId, itemId, quantity) =>
  bill(`/bills/${billId}/items/${itemId}`, { method: 'PUT', body: { quantity } });
export const deleteItem = (billId, itemId) =>
  bill(`/bills/${billId}/items/${itemId}`, { method: 'DELETE' });

// ---------- Guest menu (surplus dishes first) ----------
export const getMenu = () => bill('/menu');

// ---------- Payment progress (Split Service, staff only) ----------
// Returns { ready_to_close, needs_review, unallocated_subtotal_cents,
//           allocated_unsettled_subtotal_cents }
// TODO: agree with Sergio how the staff token is handled in production.
export const getProgress = (billId) =>
  split(`/api/bills/${billId}/progress`, {
    headers: { Authorization: `Bearer ${STAFF_TOKEN}` },
  });

// ---------- Helpers ----------
// 1250 -> "€12.50"
export const formatMoney = (cents) =>
  new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(
    (Number(cents) || 0) / 100,
  );
