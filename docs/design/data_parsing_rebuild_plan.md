# Data Parsing Improvement & Database Rebuild Plan (Final)

## 🔍 **Issues Identified**

Based on analysis of the Apify data and current mapping logic, key parsing issues to fix:

### **Current Parsing Problems:**
1. **`reviews_count`**: Currently mapped from `countReview` ✅ (correct)
2. **`price`**: Currently mapped from `price` ✅ (correct)
3. **`features`**: **MISSING** - Not extracted from `features` array (bullet points)
4. **`rating`**: Needs improvement - parsed from `productRating` but could be more robust
5. **`asin`**: ✅ Keep using main `asin` field (user confirmed)
6. **`bsr`**: **MAJOR ISSUE** - Not parsing BSR from `productDetails[].Best Sellers Rank`
7. **`buybox_price`**: **LOGIC ERROR** - Should be `null` when `buyBoxUsed` is `null`, but currently defaults to main price

### **BSR Parsing Challenge:**
Extract most specific rank from:
```json
{
  "name": "Best Sellers Rank",
  "value": "#35,077 in Electronics (See Top 100 in Electronics) #2,607 in Earbud & In-Ear Headphones"
}
```
Need to extract `2607` for headphones category.

## 🚨 **CRITICAL REQUIREMENT - REAL ASINS ONLY**

### **⚠️ NO FAKE DATA POLICY:**
- **NEVER generate fake ASINs** or fake product data
- **ONLY use real ASINs** from `data/config/asin_roles.txt`
- **Always validate ASINs** against the approved list before using in demos/tests
- **Use actual product data** from the Apify dataset for all values

### **📋 ASIN Validation Workflow:**
1. **Check `data/config/asin_roles.txt`** for valid ASINs and their roles (main/comp)
2. **Extract real product data** from Apify dataset for these ASINs
3. **Use actual values** (real prices, real titles, real BSR) in all scripts
4. **NO hardcoded fake values** in demo scripts

## 🛠️ **Implementation Plan**

### **Phase 1: Enhanced Data Mapper (30 min)**
- **Fix BSR parsing**: Create robust regex to extract category-specific BSR ranks
- **Add features extraction**: Parse bullet points from `features` array for `core.product_features` table
- **Improve rating parsing**: Handle edge cases in rating text
- **Fix buybox_price logic**: Set to `null` when `buyBoxUsed` is `null`
- **ASIN validation**: Only process ASINs that exist in the real Apify dataset

### **Phase 2: Features Table Integration (20 min)**
- **Use existing `core.product_features` table**: Store features as separate records
- **Update mapper**: Create features records linked to ASIN
- **Maintain referential integrity**: Ensure features are properly linked to products

### **Phase 3: Database Rebuild Tool (20 min)**
- **New tool**: `tools/offline/rebuild_database.py`
- **Features**:
  - Clear existing data from core tables (including product_features)
  - Re-process all Apify data with improved mapper
  - **ONLY process real ASINs** from the dataset
  - Handle features insertion into separate table
  - Support dry-run mode and progress tracking

### **Phase 4: Demo/Testing Script Refactoring (25 min)**
- **Audit all demo scripts**: Find hardcoded fake ASINs and fake data
- **Replace with real ASINs**: Use ASINs from `data/config/asin_roles.txt`
- **Extract real data values**: Pull actual prices, titles, BSR from processed dataset
- **Create ASIN helper utility**: Function to get valid ASINs and their real data
- **Update default values**: Replace fake defaults with real product data

### **Phase 5: Testing & Validation (15 min)**
- **Test improved parsing**: Validate BSR extraction for different categories
- **Verify features storage**: Check product_features table population
- **Validate real data usage**: Ensure no fake ASINs remain in any scripts
- **Compare before/after**: Ensure data quality improvement with real data

## 🎯 **Key Improvements**

### **BSR Parsing Strategy:**
```python
def _extract_bsr(apify_data: Dict[str, Any]) -> Optional[int]:
    # Extract from productDetails "Best Sellers Rank"
    # Priority: Most specific category rank (headphones > electronics)
    # Handle formats: "#2,607 in Headphones" -> 2607
```

### **ASIN Validation Utility:**
```python
def get_valid_asins_from_config() -> Dict[str, str]:
    # Read data/config/asin_roles.txt
    # Return {asin: role} mapping for validation

def get_real_product_data(asin: str) -> Dict[str, Any]:
    # Extract real data for ASIN from processed dataset
    # Return actual values for use in demos/tests
```

### **Features Storage Strategy:**
```python
def _extract_features_for_table(apify_data: Dict[str, Any], asin: str) -> List[Dict]:
    # Extract bullet points from features array
    # Return list of records for core.product_features table insertion
    # Format: [{"asin": asin, "feature_text": "...", "order_index": 1}, ...]
```

## 📁 **Files to Create/Modify**

### **New Files:**
- `tools/offline/rebuild_database.py` - Database rebuild tool with features table support
- `tools/utilities/asin_validator.py` - ASIN validation and real data extraction utility

### **Modified Files:**
- `tools/offline/apify_mapper.py` - Enhanced parsing logic
- **All demo/testing scripts** - Replace fake ASINs with real ones from config
- **NO changes to core.products table schema** ✅

## ⚡ **Execution Flow**

1. **Update mapper** with improved BSR, features, and buybox parsing
2. **Build rebuild tool** that handles both core tables and product_features
3. **Create ASIN validation utility** for safe ASIN usage
4. **Run rebuild** to refresh Supabase with accurate real data
5. **Refactor all scripts** to use real ASINs and real product data
6. **Validate results** ensuring no fake data remains anywhere

## 🛡️ **Quality Assurance**

- **Real ASIN verification**: Every ASIN used must exist in `data/config/asin_roles.txt`
- **Real data values**: All prices, titles, BSR must come from actual Apify dataset
- **No fake data tolerance**: Zero tolerance for generated/hardcoded fake values
- **Demo accuracy**: All demos will use real Amazon product data for authenticity

This plan ensures your demo uses 100% real product data with significantly improved parsing accuracy.