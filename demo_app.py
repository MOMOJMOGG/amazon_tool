"""
Gradio Demo App for Amazon Product Monitoring Tool
Perfect for video recording and live demonstrations
"""

import gradio as gr
import httpx
import asyncio
import json
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Configuration
API_BASE_URL = "http://localhost:8080"
GRAPHQL_URL = f"{API_BASE_URL}/graphql"

# Real test data from your system
DEMO_ASINS = {
    "primary": "B0C6KKQ7ND",  # Soundcore headphones
    "competitors": ["B0FDKB341G", "B0DNBQ6HPR", "B0D9GYS7BX"]
}

class DemoAPIClient:
    """API client for demo interactions."""
    
    async def make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with fresh client to avoid connection issues."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, **kwargs)
                elif method.upper() == "POST":
                    response = await client.post(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                return {
                    "success": True,
                    "data": response.json(),
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds()
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_product(self, asin: str) -> Dict[str, Any]:
        """Get product details."""
        return await self.make_request("GET", f"{API_BASE_URL}/v1/products/{asin}")
    
    async def get_product_metrics(self, asin: str, range_param: str = "30d") -> Dict[str, Any]:
        """Get product historical metrics."""
        return await self.make_request("GET", f"{API_BASE_URL}/v1/products/{asin}/metrics?range={range_param}")
    
    async def get_batch_products(self, asins: List[str]) -> Dict[str, Any]:
        """Get multiple products in batch."""
        payload = {"asins": asins}
        return await self.make_request("POST", f"{API_BASE_URL}/v1/products/batch", json=payload)
    
    async def setup_competition(self, main_asin: str, competitor_asins: List[str]) -> Dict[str, Any]:
        """Setup competitive analysis."""
        payload = {
            "asin_main": main_asin,
            "competitor_asins": competitor_asins
        }
        return await self.make_request("POST", f"{API_BASE_URL}/v1/competitions/setup", json=payload)
    
    async def get_competition(self, asin: str, range_param: str = "30d") -> Dict[str, Any]:
        """Get competition analysis."""
        return await self.make_request("GET", f"{API_BASE_URL}/v1/competitions/{asin}?range={range_param}")
    
    async def get_competition_report(self, asin: str) -> Dict[str, Any]:
        """Get AI-generated competition report."""
        return await self.make_request("GET", f"{API_BASE_URL}/v1/competitions/{asin}/report")
    
    async def refresh_report(self, asin: str) -> Dict[str, Any]:
        """Trigger report refresh."""
        return await self.make_request("POST", f"{API_BASE_URL}/v1/competitions/{asin}/report:refresh")
    
    async def get_health(self) -> Dict[str, Any]:
        """Get system health."""
        return await self.make_request("GET", f"{API_BASE_URL}/health")
    
    async def graphql_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute GraphQL query."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return await self.make_request("POST", GRAPHQL_URL, json=payload)

# Global client instance
api_client = DemoAPIClient()

def format_json_response(response: Dict[str, Any]) -> str:
    """Format API response for display."""
    if not response.get("success"):
        return f"❌ **Error**: {response.get('error', 'Unknown error')}"
    
    data = response.get("data", {})
    response_time = response.get("response_time", 0)
    status_code = response.get("status_code", 200)
    
    formatted = f"✅ **Status**: {status_code} | **Response Time**: {response_time:.3f}s\n\n"
    formatted += f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
    
    return formatted

def create_metrics_chart(data: Dict[str, Any]) -> go.Figure:
    """Create metrics visualization chart."""
    try:
        if not data.get("success") or not data.get("data"):
            fig = go.Figure()
            fig.add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5)
            return fig
        
        metrics_data = data["data"].get("data", [])
        if not metrics_data:
            fig = go.Figure()
            fig.add_annotation(text="No metrics data found", xref="paper", yref="paper", x=0.5, y=0.5)
            return fig
        
        # Create subplots for different metrics
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Price Trend', 'BSR Trend', 'Rating Trend', 'Reviews Growth'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        dates = [item.get("date", "") for item in metrics_data]
        prices = [item.get("price", 0) for item in metrics_data]
        bsrs = [item.get("bsr", 0) for item in metrics_data]
        ratings = [item.get("rating", 0) for item in metrics_data]
        reviews = [item.get("reviews_count", 0) for item in metrics_data]
        
        # Price trend
        fig.add_trace(go.Scatter(x=dates, y=prices, name="Price", line=dict(color="green")), row=1, col=1)
        
        # BSR trend (lower is better)
        fig.add_trace(go.Scatter(x=dates, y=bsrs, name="BSR", line=dict(color="blue")), row=1, col=2)
        
        # Rating trend
        fig.add_trace(go.Scatter(x=dates, y=ratings, name="Rating", line=dict(color="orange")), row=2, col=1)
        
        # Reviews growth
        fig.add_trace(go.Scatter(x=dates, y=reviews, name="Reviews", line=dict(color="purple")), row=2, col=2)
        
        fig.update_layout(height=600, showlegend=False, title_text="Product Metrics Over Time")
        return fig
        
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text=f"Error creating chart: {str(e)}", xref="paper", yref="paper", x=0.5, y=0.5)
        return fig

