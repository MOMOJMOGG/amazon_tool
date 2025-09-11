// Enhanced Swagger UI Configuration
// Custom JavaScript for Amazon Product Monitor API documentation

// API Documentation Configuration
const API_CONFIG = {
  title: "Amazon Product Monitor API",
  version: "1.0.0",
  description: "Professional API for Amazon product tracking and competitive analysis",
  contact: {
    name: "API Support",
    email: "support@amazonmonitor.com"
  },
  servers: {
    production: {
      url: "https://api.amazonmonitor.com",
      description: "Production API Server"
    },
    staging: {
      url: "https://staging-api.amazonmonitor.com", 
      description: "Staging API Server"
    },
    development: {
      url: "https://dev-api.amazonmonitor.com",
      description: "Development API Server"
    },
    local: {
      url: "http://localhost:8000",
      description: "Local Development Server"
    }
  }
};

// Authentication Configuration
const AUTH_CONFIG = {
  jwt: {
    name: "JWT Bearer Token",
    description: "Enter your JWT token to authenticate API requests",
    bearerFormat: "JWT",
    scheme: "bearer"
  },
  apiKey: {
    name: "API Key",
    description: "Enter your API key for authentication",
    in: "header",
    keyName: "X-API-Key"
  }
};

// Sample API Calls for Demo
const DEMO_REQUESTS = {
  products: {
    endpoint: "/v1/products",
    method: "GET",
    description: "Get list of monitored products",
    sampleResponse: {
      "products": [
        {
          "id": "B08N5WRWNW",
          "name": "Echo Dot (4th Gen)",
          "current_price": 49.99,
          "last_updated": "2025-01-10T10:00:00Z"
        }
      ]
    }
  },
  competition: {
    endpoint: "/v1/competition/analysis",
    method: "GET", 
    description: "Get competitive analysis data",
    sampleResponse: {
      "competitors": 9,
      "data_completeness": 52.90,
      "analysis_date": "2025-01-10T10:00:00Z"
    }
  },
  graphql: {
    endpoint: "/graphql",
    method: "POST",
    description: "GraphQL endpoint for flexible data queries",
    sampleQuery: `
query GetProductAnalysis {
  products(limit: 10) {
    id
    name
    currentPrice
    competitors {
      name
      price
      priceGap
    }
  }
}
    `
  }
};

// UI Enhancement Functions
function addCustomCSS() {
  const customCSS = `
    /* Amazon Product Monitor Custom Styling */
    .swagger-ui .info {
      background: linear-gradient(135deg, #232F3E 0%, #37475A 100%);
      color: white;
      padding: 30px;
      border-radius: 10px;
      margin-bottom: 30px;
    }
    
    .swagger-ui .info .title {
      color: white !important;
      text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    
    .swagger-ui .info .description {
      color: #f0f0f0 !important;
    }
    
    .swagger-ui .scheme-container {
      background: linear-gradient(135deg, #FF9900 0%, #FFB84D 100%);
      color: white;
      border: none !important;
    }
    
    .swagger-ui .opblock.opblock-get {
      border-color: #61affe;
      background: rgba(97, 175, 254, 0.1);
    }
    
    .swagger-ui .opblock.opblock-post {
      border-color: #49cc90;
      background: rgba(73, 204, 144, 0.1);
    }
    
    .swagger-ui .btn.authorize {
      background-color: #FF9900;
      border-color: #FF9900;
    }
    
    .swagger-ui .btn.authorize:hover {
      background-color: #e68900;
      border-color: #e68900;
    }
  `;
  
  const styleElement = document.createElement('style');
  styleElement.textContent = customCSS;
  document.head.appendChild(styleElement);
}

// Demo Data Loader
function loadDemoData() {
  console.log('Loading Amazon Product Monitor Demo Data...');
  
  // Add demo authentication token
  if (window.ui) {
    const demoToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZW1vLXVzZXIiLCJpYXQiOjE3MDQ5NjcyMDAsImV4cCI6MTcwNDk3NDQwMH0.demo-signature";
    
    setTimeout(() => {
      try {
        window.ui.authActions.authorize({
          BearerAuth: {
            name: "BearerAuth",
            schema: {
              type: "http",
              scheme: "bearer"
            },
            value: demoToken
          }
        });
        console.log('Demo authentication applied');
      } catch (error) {
        console.log('Demo auth not available yet, UI still loading');
      }
    }, 2000);
  }
}

