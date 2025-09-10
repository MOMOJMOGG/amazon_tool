# Tools Directory

This directory contains utility scripts and tools for the Amazon Product Monitoring Tool project.

## 📁 Directory Structure

```
tools/
├── database/           # Database management utilities
│   ├── test_connection.py    # Test database connectivity
│   └── initialize.py         # Initialize database schemas and tables
├── testing/            # Testing and debugging utilities  
│   ├── debug_celery.py       # Debug Celery task execution
│   ├── get_latest_job.py     # Get recent job information
│   └── run_api_tests.py      # Automated M2 API test suite
└── README.md           # This file
```

## 🗄️ Database Tools

### `database/test_connection.py`
Test database connectivity and basic functionality.

```bash
python tools/database/test_connection.py
```

**Purpose:**
- Verify DATABASE_URL configuration
- Test PostgreSQL connection
- Check schema availability (staging, core, mart)
- Diagnose connection issues

### `database/initialize.py` 
Initialize database with required schemas and tables.

```bash
python tools/database/initialize.py
```

**Purpose:**
- Create database schemas (staging, core, mart)
- Create all tables via SQLAlchemy models
- Set up indexes and relationships
- Required before first app startup

## 🧪 Testing Tools

### `testing/debug_celery.py`
Debug Celery task execution and job flow.

```bash
python tools/testing/debug_celery.py
```

**Purpose:**
- Test database connectivity in Celery workers
- Verify job creation and retrieval
- Debug ETL pipeline task execution
- Diagnose Celery/Redis issues

### `testing/get_latest_job.py`
Get information about recent job executions.

```bash
python tools/testing/get_latest_job.py
```

**Purpose:**
- Find recent job IDs for API testing
- Display job execution details and timing
- Help with manual API endpoint testing

### `testing/run_api_tests.py`
Automated M2 API test suite.

```bash
python tools/testing/run_api_tests.py
```

**Purpose:**
- Run all M2 manual API tests automatically
- Comprehensive ETL pipeline verification
- Generate pass/fail report
- Validate M2 acceptance criteria

## 🚀 Usage Workflows

### Initial Project Setup
1. `python tools/database/test_connection.py` - Verify database access
2. `python tools/database/initialize.py` - Set up database structure
3. Start FastAPI and Celery services
4. `python tools/testing/run_api_tests.py` - Verify everything works

### Development Debugging
1. `python tools/testing/debug_celery.py` - Debug task execution issues
2. `python tools/testing/get_latest_job.py` - Find job IDs for testing
3. Manual API testing with curl/Postman using job IDs

### Continuous Verification
- Run `python tools/testing/run_api_tests.py` after changes
- Use for CI/CD pipeline validation
- Verify deployment success

## 📋 Prerequisites

All tools require:
- Virtual environment activated (`pyenv activate amazon`)
- Dependencies installed (`pip install -r requirements.txt`) 
- Environment variables set (`.env` file with DATABASE_URL, etc.)

Additional requirements:
- **Database tools**: PostgreSQL accessible via DATABASE_URL
- **Testing tools**: FastAPI server running, Celery worker running, Redis running

## 🔧 Troubleshooting

### "Database not initialized" errors
```bash
python tools/database/initialize.py
```

### "Connection refused" errors  
- Check if services are running (FastAPI, Redis, PostgreSQL)
- Verify environment variables in `.env`

### Celery task failures
```bash
python tools/testing/debug_celery.py
```

### API endpoint issues
```bash
python tools/testing/run_api_tests.py
```

## 📝 Adding New Tools

When adding new utility scripts:

1. **Choose appropriate directory**:
   - `database/` - Database management, migrations, admin tasks
   - `testing/` - Test utilities, debugging, validation tools

2. **Follow naming conventions**:
   - Use descriptive snake_case names
   - Include `.py` extension

3. **Include proper documentation**:
   - Docstring with purpose and usage
   - Command-line help/examples
   - Prerequisites and error handling

4. **Update this README** with new tool information

---

*These tools support the M2 Daily ETL Pipeline implementation and testing workflows.*