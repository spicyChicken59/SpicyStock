def frames_for_replay(normalized):
    """Explicit float64 adapter; decimal strings and wire hashes remain retained.

    Invalid symbols cannot enter the replay. Partial histories may enter with
    real holes; the reference then emits unknown, matching measured denominators.
    """
    import pandas as pd
    frames, conversions = {}, []
    for symbol, record in normalized["symbols"].items():
        if record["invalid_rows"]:
            continue
        rows = record["rows"]
        if not rows:
            continue
        for row in rows:
            for field, value in row["values"].items():
                float_value = float(value)
                if not math.isfinite(float_value) or (field != "Volume" and float_value <= 0):
                    raise ValueError("decimal value cannot be represented safely in production float64")
                if Decimal.from_float(float_value) != Decimal(value):
                    conversions.append({"symbol": symbol, "session": row["session"], "field": field,
                                        "decimal": value, "float64_hex": float_value.hex()})
        frames[symbol] = pd.DataFrame([{k: float(v) for k, v in r["values"].items()} for r in rows],
                                     index=pd.to_datetime([r["timestamp"] for r in rows], utc=True))
    return frames, {"operation": "explicit production float64 projection; never claim wire precision",
                    "inexact_conversions": conversions}
