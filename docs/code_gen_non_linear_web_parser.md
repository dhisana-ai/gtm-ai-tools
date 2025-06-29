# Non-Linear Web Parser Code Gen

## Problem Solved

**Heavy LLM Token Usage for Multi-Page Parsing**: Traditional AI web scraping requires expensive LLM calls for every page, making it cost-prohibitive for large-scale data extraction.

**Code Generation for Complex Websites**: Non-linear and multi-page websites require specialized parsing logic that's difficult to write manually.

## Solution

This utility generates **reusable Python code** for non-linear/multi-page parsing that can run independently without further LLM calls. The generated code integrates seamlessly with existing GTM utilities.

**Important**: This tool is designed for **code generation only** - it creates reusable utilities for repeated data extraction tasks. It is **NOT suitable for one-time web parsing** due to the heavy LLM token usage during the generation phase.

**Website-Specific**: The generated code is **optimized for the specific website structure** it was created for. It works best for parsing the **same webapp/website** repeatedly, not for different websites with different structures.

### Key Benefits

- **One-Time LLM Cost**: Generate code once, run freely without additional LLM tokens
- **Dynamic Page Analysis**: AI analyzes each page individually and generates optimized extraction code
- **Code Aggregation**: Combines multiple page-specific codes into a single utility
- **GTM Integration**: Generated utilities work with existing GTM workflows
- **Cost-Effective**: Perfect for repeated data extraction tasks
- **Non-Linear Support**: Handles complex website structures with multiple navigation paths
- **Website-Specific Optimization**: Code tailored to the exact structure of the target website

### When to Use This Tool

✅ **Use for**:
- Creating reusable utilities for repeated data extraction
- Complex multi-page website parsing
- Non-linear website structures
- GTM workflows requiring consistent data extraction
- Batch processing of similar websites
- **Parsing the same website structure repeatedly**

❌ **Not suitable for**:
- One-time web scraping tasks
- Simple single-page data extraction
- Quick data gathering without reuse
- Low-volume or ad-hoc scraping needs
- **Parsing different websites with different structures**
- **Generic scraping across multiple unrelated websites**

## How It Works

1. **AI Analysis**: LLM analyzes website structure and identifies data patterns
2. **Code Generation**: Creates Python utilities for each page type
3. **Code Aggregation**: Combines individual page codes into unified utility
4. **Free Execution**: Generated code runs without further LLM calls
5. **GTM Integration**: Outputs data in standard GTM formats

## Technical Workflow: Step-by-Step

1. **Fetch HTML Using Playwright**
   - Handles JavaScript and dynamic content for accurate page rendering.

2. **AI-Driven Page Analysis**
   - Determines page type (e.g., listing page, detail page, etc.)
   - Identifies available data fields and navigation elements.
   - Assigns a relevance score (0.0–1.0) to each page.

3. **Python Code Generation for Each Page Type**
   - Generates extraction code tailored to the specific page structure.
   - Executes and validates the generated code immediately.
   - If code fails, AI auto-fixes it (up to 4 attempts, using different models for generation and fixing).

4. **Navigation & Relevance Filtering**
   - Identifies next pages to visit based on relevance and navigation elements.
   - Only visits pages likely to contain required data.
   - Avoids duplicate or irrelevant page types with similar structures.

5. **Aggregation & Utility Creation**
   - Collects all validated code for different page types.
   - Combines them into a single, production-ready Python utility.
   - Adds CLI argument parsing, CSV input/output, error handling, and logging.

6. **AI Extraction Specification (if no fields provided)**
   - Analyzes the target URL and user instructions.
   - Creates a structured JSON specification with field names, validation rules, and output format.
   - Determines what data is likely available on the website.

---

## Examples
### 1. Amazon FBA Seller Lead Generation
**Target**: https://www.amazon.com/Best-Sellers/zgbs/

**Instructions**:
- Extract brands with 500+ reviews in niche categories
- Capture seller name + contact via "Ask a Question"
- Identify private label vs. wholesale sellers
- Flag sellers using FBA (Fulfillment by Amazon)
- Validation: 80% response rate to seller messages

**Generated Code**: Creates utility to crawl Amazon product pages, extract seller information, and identify FBA sellers for lead generation.

**Note**: This code works specifically for Amazon's structure and would need regeneration for other e-commerce sites.

### YCombinator Startup Analysis
**Target**: https://www.ycombinator.com/

**Instructions**:
- Parse list of startups from YCombinator page
- Check if they have SOC2 certification
- Find founders of companies without SOC2 certification

**Generated Code**: Analyzes startup profiles, identifies SOC2 status, and extracts founder information for compliance-focused outreach.

**Note**: This code is optimized for YCombinator's specific page structure.


**Target**: https://www.producthunt.com/

**Instructions**:
- Find creators of top apps in Product Hunt
- Use Playwright + structured data parsing
- Extract app listings and company information
- Find founders of apps (consider as leads)

**Generated Code**: Crawls Product Hunt pages, extracts app creator information, and identifies founders for partnership opportunities.
**Note**: This code works specifically for Product Hunt's layout and navigation structure.

An AI-driven web scraping system that analyzes websites and generates custom Python utilities for data extraction. Supports non-linear crawling and GTM workflow integration.

----------

## Features
- **AI Analysis**: Intelligent page relevance scoring and field identification
- **Non-Linear Crawling**: Tree-based multi-path website exploration
- **Code Generation**: Automatic Python utility creation with CLI/CSV support
- **GTM Integration**: Standard property mapping and workflow compatibility
- **Website-Specific**: Optimized for the target website's structure

 