def create_competition_chart(data: Dict[str, Any]) -> go.Figure:
    """Create competition analysis chart."""
    try:
        if not data.get("success") or not data.get("data"):
            fig = go.Figure()
            fig.add_annotation(text="No competition data available", xref="paper", yref="paper", x=0.5, y=0.5)
            return fig
        
        comp_data = data["data"].get("data", {})
        peers = comp_data.get("peers", [])
        
        if not peers:
            fig = go.Figure()
            fig.add_annotation(text="No peer comparison data found", xref="paper", yref="paper", x=0.5, y=0.5)
            return fig
        
        # Create radar chart for competitive positioning
        categories = ['Price Gap', 'BSR Gap', 'Rating Diff', 'Reviews Gap']
        
        fig = go.Figure()
        
        for peer in peers[:3]:  # Limit to first 3 competitors
            values = [
                peer.get("price_diff", 0),
                peer.get("bsr_gap", 0) / 1000,  # Scale BSR for visibility
                peer.get("rating_diff", 0) * 10,  # Scale rating for visibility  
                peer.get("reviews_gap", 0) / 100  # Scale reviews for visibility
            ]
            
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name=f"vs {peer.get('asin', 'Unknown')}"
            ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[-50, 50]
                )),
            showlegend=True,
            title="Competitive Positioning Analysis"
        )
        
        return fig
        
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text=f"Error creating competition chart: {str(e)}", xref="paper", yref="paper", x=0.5, y=0.5)
        return fig

# Async wrapper functions for Gradio
def async_wrapper(coro):
    """Wrapper to run async functions in Gradio."""
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))
    return wrapper

# Demo functions
async def demo_get_product(asin: str):
    """Demo: Get product details."""
    if not asin:
        return "Please enter an ASIN", None, None
    
    result = await api_client.get_product(asin)
    formatted_response = format_json_response(result)
    
    # Create simple product info display
    if result.get("success") and result.get("data"):
        product_data = result["data"].get("data", {})
        info_html = f"""
        <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px; background-color: #374151;">
            <h3>📦 {product_data.get('title', 'Unknown Product')}</h3>
            <p><strong>Brand:</strong> {product_data.get('brand', 'N/A')}</p>
            <p><strong>Category:</strong> {product_data.get('category', 'N/A')}</p>
            <p><strong>Latest Price:</strong> ${product_data.get('latest_price', 'N/A')}</p>
            <p><strong>BSR:</strong> {product_data.get('latest_bsr', 'N/A')}</p>
            <p><strong>Rating:</strong> {product_data.get('latest_rating', 'N/A')} ⭐</p>
            <p><strong>Reviews:</strong> {product_data.get('latest_reviews_count', 'N/A')}</p>
        </div>
        """
        return formatted_response, info_html, None
    
    return formatted_response, "❌ No product data available", None

async def demo_get_metrics(asin: str, range_param: str):
    """Demo: Get product metrics with visualization."""
    if not asin:
        return "Please enter an ASIN", None
    
    result = await api_client.get_product_metrics(asin, range_param)
    formatted_response = format_json_response(result)
    chart = create_metrics_chart(result)
    
    return formatted_response, chart