// Environment Status Indicator
function addEnvironmentIndicator() {
  const indicator = document.createElement('div');
  indicator.id = 'env-indicator';
  indicator.style.cssText = `
    position: fixed;
    bottom: 20px;
    left: 20px;
    background: #232F3E;
    color: white;
    padding: 10px 15px;
    border-radius: 5px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 1000;
    font-size: 14px;
    font-weight: bold;
  `;
  
  const currentEnv = document.getElementById('env-select')?.value || 'production';
  const envColors = {
    production: '#28a745',
    staging: '#ffc107', 
    development: '#17a2b8',
    local: '#6c757d'
  };
  
  indicator.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <div style="width: 8px; height: 8px; border-radius: 50%; background: ${envColors[currentEnv]};"></div>
      <span>${currentEnv.toUpperCase()}</span>
    </div>
  `;
  
  document.body.appendChild(indicator);
}

// API Performance Monitor
function addPerformanceMonitor() {
  let requestCount = 0;
  let totalResponseTime = 0;
  
  const monitor = document.createElement('div');
  monitor.id = 'api-monitor';
  monitor.style.cssText = `
    position: fixed;
    top: 80px;
    right: 20px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 5px;
    padding: 15px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    z-index: 999;
    font-size: 12px;
    min-width: 200px;
  `;
  
  monitor.innerHTML = `
    <h4 style="margin: 0 0 10px 0; color: #232F3E;">API Performance</h4>
    <div id="request-count">Requests: 0</div>
    <div id="avg-response-time">Avg Response: 0ms</div>
    <div id="last-request">Last Request: -</div>
  `;
  
  document.body.appendChild(monitor);
  
  // Monitor API requests
  const originalFetch = window.fetch;
  window.fetch = function(...args) {
    const startTime = Date.now();
    return originalFetch.apply(this, args).then(response => {
      const endTime = Date.now();
      const responseTime = endTime - startTime;
      
      requestCount++;
      totalResponseTime += responseTime;
      
      document.getElementById('request-count').textContent = `Requests: ${requestCount}`;
      document.getElementById('avg-response-time').textContent = `Avg Response: ${Math.round(totalResponseTime / requestCount)}ms`;
      document.getElementById('last-request').textContent = `Last Request: ${responseTime}ms`;
      
      return response;
    });
  };
}

// Keyboard Shortcuts
function addKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus on filter
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const filter = document.querySelector('.swagger-ui .filter input[type="text"]');
      if (filter) filter.focus();
    }
    
    // Ctrl/Cmd + E to expand all operations
    if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
      e.preventDefault();
      const expandButtons = document.querySelectorAll('.swagger-ui .opblock-summary');
      expandButtons.forEach(button => {
        if (!button.parentElement.classList.contains('is-open')) {
          button.click();
        }
      });
    }
    
    // Ctrl/Cmd + R to collapse all operations  
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
      e.preventDefault();
      const expandButtons = document.querySelectorAll('.swagger-ui .opblock-summary');
      expandButtons.forEach(button => {
        if (button.parentElement.classList.contains('is-open')) {
          button.click();
        }
      });
    }
  });
}

// Help Modal
function addHelpModal() {
  const helpButton = document.createElement('button');
  helpButton.textContent = '?';
  helpButton.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: #FF9900;
    color: white;
    border: none;
    font-size: 18px;
    font-weight: bold;
    cursor: pointer;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 1001;
  `;
  
  helpButton.onclick = () => {
    const modal = document.createElement('div');
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.5);
      z-index: 2000;
      display: flex;
      align-items: center;
      justify-content: center;
    `;
    
    modal.innerHTML = `
      <div style="background: white; padding: 30px; border-radius: 10px; max-width: 500px; max-height: 80vh; overflow-y: auto;">
        <h2 style="color: #232F3E; margin-top: 0;">Amazon Product Monitor API - Help</h2>
        <h3>Keyboard Shortcuts:</h3>
        <ul>
          <li><kbd>Ctrl/Cmd + K</kbd> - Focus on filter input</li>
          <li><kbd>Ctrl/Cmd + E</kbd> - Expand all operations</li>
          <li><kbd>Ctrl/Cmd + R</kbd> - Collapse all operations</li>
        </ul>
        <h3>Features:</h3>
        <ul>
          <li>Environment switching (top right)</li>
          <li>JWT authentication support</li>
          <li>GraphQL endpoint testing</li>
          <li>Real-time performance monitoring</li>
          <li>Export OpenAPI specification</li>
        </ul>
        <button onclick="this.parentElement.parentElement.remove()" 
                style="background: #FF9900; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; float: right;">
          Close
        </button>
      </div>
    `;
    
    modal.onclick = (e) => {
      if (e.target === modal) modal.remove();
    };
    
    document.body.appendChild(modal);
  };
  
  document.body.appendChild(helpButton);
}

// Initialize all enhancements
document.addEventListener('DOMContentLoaded', () => {
  console.log('Initializing Amazon Product Monitor API Documentation');
  
  // Add custom styling
  addCustomCSS();
  
  // Add UI enhancements
  setTimeout(() => {
    addEnvironmentIndicator();
    addPerformanceMonitor();
    addKeyboardShortcuts();
    addHelpModal();
    loadDemoData();
  }, 1000);
});

// Export configuration for external use
window.AmazonMonitorAPI = {
  config: API_CONFIG,
  auth: AUTH_CONFIG,
  demo: DEMO_REQUESTS,
  loadDemoData: loadDemoData
};