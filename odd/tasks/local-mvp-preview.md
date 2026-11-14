# Local MVP preview

## Objective
Provide a lightweight, clearly labeled interactive localhost preview that can be updated after main-branch merges without replacing the team frontend.

## Scope and constraints
Separate preview from issues #14 and #43; preserve existing work. No invented agronomic data, live API calls, or silent external quota consumption. Use existing imagery and fixture data where appropriate. English artifacts.

## Tasks
- [x] T1 — Implement and verify the local interactive preview and update workflow. Route: delegated; multi-file implementation. Work-unit commit `acfc11e`.

## Acceptance and checks
- Local server HTTP 200 at 127.0.0.1:8765; serves only allowlisted content.
- Python HTTP test passed; Node model tests and JS syntax passed; git diff --check passed.
- Writer observed RED → GREEN and headless Edge interaction checks; independent verifier passed bounded HTTP/model/stub-DOM checks.
- Full manual visual accessibility, backend make check and live API integration not run; prototype uses a separate fixed Alajuela example and does not produce San Carlos recommendations.
- RDD disabled by global setting; assessment was unassessable/high due to untracked inventory; independent verification completed.
- Forecast 350 authored lines; actual 337 in code work unit. Delivery strategy ask-on-risk; no push or PR requested.

## Progress
T1 complete. Issue #69 opened. Engram mirror synchronized to this document when save succeeds.

## Next step
User can explore localhost; team may integrate independently and review pineapple data and backend integration.
