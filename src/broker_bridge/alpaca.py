"""Small fixed-origin Alpaca OAuth/Trading adapter with no POST retries."""
import httpx
from uuid import UUID


class BrokerError(Exception):
    def __init__(self, code="broker_unavailable", status=502, uncertain=False):
        self.code, self.status, self.uncertain = code, status, uncertain
        super().__init__(code)


class Alpaca:
    ROOTS = {"paper": "https://paper-api.alpaca.markets", "live": "https://api.alpaca.markets"}
    DATA_ROOT = "https://data.alpaca.markets"

    def __init__(self, config, transport=None):
        self.config = config
        # Do not follow redirects with Authorization or inherit an operator's HTTP proxy.
        self.client = httpx.Client(timeout=httpx.Timeout(8, connect=3), follow_redirects=False,
                                   transport=transport, trust_env=False)

    def request(self, method, root, path, token=None, params=None, json=None, data=None):
        if root not in {*self.ROOTS.values(), self.DATA_ROOT} or not path.startswith("/") or path.startswith("//"):
            raise ValueError("Only fixed broker API origins are supported")
        try:
            response = self.client.request(method, root + path, params=params, json=json, data=data,
                                           headers={"Authorization": "Bearer " + token} if token else {})
        except httpx.RequestError:
            raise BrokerError(uncertain=method != "GET") from None
        if response.status_code == 404:
            raise BrokerError("broker_not_found", 404)
        if response.status_code in (401, 403):
            raise BrokerError("broker_access_denied", 403)
        if not 200 <= response.status_code < 300:
            raise BrokerError("broker_rejected" if response.status_code < 500 else "broker_unavailable",
                              422 if response.status_code < 500 else 502,
                              uncertain=method != "GET" and (response.status_code >= 500 or response.status_code in (409, 429)))
        if len(response.content) > 2_000_000:
            raise BrokerError("broker_response_invalid", uncertain=method != "GET")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise BrokerError("broker_response_invalid", uncertain=method != "GET") from None

    def exchange(self, code):
        data = self.request("POST", self.ROOTS["live"], "/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "client_id": self.config.client_id, "client_secret": self.config.client_secret,
            "redirect_uri": self.config.redirect_uri,
        })
        if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"]:
            raise BrokerError("broker_response_invalid")
        if not {"trading", "data"}.issubset(set(data.get("scope", "").split())):
            raise BrokerError("broker_scope_missing", 403)
        return data["access_token"]

    def get(self, session, path, params=None):
        return self.request("GET", self.ROOTS[session["mode"]], path, session["token"], params=params)

    def account(self, session):
        return self.get(session, "/v2/account")

    def clock(self, session):
        return self.get(session, "/v2/clock")

    def calendar(self, session, start, end):
        return self.get(session, "/v2/calendar", {"start": start, "end": end})

    def positions(self, session):
        return self.get(session, "/v2/positions")

    def orders(self, session):
        return self.get(session, "/v2/orders", {"status": "open", "limit": 500, "nested": "true"})

    def asset(self, session, symbol):
        return self.get(session, "/v2/assets/" + symbol)

    def quote(self, session, symbol):
        feed = "sip" if session["mode"] == "live" else "iex"
        data = self.request("GET", self.DATA_ROOT, "/v2/stocks/" + symbol + "/quotes/latest",
                            session["token"], params={"feed": feed})
        return data, feed

    def fill_page(self, session, token=None):
        params = {"direction": "desc", "page_size": 100}
        if token:
            params["page_token"] = token
        return self.get(session, "/v2/account/activities/FILL", params)

    def order_by_client_id(self, session, cid):
        try:
            raw = self.get(session, "/v2/orders:by_client_order_id", {"client_order_id": cid})
            if isinstance(raw, dict) and not raw.get("legs") and raw.get("order_class") == "oto":
                try:
                    order_id = str(UUID(raw["id"]))
                except (ValueError, KeyError, TypeError):
                    raise BrokerError("broker_response_invalid") from None
                raw = self.get(session, "/v2/orders/" + order_id, {"nested": "true"})
            return raw
        except BrokerError as exc:
            if exc.status == 404:
                return None
            raise

    def submit(self, session, order):
        return self.request("POST", self.ROOTS[session["mode"]], "/v2/orders", session["token"], json=order)
