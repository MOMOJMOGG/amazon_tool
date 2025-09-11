#!/usr/bin/env python3
"""
Generate offline API documentation for Amazon Product Monitoring Tool
Creates Swagger/OpenAPI docs that can be viewed without running the server
"""

import json
import os
import sys
from pathlib import Path
import asyncio
from typing import Dict, Any

def create_offline_swagger_html(openapi_spec: Dict[str, Any], output_path: str):
    """Create a standalone HTML file with Swagger UI."""
    
    swagger_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Amazon Product Monitoring API Documentation</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui.css" />
    <style>
        html {{
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }}
        *, *:before, *:after {{
            box-sizing: inherit;
        }}
        body {{
            margin:0;
            background: #fafafa;
        }}
        .info {{
            margin: 20px auto;
            max-width: 1200px;
            padding: 20px;
            background: white;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
    </style>
</head>
<body>
    <div class="info">
        <h1>📚 Amazon Product Monitoring Tool - API Documentation</h1>
        <p><strong>Version:</strong> {openapi_spec.get('info', {}).get('version', '1.0.0')}</p>
        <p><strong>Description:</strong> {openapi_spec.get('info', {}).get('description', 'FastAPI backend for Amazon product tracking and competitive analysis')}</p>
        <p><strong>Generated:</strong> Offline documentation (no server required)</p>
    </div>
    
    <div id="swagger-ui"></div>
    
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {{
            const ui = SwaggerUIBundle({{
                spec: {json.dumps(openapi_spec, indent=2)},
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout"
            }});
        }};
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(swagger_html)
    
    return output_path

def create_redoc_html(openapi_spec: Dict[str, Any], output_path: str):
    """Create a standalone HTML file with ReDoc UI."""
    
    redoc_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Amazon Product Monitoring API Documentation - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body {{
            margin: 0;
            padding: 0;
        }}
        .header {{
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Amazon Product Monitoring Tool</h1>
        <p>Professional API Documentation</p>
    </div>
    
    <redoc scroll-y-offset="80"></redoc>
    
    <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
    <script>
        // Embed the OpenAPI spec directly
        const spec = {json.dumps(openapi_spec, indent=2)};
        Redoc.init(spec, {{}}, document.querySelector('redoc'));
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(redoc_html)
    
    return output_path

def get_openapi_spec_from_app() -> Dict[str, Any]:
    """Extract OpenAPI specification from the FastAPI app."""
    try:
        from src.main.app import app
        return app.openapi()
    except Exception as e:
        print(f"Error getting OpenAPI spec from app: {e}")
        return None

def create_markdown_docs(openapi_spec: Dict[str, Any], output_path: str):
    """Create markdown documentation from OpenAPI spec."""
    
    info = openapi_spec.get('info', {})
    paths = openapi_spec.get('paths', {})
    components = openapi_spec.get('components', {})
    
    md_content = f"""# Amazon Product Monitoring Tool - API Documentation

**Version:** {info.get('version', '1.0.0')}  
**Description:** {info.get('description', 'FastAPI backend for Amazon product tracking and competitive analysis')}

## 📋 Table of Contents

"""
    
    # Generate table of contents
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                summary = details.get('summary', f'{method.upper()} {path}')
                anchor = summary.lower().replace(' ', '-').replace('/', '').replace('{', '').replace('}', '')
                md_content += f"- [{summary}](#{anchor})\n"
    
    md_content += "\n## 🔗 API Endpoints\n\n"
    
    # Generate endpoint documentation
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                summary = details.get('summary', f'{method.upper()} {path}')
                description = details.get('description', '')
                
                md_content += f"### {summary}\n\n"
                md_content += f"**Endpoint:** `{method.upper()} {path}`\n\n"
                
                if description:
                    md_content += f"**Description:** {description}\n\n"
                
                # Parameters
                parameters = details.get('parameters', [])
                if parameters:
                    md_content += "**Parameters:**\n\n"
                    for param in parameters:
                        param_name = param.get('name', '')
                        param_in = param.get('in', '')
                        param_desc = param.get('description', '')
                        required = '(required)' if param.get('required', False) else '(optional)'
                        md_content += f"- `{param_name}` ({param_in}) {required}: {param_desc}\n"
                    md_content += "\n"
                
                # Request body
                request_body = details.get('requestBody', {})
                if request_body:
                    md_content += "**Request Body:**\n\n"
                    content = request_body.get('content', {})
                    for content_type, schema_info in content.items():
                        md_content += f"Content-Type: `{content_type}`\n\n"
                        # Could add schema details here
                
                # Responses
                responses = details.get('responses', {})
                if responses:
                    md_content += "**Responses:**\n\n"
                    for status_code, response_info in responses.items():
                        description = response_info.get('description', '')
                        md_content += f"- **{status_code}**: {description}\n"
                    md_content += "\n"
                
                md_content += "---\n\n"
    
    # Add schemas section
    schemas = components.get('schemas', {})
    if schemas:
        md_content += "## 📊 Data Models\n\n"
        for schema_name, schema_info in schemas.items():
            md_content += f"### {schema_name}\n\n"
            properties = schema_info.get('properties', {})
            if properties:
                md_content += "**Properties:**\n\n"
                for prop_name, prop_info in properties.items():
                    prop_type = prop_info.get('type', 'unknown')
                    prop_desc = prop_info.get('description', '')
                    md_content += f"- `{prop_name}` ({prop_type}): {prop_desc}\n"
            md_content += "\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return output_path

async def main():
    """Main documentation generation function."""
    print("📚 Amazon Product Monitoring Tool - API Documentation Generator")
    print("=" * 70)
    
    # Create docs directory
    docs_dir = Path("api_docs")
    docs_dir.mkdir(exist_ok=True)
    
    # Get OpenAPI specification
    print("🔍 Extracting OpenAPI specification...")
    
    try:
        openapi_spec = get_openapi_spec_from_app()
        if not openapi_spec:
            raise Exception("Could not extract OpenAPI spec")
        
        print("✅ OpenAPI specification extracted successfully")
        
        # Save raw OpenAPI JSON
        json_path = docs_dir / "openapi.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(openapi_spec, f, indent=2, ensure_ascii=False)
        print(f"✅ Raw OpenAPI JSON saved: {json_path}")
        
        # Generate Swagger UI HTML
        swagger_path = docs_dir / "swagger.html"
        create_offline_swagger_html(openapi_spec, swagger_path)
        print(f"✅ Swagger UI documentation: {swagger_path}")
        
        # Generate ReDoc HTML
        redoc_path = docs_dir / "redoc.html"
        create_redoc_html(openapi_spec, redoc_path)
        print(f"✅ ReDoc documentation: {redoc_path}")
        
        # Generate Markdown documentation
        md_path = docs_dir / "api_reference.md"
        create_markdown_docs(openapi_spec, md_path)
        print(f"✅ Markdown documentation: {md_path}")
        
        print("\n" + "=" * 70)
        print("📖 Documentation Generated Successfully!")
        print("=" * 70)
        
        print("\\n🌐 **View Options:**")
        print(f"  • Swagger UI: Open {swagger_path.absolute()} in your browser")
        print(f"  • ReDoc: Open {redoc_path.absolute()} in your browser")  
        print(f"  • Markdown: View {md_path.absolute()} in any text editor")
        print(f"  • JSON: Use {json_path.absolute()} with API tools")
        
        print("\\n💡 **Usage Tips:**")
        print("  • HTML files work offline - no server needed")
        print("  • Swagger UI allows interactive API testing")
        print("  • ReDoc provides clean, professional documentation")
        print("  • Markdown is great for GitHub/documentation sites")
        print("  • JSON can be imported into Postman/Insomnia")
        
        # Count endpoints
        endpoint_count = sum(len([m for m in methods.keys() if m.lower() in ['get', 'post', 'put', 'delete', 'patch']]) 
                           for methods in openapi_spec.get('paths', {}).values())
        model_count = len(openapi_spec.get('components', {}).get('schemas', {}))
        
        print(f"\\n📊 **Documentation Stats:**")
        print(f"  • {endpoint_count} API endpoints documented")
        print(f"  • {model_count} data models included")
        print(f"  • Generated {len(list(docs_dir.glob('*')))} documentation files")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating documentation: {e}")
        print("\\n💡 **Troubleshooting:**")
        print("  • Make sure you're in the project root directory")
        print("  • Ensure the virtual environment is activated")
        print("  • Check that all dependencies are installed")
        print("  • Verify the FastAPI app can be imported")
        
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)