async def demo_batch_products(asins_text: str):
    """Demo: Batch product request."""
    if not asins_text:
        return "Please enter ASINs (comma-separated)", None
    
    asins = [asin.strip() for asin in asins_text.split(",") if asin.strip()]
    if not asins:
        return "Please enter valid ASINs", None
    
    start_time = time.time()
    result = await api_client.get_batch_products(asins)
    end_time = time.time()
    
    formatted_response = format_json_response(result)
    
    # Create performance comparison
    if result.get("success") and result.get("data"):
        batch_time = end_time - start_time
        per_product_time = batch_time / len(asins)
        
        perf_html = f"""
        <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px; background-color: #374151;">
            <h3>🚀 Batch Performance</h3>
            <p><strong>Products Requested:</strong> {len(asins)}</p>
            <p><strong>Total Time:</strong> {batch_time:.3f}s</p>
            <p><strong>Per Product:</strong> {per_product_time:.3f}s</p>
            <p><strong>Cache Benefits:</strong> Sub-second responses per product!</p>
        </div>
        """
        return formatted_response, perf_html
    
    return formatted_response, "❌ Batch request failed"

async def demo_setup_competition(main_asin: str, competitor_asins_text: str):
    """Demo: Setup competitive analysis."""
    if not main_asin or not competitor_asins_text:
        return "Please enter main ASIN and competitor ASINs"
    
    competitor_asins = [asin.strip() for asin in competitor_asins_text.split(",") if asin.strip()]
    if not competitor_asins:
        return "Please enter valid competitor ASINs"
    
    result = await api_client.setup_competition(main_asin, competitor_asins)
    return format_json_response(result)

async def demo_get_competition(asin: str, range_param: str):
    """Demo: Get competition analysis with visualization."""
    if not asin:
        return "Please enter an ASIN", None, None
    
    result = await api_client.get_competition(asin, range_param)
    formatted_response = format_json_response(result)
    chart = create_competition_chart(result)
    
    # Create competition table
    table_df = None
    if result.get("success") and result.get("data"):
        comp_data = result["data"].get("data", {})
        peers = comp_data.get("peers", [])
        
        if peers:
            table_data = []
            for peer in peers:
                table_data.append({
                    "Competitor ASIN": peer.get("asin", "N/A"),
                    "Price Difference": f"${peer.get('price_diff', 0):.2f}",
                    "BSR Gap": peer.get("bsr_gap", 0),
                    "Rating Difference": f"{peer.get('rating_diff', 0):.1f}",
                    "Reviews Gap": peer.get("reviews_gap", 0),
                    "Buybox Difference": f"${peer.get('buybox_diff', 0):.2f}"
                })
            table_df = pd.DataFrame(table_data)
    
    return formatted_response, chart, table_df

async def demo_get_report(asin: str):
    """Demo: Get AI competition report."""
    if not asin:
        return "Please enter an ASIN", None
    
    result = await api_client.get_competition_report(asin)
    formatted_response = format_json_response(result)
    
    # Format report for better display
    report_html = None
    if result.get("success") and result.get("data"):
        report_data = result["data"].get("data", {})
        summary = report_data.get("summary", {})
        
        if summary:
            strengths = summary.get("key_strengths", [])
            opportunities = summary.get("improvement_opportunities", [])
            
            report_html = f"""
            <div style="border: 1px solid #ddd; padding: 20px; border-radius: 8px; background-color: #374151;">
                <h3>🤖 AI Competition Analysis Report</h3>
                <p><strong>Competitive Position:</strong> {summary.get('competitive_position', 'N/A')}</p>
                
                <h4>💪 Key Strengths:</h4>
                <ul>
                {''.join(f'<li>{strength}</li>' for strength in strengths)}
                </ul>
                
                <h4>🎯 Improvement Opportunities:</h4>
                <ul>
                {''.join(f'<li>{opp}</li>' for opp in opportunities)}
                </ul>
                
                <p><em>Generated: {report_data.get('generated_at', 'N/A')}</em></p>
            </div>
            """
    
    return formatted_response, report_html

async def demo_refresh_report(asin: str):
    """Demo: Trigger report refresh."""
    if not asin:
        return "Please enter an ASIN"
    
    result = await api_client.refresh_report(asin)
    return format_json_response(result)

