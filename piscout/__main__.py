import argparse
import ipaddress
import json
import sys


def scan_cli(argv):
    """`python -m piscout scan`: print the devices found on the LAN. Needs no GUI and works on macOS and Linux."""
    p = argparse.ArgumentParser(prog="piscout scan", description="Scan the local network for Raspberry Pis.")
    p.add_argument("--network", help="network to scan, for example 192.168.1.0/24 (default: the /24 of this machine)")
    p.add_argument("--all", action="store_true", help="list every device, not only Raspberry Pis")
    p.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = p.parse_args(argv)

    from . import scanner  # imported here so that `piscout scan` needs only the standard library

    try:
        network = ipaddress.ip_network(args.network, strict=False) if args.network else None
    except ValueError as e:
        p.error(str(e))
    result = scanner.scan(network)
    devices = [d for d in result["devices"] if args.all or d["is_pi"]]

    if args.json:
        print(json.dumps({"network": result["network"], "devices": devices}, ensure_ascii=False, indent=2))
        return 0
    print(f"{result['network']}: {len(result['devices'])} devices, "
          f"{sum(d['is_pi'] for d in result['devices'])} Raspberry Pi")
    if devices:
        print(f"{'IP':<16}{'MAC':<19}{'SSH':<6}{'Pi':<4}Hostname")
        for d in devices:
            print(f"{d['ip']:<16}{d['mac']:<19}{'open' if d['ssh_open'] else '-':<6}"
                  f"{'yes' if d['is_pi'] else '-':<4}{d['hostname']}")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        sys.exit(scan_cli(sys.argv[2:]))
    import uvicorn

    p = argparse.ArgumentParser(prog="piscout")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    uvicorn.run("piscout.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
