# API requests for Bruno (or Postman)

`guardians-of-the-harvest.postman_collection.json` has every endpoint, ready to send:
health, crops, conditions, three recommendation requests and one request per expected 422 error.

## Use it
1. Start the API: `make dev` (from the repo root).
2. Bruno → **Import Collection** → **Postman Collection** → pick the JSON file → choose a folder to keep it in.
3. Send any request. `baseUrl` is a collection variable (`http://localhost:8000`). Change it to
   point at a teammate's machine or a deployed server.

Expected responses for the demo field (Alajuela, lat 10.0, lon −84.2) are in
[`../examples/`](../examples/README.md). In `mock` mode the numbers differ from those files, but the shape is the same.

## Keep it in sync
When an endpoint or field changes in `../api-contract.yaml`, update the matching request here too.
