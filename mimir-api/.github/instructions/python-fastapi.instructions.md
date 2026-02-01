---
applyTo: "**/*.py"
---

# Python & FastAPI – Language-Specific Guidelines

Apply the [general coding guidelines](./general-coding.instructions.md) to all code.

## Python-Specific Guidelines

- Follow the PEP 8 style guide for Python.
- Always prioritize readability and clarity.
- Write clear and concise comments for each function.
- Ensure functions have descriptive names and include type hints.
- Maintain proper indentation (use 4 spaces for each level of indentation).

## FastAPI-Specific Guidelines

### API Design & Structure
- Use **router-based organization**: group related endpoints in separate router files (`/routers/users.py`, `/routers/images.py`).
- Prefix all API routes with `/api/v1/` for versioning.
- Use **kebab-case** for URL paths: `/api/v1/user-profiles`, not `/api/v1/userProfiles`.
- Keep route handlers thin—delegate business logic to service layers.

### Request/Response Models
- Always use **Pydantic models** for request/response schemas, never raw dicts.
- Separate models by purpose: `UserCreate`, `UserUpdate`, `UserResponse`.
- Use `Field()` for validation, descriptions, and examples:
  ```python
  class UserCreate(BaseModel):
      email: str = Field(..., description="User email address", example="user@example.com")
      age: int = Field(ge=18, le=120, description="User age in years")
  ```
- Include response models in route decorators: `@router.get("/users", response_model=list[UserResponse])`.

### Async Patterns & Dependencies
- Use `async def` for all route handlers and service functions that perform I/O.
- Leverage **dependency injection** for shared resources (database, auth, config):
  ```python
  async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
      # validation logic
      return user
  ```
- Create reusable dependencies in `/dependencies/` folder.
- Use `Depends()` for database sessions, authentication, and configuration.

### Error Handling
- Use **HTTPException** for client errors (4xx) with descriptive messages:
  ```python
  raise HTTPException(status_code=404, detail="User not found")
  ```
- Create custom exception handlers for consistent error responses.
- Always include correlation IDs in error responses for debugging.
- Use proper HTTP status codes: 200, 201, 204, 400, 401, 403, 404, 422, 500.

### Validation & Security
- Use Pydantic validators for complex business rules.
- Always validate file uploads (size, type, content).
- Implement **rate limiting** on public endpoints.
- Use **CORS middleware** with explicit allowed origins (never use `allow_origins=["*"]` in production).
- Sanitize all user inputs and validate against injection attacks.

### Database Integration
- Use **async database drivers** (asyncpg, aiomysql) with connection pooling.
- Implement proper database session management with dependency injection.
- Use database transactions for multi-step operations.
- Never commit raw SQL strings—use parameterized queries or ORM.

### Testing FastAPI
- Use **pytest-asyncio** for async test functions.
- Use `TestClient` for integration tests:
  ```python
  def test_create_user():
      response = client.post("/api/v1/users", json={"email": "test@example.com"})
      assert response.status_code == 201
  ```
- Mock external dependencies in tests using `app.dependency_overrides`.
- Test both success and error cases for each endpoint.

### Documentation & OpenAPI
- Use **docstrings** on route handlers for OpenAPI descriptions.
- Provide examples in Pydantic models for better API docs.
- Include proper **tags** for endpoint grouping in Swagger UI.
- Document expected error responses with `responses` parameter.

### Performance & Monitoring
- Use **background tasks** for non-blocking operations: `BackgroundTasks.add_task()`.
- Implement proper **logging middleware** to capture request/response details.
- Use **Prometheus metrics** or similar for monitoring endpoint performance.
- Consider **caching** for expensive read operations (Redis, in-memory).

### Configuration Management
- Use **Pydantic Settings** for environment-based configuration.
- Never hardcode secrets—use environment variables with `.env` files.
- Validate all configuration at startup, fail fast on missing required values.

> **FastAPI Copilot hints:** Suggest proper async/await usage, Pydantic models over dicts, dependency injection patterns, and structured error handling with HTTPException.

