# Example API responses (mock data for the frontend)

Real responses from the backend for one demo field, so the frontend can build without running it.
They follow [`../api-contract.yaml`](../api-contract.yaml); `tests/test_examples.py` fails CI if they stop matching.

| File | Endpoint |
|---|---|
| `conditions_alajuela.json` | `GET /conditions?lat=10.0&lon=-84.2` |
| `recommendation_request_alajuela.json` | body sent to `POST /recommendations` |
| `recommendation_alajuela.json` | `POST /recommendations` response: top 3 rotations + the farmer's current one (maize → maize) |
| `crops.json` | `GET /crops` |

**Demo field:** Alajuela, Costa Rica (lat 10.0, lon −84.2).
**Data behind it:** climate is real NASA POWER monthly normals (fixture `tests/fixtures/nasa_power/climatology_alajuela.json`).
Soil is still mock, and crop ranges are approximate. The responses say so in `data_sources` and `data_gaps`.

## Regenerate
After a contract, scoring or `mvp.yaml` change:

```bash
cd backend && .venv/bin/python -m scripts.make_examples
```

It runs the real app in `cached` mode on top of the fixture, so it never calls the network.
