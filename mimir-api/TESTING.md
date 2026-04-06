# Testing Infrastructure

This document describes the comprehensive testing infrastructure for the Mimir API, implemented as part of Phase 6 of the refactoring process.

## Overview

The testing infrastructure provides:
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test API endpoints and service interactions
- **Fixtures**: Reusable test data and setup
- **Mocking**: Mock external dependencies for reliable testing
- **Coverage Reporting**: Track test coverage across the codebase

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests for services
│   ├── test_channel_discovery_service.py
│   ├── test_websocket_service.py
│   ├── test_distribution_service.py
│   ├── test_caching_service.py
│   └── test_content_service.py
├── integration/             # Integration tests for APIs
│   ├── test_api_endpoints.py
│   └── test_websocket_integration.py
└── fixtures/                # Test data and utilities
    └── (generated test data)
```

## Configuration Files

### pytest.ini
- Test discovery and execution configuration
- Markers for categorizing tests
- Async test support
- Warning filters

### requirements-test.txt
- Testing dependencies
- Coverage tools
- Async testing support

## Test Categories (Markers)

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests for API endpoints
- `@pytest.mark.websocket` - WebSocket-specific tests
- `@pytest.mark.redis` - Redis-dependent tests
- `@pytest.mark.database` - Database tests
- `@pytest.mark.channels` - Channel-related tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - Slow-running tests

## Key Fixtures

### Database Fixtures
- `test_db_engine` - Test database engine
- `test_db_session` - Database session for tests
- `db_with_sample_data` - Pre-populated database

### Application Fixtures
- `test_settings` - Test configuration
- `app_with_test_db` - FastAPI app with test database
- `client` - HTTP test client

### Mock Data Fixtures
- `sample_channel_data` - Sample channel configuration
- `sample_scene_data` - Sample scene data
- `sample_overlay_data` - Sample overlay configuration
- `sample_display_data` - Sample display client data

### Utility Fixtures
- `mock_channel_directory` - Mock channel filesystem
- `mock_websocket` - Mock WebSocket connection
- `test_channels_dir` - Temporary channels directory

## Running Tests

### Using the Test Runner Script

The `run_tests.py` script provides convenient test execution:

```bash
# Install test dependencies
python run_tests.py --install-deps

# Run all tests
python run_tests.py --all

# Run unit tests only
python run_tests.py --unit

# Run integration tests only
python run_tests.py --integration

# Run with coverage
python run_tests.py --unit --coverage

# Run specific test file
python run_tests.py --test tests/unit/test_channel_discovery_service.py

# Run tests by marker
python run_tests.py --marker unit

# Verbose output
python run_tests.py --unit --verbose

# Check test environment
python run_tests.py --check
```

### Using pytest Directly

```bash
# Install dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m websocket

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_channel_discovery_service.py

# Run specific test function
pytest tests/unit/test_channel_discovery_service.py::TestChannelDiscoveryService::test_compute_sri_hash

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Test Coverage

Coverage reporting tracks:
- Line coverage across all modules
- Branch coverage for conditional logic
- Missing coverage identification
- HTML reports for detailed analysis

Generate coverage reports:
```bash
pytest --cov=app --cov-report=html --cov-report=term
```

View HTML coverage report:
```bash
# Open htmlcov/index.html in browser
```

## Unit Test Examples

### Service Testing Pattern
```python
@pytest.mark.unit
class TestChannelDiscoveryService:
    @pytest.fixture
    def channel_service(self, mock_settings):
        return ChannelDiscoveryService(settings=mock_settings)
    
    def test_compute_sri_hash(self, channel_service):
        content = "test content"
        result = channel_service.compute_sri_hash(content)
        assert result.startswith("sha384-")
```

### Async Service Testing
```python
@pytest.mark.asyncio
async def test_websocket_connection(self, websocket_service, mock_websocket):
    await websocket_service.connect_display_client(
        websocket=mock_websocket,
        display_id="test-display",
        display_client=mock_display_client,
        db=mock_db_session
    )
    mock_websocket.accept.assert_called_once()
```

