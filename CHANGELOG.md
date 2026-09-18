# Changelog

## [0.4.0](https://github.com/HackermanMe/flashapi/compare/v0.3.0...v0.4.0) (2026-09-18)


### Features

* add field selection (?fields=id,name,price) ([4c07e45](https://github.com/HackermanMe/flashapi/commit/4c07e4536ab442f3a984ec8108154ef47f361098))
* add idempotency keys, cache layer, and currentUserField auto-injection ([141ae08](https://github.com/HackermanMe/flashapi/commit/141ae084afd4d605540a0cead5c4aac9cd6c41f6))
* add interactive CRUD dashboard with HTMX and real-time WebSocket ([1b1b4a5](https://github.com/HackermanMe/flashapi/commit/1b1b4a5c9924db5858119a69fb9c2585c687fe6d))


### Bug Fixes

* **django:** convert URL path params to OpenAPI format in discover_django_views ([78e5675](https://github.com/HackermanMe/flashapi/commit/78e5675b8fafe0a87a7711f30f9b3db26bfd9dd6))
* simplify nested if statement for ruff linter ([73fb95b](https://github.com/HackermanMe/flashapi/commit/73fb95bdd7282141081a85d0f44d6d8c4478967e))
* sync release-please manifest and README version to 0.3.0 ([1538199](https://github.com/HackermanMe/flashapi/commit/1538199c6f9edc3fb4be9a17d9b69c67838a90bb))

## [0.3.0](https://github.com/HackermanMe/flashapi/compare/v0.2.0...v0.3.0) (2026-08-08)


### Features

* add production health check endpoints (/health and /ready) ([cc4e881](https://github.com/HackermanMe/flashapi/commit/cc4e881f09055fa990bb054298ebc8c1f55af7af))


### Bug Fixes

* corriger les gradients et les couleurs dans les fichiers SVG du logo ([50aadaf](https://github.com/HackermanMe/flashapi/commit/50aadaff44919e5666621cc3f645dd34c1364a64))


### Documentation

* add release-please version marker in README ([515aeb8](https://github.com/HackermanMe/flashapi/commit/515aeb83c2f021bebac25d9690c4726003769746))

## 0.1.0 (2026-07-09)

Initial release.

### Features
- Auto-generate REST API + CRUD from model definitions
- Framework support: FastAPI, Django, Flask
- Model support: Django ORM, SQLAlchemy, Pydantic, dataclass
- Pagination, filtering, sorting, full-text search
- Relation detection: nested routes and `?expand=`
- OpenAPI 3.1.0 schema generation + Swagger UI
- French + English pluralization
- `Model()` wrapper: readonly, exclude, only, plural
- `@api_doc()` decorator for custom routes in Swagger
- `engine=` parameter for SQLAlchemy database reuse
- Custom response formatter support

### Security
- SQL identifier validation (prevents injection via table/column names)
- Session rollback on SQLAlchemy errors
- Input validation for pagination parameters
- CSRF exempt on Django API views (documented behavior)
