# Demo App Setup Guide

> **Perfect for recording professional demo videos of your Amazon Product Monitoring Tool**

## 🎯 Demo Overview

This Gradio demo app showcases the key features of your Amazon Product Monitoring Tool in a step-by-step flow designed for video recording:

1. **🏗️ Architecture Overview** - System health and architecture explanation
2. **📦 Product Monitoring** - Single product tracking, metrics, batch processing
3. **⚔️ Competitive Analysis** - Competition setup, analysis, AI reports
4. **🔍 GraphQL Playground** - Flexible API querying demonstration

## 🚀 Quick Start

### Prerequisites

1. **Backend API Running**: Your FastAPI backend must be running on `http://localhost:8080`
2. **Database with Test Data**: Real ASINs should be available in your database
3. **Dependencies Installed**: Gradio and visualization libraries

### Step 1: Install Demo Dependencies

```bash
# Install the additional demo dependencies
pip install gradio>=4.0.0 plotly>=5.0.0 pandas>=1.5.0

# Or install all requirements (includes demo dependencies)
pip install -r requirements.txt
```

### Step 2: Setup Competition Database Tables

The competition features require additional database tables. Run the setup script:

```bash
# Activate your virtual environment first
source ~/.pyenv/versions/amazon/bin/activate

# Run the database setup script
python setup_demo_db.py
```

**Alternative: Manual SQL Setup**
```bash
# If the Python script doesn't work, run the SQL manually
psql -h your-db-host -U your-user -d your-database -f setup_competition_tables.sql
```

### Step 3: Start Your Backend API

```bash
# Make sure your main API is running
uvicorn src.main.app:app --reload --host 0.0.0.0 --port 8000

# Or use Docker
docker-compose -f docker-compose.simple.yml up -d
```

### Step 4: Launch Demo App

```bash
# Run the demo app
python demo_app.py
```

The demo will be available at: **http://localhost:7860**

## 📋 Demo Script for Video Recording

### **Introduction (30 seconds)**
> "This is the Amazon Product Monitoring Tool - a professional backend system for product tracking and competitive analysis. Built with FastAPI, PostgreSQL, Redis, and Celery for production scalability."

### **Architecture Overview (30 seconds)**
1. Click "🔍 Check System Health"
2. Show system status, response times, service health
3. Explain: "Cache-first architecture with sub-200ms responses, background job processing, dual API design"

### **Product Monitoring Demo (90 seconds)**
1. **Single Product**: 
   - ASIN is pre-filled: `B0C6KKQ7ND` (Soundcore headphones)
   - Click "Get Product Details"
   - Show: Product info, pricing, ratings, BSR
   
2. **Historical Metrics**:
   - Select "30d" range
   - Click "Get Historical Metrics"
   - Show: Price trends, BSR changes, rating evolution charts
   
3. **Batch Processing**:
   - Multiple ASINs pre-filled
   - Click "Batch Request"
   - Show: Performance stats, sub-second per-product response times

### **Competitive Analysis Demo (90 seconds)**
1. **Setup Competition**:
   - Main ASIN pre-filled: `B0C6KKQ7ND`
   - Competitor ASINs pre-filled: `B0FDKB341G,B0DNBQ6HPR`
   - Click "Setup Competition"
   
2. **Analysis**:
   - Click "Get Competition Analysis"
   - Show: Competitive positioning radar chart, comparison table
   
3. **AI Report**:
   - Click "Get AI Report"
   - Show: LLM-generated competitive insights, strengths, opportunities

### **GraphQL Demo (30 seconds)**
1. Show sample queries dropdown
2. Select "Single Product Query"
3. Click "Execute GraphQL Query"  
4. Explain: "Flexible querying, exactly the data you need, single request"

## 🎬 Video Recording Tips

### **Camera Setup**
- Record in 1920x1080 resolution
- Use screen recording software (OBS, Loom, etc.)
- Show both browser and terminal if demonstrating API calls

### **Presentation Flow**
- **Start with architecture** - explain the big picture first
- **Use pre-filled data** - everything is configured with real ASINs
- **Show response times** - highlight performance benefits
- **Demonstrate error handling** - show system resilience
- **End with GraphQL** - show API flexibility

### **Key Talking Points**

**Technical Highlights:**
- "Cache-first architecture for sub-200ms responses"
- "Real-time competitive analysis with AI insights"
- "Horizontal scaling with Celery background workers"
- "Dual API design: REST for stability, GraphQL for flexibility"

**Business Value:**
- "Monitor 1000+ products efficiently"
- "AI-powered competitive intelligence"
- "Production-ready from day one"
- "Scales from startup to enterprise"

## 🔧 Demo Configuration

### **Real Test Data Used**
- **Primary ASIN**: `B0C6KKQ7ND` (Soundcore headphones)
- **Competitor ASINs**: `B0FDKB341G`, `B0DNBQ6HPR`, `B0D9GYS7BX`
- All ASINs are real and should have data in your database

### **API Endpoints Demonstrated**
```
GET  /health                          # System health
GET  /v1/products/{asin}             # Product details
GET  /v1/products/{asin}/metrics     # Historical metrics  
GET  /v1/products/metrics:batch      # Batch product requests
POST /v1/competitions/setup          # Setup competitors
GET  /v1/competitions/{asin}         # Competition analysis
GET  /v1/competitions/{asin}/report  # AI reports
POST /graphql                        # GraphQL queries
```

### **Customizing Demo Data**
Edit the `DEMO_ASINS` dictionary in `demo_app.py`:
```python
DEMO_ASINS = {
    "primary": "YOUR_PRIMARY_ASIN",
    "competitors": ["COMPETITOR_1", "COMPETITOR_2", "COMPETITOR_3"]
}
```

## 🐛 Troubleshooting

### **Common Issues**

**"Connection Error" Messages:**
- Ensure your FastAPI backend is running on port 8080
- Check if your database has the test ASINs with actual data
- Verify Redis is running and accessible

**"No Data Available":**
- Run your ETL pipeline to populate test data
- Check that the demo ASINs exist in your database
- Verify external API keys are configured

**Charts Not Loading:**
- Ensure Plotly is installed: `pip install plotly>=5.0.0`
- Check that metrics data exists for the demo ASINs
- Browser developer tools will show any JavaScript errors

### **Demo App Logs**
The demo app runs with debug mode enabled, check the console for detailed error messages:
```bash
python demo_app.py
# Watch console output for API call details and errors
```

### **Backend API Health**
Test your backend independently:
```bash
curl http://localhost:8080/health
curl http://localhost:8080/v1/products/B0C6KKQ7ND
```

## 📊 Performance Expectations

**Expected Response Times:**
- Health check: < 100ms
- Single product (cached): < 50ms  
- Single product (uncached): < 500ms
- Batch products: < 200ms per product
- Competition analysis: < 300ms
- AI report generation: 2-5 seconds

**Demo Success Criteria:**
- ✅ All API calls return data (not errors)
- ✅ Charts render correctly with real metrics
- ✅ Response times are consistently fast
- ✅ System health shows all services healthy
- ✅ GraphQL queries execute successfully

---

## 🎥 Ready to Record!

With this setup, you'll have a professional demo that showcases:
- **System architecture and health monitoring**
- **Real product data and metrics visualization** 
- **Competitive analysis with AI insights**
- **API performance and scalability features**
- **GraphQL flexibility and developer experience**

Perfect for investor presentations, technical demos, or developer documentation videos!