## Integration Test Examples

### API Endpoint Testing
```python
@pytest.mark.integration
@pytest.mark.api
def test_get_channels(self, client):
    response = client.get("/api/v1/channels")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
```

### Database Integration
```python
@pytest.mark.integration
@pytest.mark.database
def test_channel_crud(self, client, sample_channel_data):
    # Create
    response = client.post("/api/v1/channels", json=sample_channel_data)
    assert response.status_code == 201
    
    # Read
    response = client.get(f"/api/v1/channels/{sample_channel_data['id']}")
    assert response.status_code == 200
```

## Mocking Strategies

### External Dependencies
```python
@patch('app.services.channel_discovery.Path.exists')
def test_with_mocked_filesystem(self, mock_exists):
    mock_exists.return_value = True
    # Test logic
```

### Async Operations
```python
@pytest.fixture
def mock_websocket():
    websocket = Mock()
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    return websocket
```

### Database Operations
```python
@pytest.fixture
def mock_db_session():
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    return session
```

## Test Data Management

### Temporary Files
```python
@pytest.fixture
def test_channels_dir():
    temp_dir = tempfile.mkdtemp(prefix="test_channels_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)
```

### Sample Data
```python
@pytest.fixture
def sample_channel_data():
    return {
        "id": "test-channel",
        "name": "Test Channel",
        "version": "1.0.0",
        "schemaVersion": "2.1",
        # ... more data
    }
```

## Continuous Integration

### GitHub Actions Integration
```yaml
- name: Run Tests
  run: |
    pip install -r requirements-test.txt
    python run_tests.py --all --coverage
```

### Pre-commit Hooks
```yaml
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: python run_tests.py --unit
      language: system
      pass_filenames: false
```

## Best Practices

### Test Organization
- One test class per service/module
- Descriptive test method names
- Group related tests in classes
- Use appropriate markers

### Test Data
- Use fixtures for reusable data
- Create minimal test data
- Clean up temporary files
- Isolate test data between tests

### Assertions
- Use specific assertions
- Test both positive and negative cases
- Verify side effects
- Check error conditions

### Mocking
- Mock external dependencies
- Don't mock what you're testing
- Use specific mock assertions
- Verify mock calls

### Performance
- Keep tests fast
- Use markers for slow tests
- Parallelize when possible
- Clean up resources

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Database Issues**
```bash
# Clean test database
rm -f test.db
```

**Async Test Issues**
```python
# Ensure proper async test setup
@pytest.mark.asyncio
async def test_async_function():
    # Test async code
```

**Fixture Scope Issues**
```python
# Use appropriate fixture scope
@pytest.fixture(scope="function")  # Fresh for each test
@pytest.fixture(scope="session")   # Shared across session
```

### Debug Mode
```bash
# Run tests with debug output
pytest --capture=no --verbose

# Run single test with pdb
pytest --pdb tests/unit/test_channel_discovery_service.py::test_specific_function
```

## Test Metrics

The testing infrastructure tracks:
- **Test Count**: Total number of tests
- **Coverage Percentage**: Code coverage metrics
- **Execution Time**: Test performance
- **Success Rate**: Pass/fail ratios
- **Flaky Tests**: Tests with inconsistent results

## Future Enhancements

Planned improvements:
- **Property-based testing** with Hypothesis
- **Performance testing** with pytest-benchmark
- **API contract testing** with Pact
- **Load testing** integration
- **Mutation testing** for test quality
- **Visual regression testing** for UI components

## Conclusion

This testing infrastructure provides:
✅ **Comprehensive Coverage** - Unit and integration tests  
✅ **Easy Execution** - Simple test runner script  
✅ **Reliable Fixtures** - Reusable test data and setup  
✅ **Flexible Configuration** - Multiple test execution modes  
✅ **Quality Metrics** - Coverage and performance tracking  

The testing infrastructure ensures code quality, prevents regressions, and supports confident refactoring and feature development.
