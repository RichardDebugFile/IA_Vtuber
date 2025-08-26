import requests, sys

def check(url: str) -> bool:
    try:
        r = requests.get(url, timeout=3)
        return r.ok
    except Exception:
        return False

if __name__ == "__main__":
    fish = check("http://127.0.0.1:9080/")
    wok = check("http://127.0.0.1:18888/")
    print("Fish:", fish, "w-okada:", wok)
    sys.exit(0 if (fish and wok) else 1)
