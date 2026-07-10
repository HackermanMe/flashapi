# Changelog

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
