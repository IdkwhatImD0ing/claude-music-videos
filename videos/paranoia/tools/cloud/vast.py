#!/usr/bin/env python3
"""Small Vast.ai helper (the account rules are in the repo CLAUDE.md: spend only existing credit, never add funds,
destroy every instance when its job is done). Reads VAST_API_KEY from the environment.

  python tools/cloud/vast.py credit
  python tools/cloud/vast.py offers                      # verified US RTX 5090s, reliability >= 0.98, cheapest first
  python tools/cloud/vast.py rent <offer id> <label>     # vastai/base-image, ssh_direct, NVIDIA EGL/Vulkan libs, $VAST_DISK GB (60)
  python tools/cloud/vast.py list                        # this account's instances: id, label, status, ssh command
  python tools/cloud/vast.py destroy <instance id> [...]
"""
import json
import os
import sys
import urllib.parse
import urllib.request

API = 'https://console.vast.ai/api/v0'


def call(method, path, body=None, auth=True):
    req = urllib.request.Request(API + path, method=method)
    if auth:
        req.add_header('Authorization', 'Bearer ' + os.environ['VAST_API_KEY'])
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, data, timeout=60) as r:
        return json.load(r)


def offers():
    q = {"gpu_name": {"eq": "RTX 5090"}, "num_gpus": {"eq": 1}, "rentable": {"eq": True}, "rented": {"eq": False},
         "type": "on-demand", "verified": {"eq": True}}
    d = call('GET', '/bundles/?q=' + urllib.parse.quote(json.dumps(q)), auth=False)
    good = [o for o in d.get('offers', []) if o.get('reliability2', 0) >= 0.98
            and (o.get('geolocation') or '').endswith('US')]
    return sorted(good, key=lambda o: o['dph_total'])


def ssh_of(i):
    port = ((i.get('ports') or {}).get('22/tcp') or [{}])[0].get('HostPort')
    return f"ssh -p {port} root@{i.get('public_ipaddr')}" if port else ''


def main():
    cmd = sys.argv[1]
    if cmd == 'credit':
        u = call('GET', '/users/current/')
        print(f"credit ${u.get('credit', 0):.2f}")
    elif cmd == 'offers':
        for o in offers():
            print(o['id'], f"${o['dph_total']:.3f}/h", o.get('cpu_name'), o.get('geolocation'),
                  f"rel {o.get('reliability2', 0):.3f}", f"up {o.get('inet_up', 0):.0f} Mb/s")
    elif cmd == 'rent':
        oid, label = sys.argv[2], sys.argv[3]
        r = call('PUT', f'/asks/{oid}/', {"client_id": "me", "image": "vastai/base-image:@vastai-automatic-tag",
                                          "disk": int(os.environ.get("VAST_DISK", "60")), "runtype": "ssh_direct", "label": label,
                                          "env": "-e NVIDIA_DRIVER_CAPABILITIES=all"})
        iid = r.get('new_contract')
        print('rented' if r.get('success') else 'failed', iid)   # (the response also holds an instance key: not printed)
        if iid:
            try:
                call('PUT', f'/instances/{iid}/', {"label": label})
            except Exception as e:  # the label is a convenience
                print('label not set:', e)
    elif cmd == 'list':
        for i in call('GET', '/instances/').get('instances', []):
            print(i['id'], i.get('label'), i.get('actual_status'), i.get('cpu_name'), f"${i.get('dph_total', 0):.3f}/h",
                  ssh_of(i))
    elif cmd == 'destroy':
        for iid in sys.argv[2:]:
            print(iid, call('DELETE', f'/instances/{iid}/'))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