async def demo_system_health():
    """Demo: System health check."""
    result = await api_client.get_health()
    formatted_response = format_json_response(result)
    
    # Create health status display
    health_html = None
    if result.get("success") and result.get("data"):
        health_data = result["data"]
        services = health_data.get("services", {})
        
        status_color = "green" if health_data.get("status") == "healthy" else "red"
        
        health_html = f"""
        <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px; background-color: #374151;">
            <h3>🏥 System Health Status</h3>
            <p><strong>Overall Status:</strong> <span style="color: {status_color}">●</span> {health_data.get('status', 'unknown')}</p>
            <p><strong>Environment:</strong> {health_data.get('environment', 'N/A')}</p>
            <p><strong>Version:</strong> {health_data.get('version', 'N/A')}</p>
            
            <h4>Services:</h4>
            <ul>
                <li><strong>Database:</strong> <span style="color: {'green' if services.get('database') == 'healthy' else 'red'}">●</span> {services.get('database', 'unknown')}</li>
                <li><strong>Redis Cache:</strong> <span style="color: {'green' if services.get('redis') == 'healthy' else 'red'}">●</span> {services.get('redis', 'unknown')}</li>
            </ul>
            
            <p><strong>Response Time:</strong> {result.get('response_time', 0):.3f}s</p>
        </div>
        """
    
    return formatted_response, health_html

async def demo_graphql_query(query: str, variables_text: str):
    """Demo: GraphQL query execution."""
    if not query:
        return "Please enter a GraphQL query"
    
    variables = {}
    if variables_text:
        try:
            variables = json.loads(variables_text)
        except json.JSONDecodeError:
            return "Invalid JSON in variables field"
    
    result = await api_client.graphql_query(query, variables)
    return format_json_response(result)

