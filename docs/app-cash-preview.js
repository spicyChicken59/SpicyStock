/* Personal arithmetic over one unchanged published order. No storage, network,
   strategy sizing, broker verification or cash reservation. Amounts are cents. */
(function (w) {
  'use strict';
  const api = w.SCStock = w.SCStock || {};
  const MAX_CENTS = BigInt(Number.MAX_SAFE_INTEGER), MAX_SHARES = 1000000;
  function cents(raw) {
    if (typeof raw !== 'string') return undefined;
    const text = raw.trim();
    if (!text) return null;
    if (!/^\d+(?:\.\d{1,2})?$/.test(text) || text.length > 20) return undefined;
    const [whole, fraction = ''] = text.split('.');
    const amount = BigInt(whole) * 100n + BigInt((fraction + '00').slice(0, 2));
    return amount <= MAX_CENTS ? Number(amount) : undefined;
  }
  function price(value) { return typeof value === 'number' && Number.isFinite(value) && value > 0 ? cents(String(value)) : undefined; }
  function calculate({ cash, fees, quantity = '', order } = {}) {
    const fail = (state, reason) => ({ state, reason, quantity: null });
    const limit = price(order && order.limit_price), stop = price(order && order.then && order.then.stop_price), trigger = price(order && order.stop_price);
    const published = order && order.quantity;
    if (!order || order.action !== 'buy' || order.order_type !== 'stop_limit' || order.time_in_force !== 'day' || order.conditional !== 'one_triggers_the_other' ||
        !order.then || order.then.action !== 'sell' || order.then.order_type !== 'stop' || order.then.time_in_force !== 'gtc' || order.then.quantity !== published ||
        !Number.isInteger(published) || published < 1 || published > MAX_SHARES || !Number.isSafeInteger(limit) || !Number.isSafeInteger(stop) || !Number.isSafeInteger(trigger) || stop >= trigger || trigger > limit)
      return fail('invalid_order', 'This published order cannot support a whole-share cash preview.');
    const cashCents = cents(cash), feeCents = cents(fees);
    if (cashCents === null) return fail('needs_cash', 'Enter available settled cash from your broker to calculate a quantity.');
    if (cashCents === undefined) return fail('invalid_cash', 'Settled cash must be a non-negative dollar amount with at most two decimals.');
    if (feeCents === null) return fail('needs_fees', 'Enter an explicit fees buffer; enter 0 only if that is your intended estimate.');
    if (feeCents === undefined) return fail('invalid_fees', 'The fees buffer must be a non-negative dollar amount with at most two decimals.');
    const affordable = feeCents > cashCents ? 0 : Number(BigInt(cashCents - feeCents) / BigInt(limit));
    const maximum = Math.min(published, affordable);
    if (!maximum) return { ...fail('unfunded', 'No whole share fits the entered cash after the fees buffer.'), maximum: 0 };
    if (typeof quantity !== 'string') return fail('invalid_quantity', 'Enter a whole-share quantity or leave it blank for the affordable maximum.');
    const entered = quantity.trim(), chosen = entered === '' ? maximum : /^\d+$/.test(entered) && entered.length <= 7 ? Number(entered) : NaN;
    if (!Number.isInteger(chosen) || chosen < 1 || chosen > maximum) return { ...fail('invalid_quantity', 'Choose 1–' + maximum + ' whole shares, or leave quantity blank for that maximum.'), maximum };
    const principal = Number(BigInt(chosen) * BigInt(limit)), risk = Number(BigInt(chosen) * BigInt(limit - stop));
    const commitment = principal + feeCents;
    return { state: 'calculated', reason: 'Calculation for broker review; cash and fees are entered by you, not verified.', quantity: chosen,
      maximum, publishedQuantity: published, triggerCents: trigger, limitCents: limit, stopCents: stop,
      principalCents: principal, feeCents, commitmentCents: commitment, riskCents: risk, remainingCents: cashCents - commitment };
  }
  api.cashPreview = { cents, calculate };
})(window);
