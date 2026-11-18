import json

class EtsStream:
    def __init__(self):
        self.states = {}

    def on_ws(self, ws):
        ws.on("framereceived", self._on_frame)

    def _on_frame(self, payload):
        try:
            data = json.loads(payload)
        except Exception:
            return
        self._walk(data)

    def _walk(self, obj):
        if isinstance(obj, dict):
            gps = obj.get("gps_code") or obj.get("gpsCode") or obj.get("gps")
            ts = obj.get("timestamp") or obj.get("ts") or obj.get("time")
            if gps and ts:
                try:
                    self.states[str(gps)] = {"timestamp": int(ts)}
                except Exception:
                    pass
            for v in obj.values():
                self._walk(v)
        elif isinstance(obj, list):
            for v in obj:
                self._walk(v)