# Create the Gradio interface
def create_demo_app():
    """Create the main Gradio demo application."""
    
    with gr.Blocks(
        title="Amazon Product Monitoring Tool - Demo",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 1200px !important;
        }
        .demo-header {
            text-align: center;
            padding: 20px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        """
    ) as demo:
        
        # Header
        gr.HTML("""
        <div class="demo-header">
            <h1>🚀 Amazon Product Monitoring Tool</h1>
            <p>Professional product tracking and competitive analysis system</p>
            <p><strong>Architecture:</strong> FastAPI + PostgreSQL + Redis + Celery + GraphQL</p>
        </div>
        """)
        
        with gr.Tabs():
            # Tab 1: Architecture Overview
            with gr.Tab("🏗️ Architecture Overview"):
                gr.HTML("""
                <div style="text-align: center; padding: 20px;">
                    <h2>System Architecture</h2>
                    <div style="border: 2px solid #ddd; padding: 20px; border-radius: 10px; background-color: #374151;">
                        <h3>🔄 Data Flow</h3>
                        <p><strong>Ingestion:</strong> Celery Workers → Apify APIs → PostgreSQL → Redis Cache</p>
                        <p><strong>API Layer:</strong> FastAPI (REST + GraphQL) → Cache-First Strategy → SWR Pattern</p>
                        <p><strong>Processing:</strong> Background Jobs → Competitive Analysis → AI Reports</p>
                        
                        <h3>🎯 Key Features</h3>
                        <ul style="text-align: left; display: inline-block;">
                            <li><strong>Product Monitoring:</strong> Track 1000+ ASINs with daily metrics</li>
                            <li><strong>Competitive Analysis:</strong> AI-powered comparison and insights</li>
                            <li><strong>Cache-First:</strong> Sub-200ms API responses with Redis</li>
                            <li><strong>Dual APIs:</strong> REST for integrations, GraphQL for flexibility</li>
                            <li><strong>Scalable:</strong> Horizontal worker scaling, batch processing</li>
                        </ul>
                    </div>
                </div>
                """)
                
                with gr.Row():
                    health_btn = gr.Button("🔍 Check System Health", variant="primary")
                    
                with gr.Row():
                    with gr.Column(scale=2):
                        health_response = gr.Textbox(label="API Response", lines=10)
                    with gr.Column(scale=1):
                        health_status = gr.HTML(label="Health Status")
                
                health_btn.click(
                    fn=async_wrapper(demo_system_health),
                    outputs=[health_response, health_status]
                )
            
            # Tab 2: Feature 1 - Product Monitoring  
            with gr.Tab("📦 Product Monitoring"):
                gr.HTML("<h2>Feature 1: Product Monitoring & Metrics</h2>")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        product_asin = gr.Textbox(
                            label="Product ASIN",
                            value=DEMO_ASINS["primary"],
                            placeholder="Enter Amazon ASIN (e.g., B0C6KKQ7ND)"
                        )
                        get_product_btn = gr.Button("Get Product Details", variant="primary")
                        
                        metrics_range = gr.Dropdown(
                            choices=["7d", "30d", "90d"],
                            value="30d",
                            label="Historical Range"
                        )
                        get_metrics_btn = gr.Button("Get Historical Metrics", variant="secondary")
                        
                with gr.Row():
                    with gr.Column(scale=2):
                        product_response = gr.Textbox(label="API Response", lines=8)
                    with gr.Column(scale=1):
                        product_info = gr.HTML(label="Product Info")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        metrics_response = gr.Textbox(label="Metrics API Response", lines=6)
                    with gr.Column(scale=2):
                        metrics_chart = gr.Plot(label="Metrics Visualization")
                
                # Batch processing demo
                gr.HTML("<h3>🚀 Batch Processing Demo</h3>")
                with gr.Row():
                    batch_asins = gr.Textbox(
                        label="Multiple ASINs (comma-separated)",
                        value=f"{DEMO_ASINS['primary']},{','.join(DEMO_ASINS['competitors'][:2])}",
                        placeholder="B0C6KKQ7ND,B0FDKB341G,B0DNBQ6HPR"
                    )
                    batch_btn = gr.Button("Batch Request", variant="primary")
                
                with gr.Row():
                    with gr.Column(scale=2):
                        batch_response = gr.Textbox(label="Batch API Response", lines=8)
                    with gr.Column(scale=1):
                        batch_performance = gr.HTML(label="Performance Stats")
                
                # Event handlers
                get_product_btn.click(
                    fn=async_wrapper(demo_get_product),
                    inputs=[product_asin],
                    outputs=[product_response, product_info, gr.State()]
                )
                
                get_metrics_btn.click(
                    fn=async_wrapper(demo_get_metrics),
                    inputs=[product_asin, metrics_range],
                    outputs=[metrics_response, metrics_chart]
                )
                
                batch_btn.click(
                    fn=async_wrapper(demo_batch_products),
                    inputs=[batch_asins],
                    outputs=[batch_response, batch_performance]
                )
            
            # Tab 3: Feature 2 - Competitive Analysis
            with gr.Tab("⚔️ Competitive Analysis"):
                gr.HTML("<h2>Feature 2: Competitive Analysis & AI Reports</h2>")
                
                # Competition setup
                gr.HTML("<h3>🎯 Setup Competition</h3>")
                with gr.Row():
                    with gr.Column(scale=1):
                        comp_main_asin = gr.Textbox(
                            label="Main Product ASIN",
                            value=DEMO_ASINS["primary"],
                            placeholder="Your product ASIN"
                        )
                        comp_competitor_asins = gr.Textbox(
                            label="Competitor ASINs (comma-separated)",
                            value=",".join(DEMO_ASINS["competitors"][:2]),
                            placeholder="Competitor ASINs"
                        )
                        setup_comp_btn = gr.Button("Setup Competition", variant="primary")
                        
                    with gr.Column(scale=2):
                        setup_response = gr.Textbox(label="Setup Response", lines=6)
                
                # Competition analysis
                gr.HTML("<h3>📊 Competition Analysis</h3>")
                with gr.Row():
                    comp_analysis_range = gr.Dropdown(
                        choices=["7d", "30d", "90d"],
                        value="30d",
                        label="Analysis Range"
                    )
                    get_comp_btn = gr.Button("Get Competition Analysis", variant="secondary")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        comp_response = gr.Textbox(label="Competition API Response", lines=6)
                    with gr.Column(scale=2):
                        comp_chart = gr.Plot(label="Competitive Positioning")
                
                with gr.Row():
                    comp_table = gr.Dataframe(label="Competitor Comparison Table")
                
                # AI Report generation
                gr.HTML("<h3>🤖 AI-Powered Competition Report</h3>")
                with gr.Row():
                    report_asin = gr.Textbox(
                        label="Product ASIN for Report",
                        value=DEMO_ASINS["primary"],
                        placeholder="Enter ASIN for AI analysis"
                    )
                    get_report_btn = gr.Button("Get AI Report", variant="primary")
                    refresh_report_btn = gr.Button("Refresh Report", variant="secondary")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        report_response = gr.Textbox(label="Report API Response", lines=6)
                    with gr.Column(scale=2):
                        report_display = gr.HTML(label="AI Analysis Report")
                
                # Event handlers
                setup_comp_btn.click(
                    fn=async_wrapper(demo_setup_competition),
                    inputs=[comp_main_asin, comp_competitor_asins],
                    outputs=[setup_response]
                )
                
                get_comp_btn.click(
                    fn=async_wrapper(demo_get_competition),
                    inputs=[comp_main_asin, comp_analysis_range],
                    outputs=[comp_response, comp_chart, comp_table]
                )
                
                get_report_btn.click(
                    fn=async_wrapper(demo_get_report),
                    inputs=[report_asin],
                    outputs=[report_response, report_display]
                )
                
                refresh_report_btn.click(
                    fn=async_wrapper(demo_refresh_report),
                    inputs=[report_asin],
                    outputs=[report_response]
                )
            
            # Tab 4: GraphQL Demo
            with gr.Tab("🔍 GraphQL Playground"):
                gr.HTML("<h2>GraphQL API Demo</h2>")
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.HTML("<h3>Sample Queries</h3>")
                        sample_queries = gr.Dropdown(
                            choices=[
                                "Single Product Query",
                                "Multiple Products Query", 
                                "Competition Query",
                                "Latest Report Query"
                            ],
                            label="Sample Queries",
                            value="Single Product Query"
                        )
                        
                        def load_sample_query(query_name):
                            queries = {
                                "Single Product Query": f"""
query GetProduct {{
  product(asin: "{DEMO_ASINS['primary']}") {{
    asin
    title
    brand
    category
    latest {{
      date
      price
      bsr
      rating
      reviewsCount
    }}
  }}
}}""",
                                "Multiple Products Query": f"""
query GetMultipleProducts {{
  products(asins: ["{DEMO_ASINS['primary']}", "{DEMO_ASINS['competitors'][0]}"]) {{
    asin
    title
    latest {{
      price
      bsr
      rating
    }}
  }}
}}""",
                                "Competition Query": f"""
query GetCompetition {{
  competition(asinMain: "{DEMO_ASINS['primary']}", peers: ["{DEMO_ASINS['competitors'][0]}"]) {{
    asinMain
    range
    peers {{
      asin
      priceDiff
      bsrGap
      ratingDiff
    }}
  }}
}}""",
                                "Latest Report Query": f"""
query GetLatestReport {{
  latestReport(asinMain: "{DEMO_ASINS['primary']}") {{
    asinMain
    version
    summary
    generatedAt
  }}
}}"""
                            }
                            return queries.get(query_name, "")
                        
                        # We'll connect this to the main graphql_query textbox below
                    
                    with gr.Column(scale=2):
                        graphql_query = gr.Textbox(
                            label="GraphQL Query",
                            lines=10,
                            value=f"""
query GetProduct {{
  product(asin: "{DEMO_ASINS['primary']}") {{
    asin
    title
    brand
    category
    latest {{
      date
      price
      bsr
      rating
      reviewsCount
    }}
  }}
}}""",
                            placeholder="Enter your GraphQL query here..."
                        )
                        
                        graphql_variables = gr.Textbox(
                            label="Variables (JSON)",
                            lines=3,
                            placeholder='{"asin": "B0C6KKQ7ND"}',
                            value=""
                        )
                        
                        execute_graphql_btn = gr.Button("Execute GraphQL Query", variant="primary")
                
                graphql_response = gr.Textbox(label="GraphQL Response", lines=15)
                
                # Event handlers
                sample_queries.change(
                    fn=load_sample_query,
                    inputs=[sample_queries],
                    outputs=[graphql_query]
                )
                
                execute_graphql_btn.click(
                    fn=async_wrapper(demo_graphql_query),
                    inputs=[graphql_query, graphql_variables],
                    outputs=[graphql_response]
                )
        
        # Footer
        gr.HTML("""
        <div style="text-align: center; padding: 20px; margin-top: 30px; border-top: 1px solid #ddd;">
            <p><strong>🎥 Perfect for Demo Videos!</strong></p>
            <p>This demo showcases the key features of the Amazon Product Monitoring Tool</p>
            <p>API Base URL: <code>http://localhost:8080</code> | GraphQL: <code>/graphql</code></p>
        </div>
        """)
    
    return demo

if __name__ == "__main__":
    demo_app = create_demo_app()
    demo_app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )