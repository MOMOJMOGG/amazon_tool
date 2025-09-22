# API Documentation Guide

> **Get offline API documentation for your Amazon Product Monitoring Tool**

## 🚀 Quick Start - Generate Offline Docs

### Method 1: Automated Generation (Recommended)

```bash
# Activate your virtual environment
source ~/.pyenv/versions/amazon/bin/activate

# Generate all documentation formats
python generate_api_docs.py
```

**Output:** Creates `api_docs/` folder with:
- `swagger.html` - Interactive Swagger UI (works offline)
- `redoc.html` - Professional ReDoc documentation  
- `api_reference.md` - Markdown documentation
- `openapi.json` - Raw OpenAPI specification

### Method 2: Manual API Access (Server Required)

```bash
# Start your API server
uvicorn src.main.app:app --reload --host 0.0.0.0 --port 8000

# Access documentation URLs:
# - Swagger UI: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc
# - OpenAPI JSON: http://localhost:8000/openapi.json
```

### Method 3: Export from Running Server

```bash
# Download OpenAPI spec from running server
curl http://localhost:8000/openapi.json > openapi.json

# Create standalone Swagger HTML
curl http://localhost:8000/docs > swagger_page.html
```

## 📋 Documentation Formats

### 🌐 Interactive Swagger UI (`swagger.html`)
- **Best for:** API testing and exploration
- **Features:** Try API calls directly in browser
- **Use case:** Development and debugging

### 📚 ReDoc Documentation (`redoc.html`)  
- **Best for:** Professional documentation sharing
- **Features:** Clean, modern design
- **Use case:** Client documentation, presentations

### 📝 Markdown Reference (`api_reference.md`)
- **Best for:** GitHub integration and text editors
- **Features:** Version control friendly
- **Use case:** Documentation websites, README files

### 🔧 Raw OpenAPI JSON (`openapi.json`)
- **Best for:** Tool integration
- **Features:** Machine-readable specification
- **Use case:** Postman import, code generation

## 🎯 API Documentation Content

Your API documentation includes:

### 📡 **REST API Endpoints**
- **Products API** - `/v1/products/*` - Product tracking and metrics
- **Competition API** - `/v1/competitions/*` - Competitive analysis  
- **ETL API** - `/v1/etl/*` - Data processing operations
- **Health & Metrics** - `/health`, `/v1/metrics` - System monitoring

### 🔍 **GraphQL API** 
- **Endpoint** - `/graphql` - Flexible query interface
- **Schema** - Available at `/graphql/schema` (development)
- **Operations** - Available at `/graphql/operations.json`

### 📊 **Data Models**
- **Product Models** - ProductResponse, ProductWithMetrics, BatchProductRequest
- **Competition Models** - CompetitionData, CompetitorLinkRequest, CompetitionReport
- **Common Models** - Error responses, pagination, filtering

## 🛠️ Advanced Usage

### Customize Documentation
Edit `generate_api_docs.py` to:
- Change styling and branding
- Add custom descriptions
- Filter endpoints
- Add authentication examples

### Integration with Tools

#### Postman Collection
```bash
# Import openapi.json into Postman for API testing
# File → Import → Upload openapi.json
```

#### Code Generation
```bash
# Generate client code using OpenAPI Generator
npm install @openapitools/openapi-generator-cli -g
openapi-generator-cli generate -i openapi.json -g python -o python-client/
```

#### Documentation Sites
```bash
# Use with documentation generators
npx @redocly/openapi-cli build-docs openapi.json --output=docs.html
```

## 🎬 For Demo/Presentation

### Best Documentation for Different Audiences:

- **🎥 Demo Videos**: Swagger UI (interactive)
- **👔 Client Presentations**: ReDoc (professional)  
- **👨‍💻 Developer Onboarding**: Markdown (comprehensive)
- **🔧 Integration Teams**: JSON (programmatic)

### Offline Presentation Tips:
1. Generate docs before presentations (no internet needed)
2. Use ReDoc for clean, professional look
3. Swagger UI for interactive demonstrations
4. Keep openapi.json for technical discussions

## 🔍 Troubleshooting

### Common Issues:

**"Cannot import FastAPI app"**
```bash
# Make sure you're in the project root and venv is activated
cd /path/to/amazon_tool
source ~/.pyenv/versions/amazon/bin/activate
```

**"Module not found errors"**
```bash
# Install missing dependencies
pip install -r requirements.txt
```

**"Documentation looks broken"**
- Open HTML files in modern browser (Chrome/Firefox/Edge)
- Check browser console for JavaScript errors
- Ensure files are completely downloaded

**"API endpoints missing"**
- Verify all routers are included in main FastAPI app
- Check that endpoints are properly tagged
- Ensure OpenAPI schema generation is working

### Validation Commands:
```bash
# Test OpenAPI spec validity
python -c "from src.main.app import app; print('OpenAPI spec valid:', bool(app.openapi()))"

# Check endpoint count
python -c "from src.main.app import app; print('Endpoints:', len(app.routes))"
```

## 📈 Documentation Maintenance

### Keep Docs Updated:
1. **Regenerate after API changes** - Run `python generate_api_docs.py`
2. **Update descriptions** - Add docstrings to FastAPI endpoints
3. **Version documentation** - Tag releases with corresponding docs
4. **Validate regularly** - Check links and examples work

### Best Practices:
- 📝 Add detailed docstrings to all API endpoints
- 🏷️ Use consistent tags for grouping endpoints
- 📋 Include request/response examples
- ⚠️ Document error conditions and status codes
- 🔒 Document authentication requirements

---

**📚 Your API documentation is now ready for offline access and professional sharing!**