# serve.py
# Dev host for the map: runs the API + static files without Qt, so the very
# same map/index.html can be opened in Chrome while you work on the GUI.
#
#   python serve.py            # empty shift (manually add zones to test)
#   python serve.py --live     # real collection via BotWorker (needs creds)
import argparse
import json
import os
import sys
import threading
from datetime import datetime

from store import Store
from map_server import MapServerThread
import preprocess_zones
from routes_db import RoutesDB

HERE = os.path.dirname(os.path.abspath(__file__))


def ensure_zones(store):
    if not store.zones_ready():
        print("zones.json missing - running preprocess_zones.py ...")
        preprocess_zones.build(2.0)
    db = RoutesDB()
    db.import_zones(json.load(open(os.path.join(HERE, "data", "zones.json"),
                                   encoding="utf-8"))["zones"])
    db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--day", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--live", action="store_true", help="collect from ETS")
    args = ap.parse_args()

    store = Store()
    store.day = args.day
    ensure_zones(store)

    if args.live:
        from bot_worker import BotWorker
        worker = BotWorker(target_date=args.day)

        def on_done(cars):
            store.set_cars(cars)
            print(f"ETS: {len(cars)} cars loaded")

        def on_err(msg):
            print("ETS error:", msg)

        worker.finished.connect(on_done)
        worker.error.connect(on_err)
        worker.status_msg.connect(lambda m: print("  ", m))
        worker.start()
        store._worker = worker

    srv = MapServerThread(store, port=args.port)
    srv.start()
    import time
    time.sleep(0.4)
    if srv.error:
        print(f"cannot bind 127.0.0.1:{args.port}: {srv.error}")
        return 1

    st = store.db.stats(args.day)
    print("=" * 58)
    print(f"  map      : http://127.0.0.1:{args.port}/")
    print(f"  api      : http://127.0.0.1:{args.port}/api/state")
    print(f"  day      : {args.day}  ({st['assignments']} assignments, "
          f"{st['cars']} cars, {st['zones']} zones)")
    print(f"  db       : {store.db.path}")
    print("  Ctrl+C to stop")
    print("=" * 58)

    stop = threading.Event()
    try:
        while not stop.wait(3600):
            pass
    except KeyboardInterrupt:
        print("\nstopping")
        srv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
