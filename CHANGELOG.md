# Changelog

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
