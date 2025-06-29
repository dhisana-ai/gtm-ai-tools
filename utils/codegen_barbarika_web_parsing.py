"""
AI-powered web parser for GTM tools.

This module provides intelligent web scraping and code generation capabilities
using OpenAI and Playwright. It can analyze websites, generate extraction code,
and execute the generated code to extract structured data.

Key Features:
- Intelligent website analysis using LLM
- Automatic code generation for data extraction
- Multi-page crawling with relevance scoring
- Integration with GTM utility framework
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import importlib.util
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import traceback
from urllib.parse import urlparse

import argparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel

from utils import common
from utils.fetch_html_playwright import _fetch_and_clean, fetch_multiple_html_pages, html_to_markdown, _fetch_and_markdown
from utils.common import (
    call_openai_async,
    call_openai_sync,
    openai_client_sync,
    openai_client as openai_client_async,
)

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path)

# Load Playwright sample code for LLM prompt context
def _load_playwright_sample() -> str:
    """Load sample Playwright usage code for LLM context."""
    try:
        playwright_sample = ""
        extract_webpage_sample = ""
        
        # Load fetch_html_playwright.py
        sample_path = Path(__file__).parent / "fetch_html_playwright.py"
        if sample_path.exists():
            with open(sample_path, 'r', encoding='utf-8') as f:
                sample_code = f.read()
            playwright_sample = f"Here is playwright usage utils/fetch_html_playwright.py : {sample_code}"
        else:
            logger.warning("utils/fetch_html_playwright.py not found")
        

        
        return playwright_sample
    except Exception as e:
        logger.warning(f"Failed to load Playwright sample: {e}")
        return ""

sample_of_playwright_usage = _load_playwright_sample()

# Initialize OpenAI clients (global instances for reuse)
openai_async_client = openai_client_async()
openai_client = openai_client_sync()

# =============================================================================
# DATA MODELS
# =============================================================================

class UserRequirement(BaseModel):
    """
    Represents user requirements for web data extraction.
    
    This class defines the parameters needed to extract data from websites,
    including the target URL, data fields to extract, crawling depth,
    and additional instructions for the extraction process.
    
    Attributes:
        target_url: The URL to scrape and analyze
        data_to_extract: List of field names to extract (auto-generated if None)
        max_depth: Maximum depth for crawling (default: 3)
        pagination: Whether to handle pagination (default: False)
        additional_instructions: Custom instructions for extraction
        extraction_spec: Detailed extraction specification (auto-generated)
    """
    
    target_url: str
    data_to_extract: Optional[List[str]] = None
    max_depth: int = 3
    pagination: bool = False
    additional_instructions: str = ""
    extraction_spec: Optional[Dict[str, Any]] = None

    def __init__(self, **data):
        """Initialize UserRequirement and auto-generate extraction spec if needed."""
        super().__init__(**data)
        if not self.data_to_extract:
            self._generate_extraction_spec()

    def _generate_extraction_spec(self) -> None:
        """
        Use LLM to generate a structured extraction specification.
        
        This method creates a detailed JSON specification for data extraction
        based on the target URL and additional instructions provided by the user.
        """
        prompt = f"""
        Based on the following user requirements, create a structured JSON specification for data extraction:

        Target URL: {self.target_url}
        Additional Instructions: {self.additional_instructions}

        Return a JSON object with the following structure:
        {{
            "extraction_fields": [
                {{
                    "field_name": "name of the field in snake_case",
                    "description": "what this field represents",
                    "example": "example value",
                    "required": true/false,
                    "validation_rules": ["list of validation rules"]
                }}
            ],
            "data_structure": {{
                "type": "list/object",
                "description": "how the data should be structured"
            }},
            "output_format": {{
                "type": "json/csv",
                "fields": ["list of fields to include in output"]
            }}
        }}

        Make sure the fields are:
        1. Specific and well-defined
        2. Likely to be found on the target website
        3. Relevant to the user's requirements
        4. In snake_case format
        5. Include validation rules where appropriate
        
        """

        try:
            spec = call_openai_sync(
                prompt=prompt,
                response_format={"type": "json_object"},
                client=openai_client
            )
            spec_data = json.loads(spec)
            self.data_to_extract = [field["field_name"] for field in spec_data["extraction_fields"]]
            self.extraction_spec = spec_data
            logger.info("📋 LLM generated extraction specification")
            logger.debug(f"Extraction spec: {json.dumps(spec_data, indent=2)}")
        except Exception as e:
            logger.error(f"❌ Error generating extraction specification: {str(e)}")
            self.data_to_extract = []
            self.extraction_spec = None


class PageData(BaseModel):
    """
    Represents a single page in the web crawling tree.
    
    This class stores all information about a crawled page, including
    its HTML content, analysis results, generated code, and relationships
    to other pages in the tree.
    
    Attributes:
        url: The page URL
        html: Raw HTML content
        json_data: Structured data extracted from the page
        path: Breadcrumb path from root to this page
        children: Child pages in the tree
        parent: Parent page in the tree
        analysis_data: Results of page analysis
        to_be_filled_fields: Fields that need to be extracted
        page_type: Type/category of the page
        exclusive_fields: Fields unique to this page
        generated_code: Python code generated for this page
        code_execution_result: Results of executing the generated code
        code_execution_error: Any errors during code execution
        relevance_score: How relevant this page is to the extraction goal
        processing_status: Current processing status
        status_message: Detailed status message
        start_time: When processing started
        last_update_time: When status was last updated
        error_details: Detailed error information if any
        progress: Processing progress (0-100)
        markdown: Optional markdown content of the HTML
    """
    
    url: str
    html: str
    json_data: Dict[str, Any]
    path: List[str]
    children: List['PageData'] = []
    parent: Optional['PageData'] = None
    analysis_data: Optional[Dict[str, Any]] = None
    to_be_filled_fields: List[str] = []
    page_type: Optional[str] = None
    exclusive_fields: List[str] = []
    generated_code: Optional[str] = None
    code_execution_result: Optional[Dict[str, Any]] = None
    code_execution_error: Optional[str] = None
    relevance_score: float = 0.0
    processing_status: str = "pending"  # pending, processing, completed, error
    status_message: str = ""
    start_time: Optional[float] = None
    last_update_time: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    progress: int = 0  # 0-100
    markdown: Optional[str] = None


class WebParser:
    """
    AI-powered web parser for intelligent data extraction.
    
    This class orchestrates the entire web parsing process:
    1. Analyzes user requirements
    2. Crawls and analyzes web pages
    3. Generates extraction code
    4. Executes the generated code
    
    The parser uses LLM to understand page structure and generate
    appropriate extraction code for each page type.
    """
    
    def __init__(
        self, 
        requirement: UserRequirement, 
        log_update_callback: Optional[Callable[[str], None]] = None,
        tree_update_callback: Optional[Callable[[Dict], None]] = None
    ):
        """
        Initialize the WebParser with user requirements.
        
        Args:
            requirement: User requirements for data extraction
            log_update_callback: Optional callback for log updates
            tree_update_callback: Optional callback for tree updates
        """
        logger.info(f"🚀 Initializing WebParser with URL: {requirement.target_url}")
        logger.info(f"📋 Data to extract: {requirement.data_to_extract}")
        logger.info(f"🔍 Max depth: {requirement.max_depth}")
        logger.info(f"📄 Pagination: {requirement.pagination}")
        logger.info(f"📝 Additional instructions: {requirement.additional_instructions}")
        
        self.requirement = requirement
        self.root_url = requirement.target_url
        self.log_update_callback = log_update_callback or (lambda msg: None)
        self.tree_update_callback = tree_update_callback or (lambda tree: None)
        
        # Internal state
        self.page_tree: Dict[str, PageData] = {}
        self.visited_urls: set = set()
        self.visited_page_types: set = set()
        self.generated_code: str = ""
        self.python_code_function_name: str = ""
        self.plan: Dict[str, Any] = {}
        self.tree_root: Optional[PageData] = None
        self.extra_info: Dict[str, Any] = {}
        
        # Tree update optimization
        self.last_tree_update = 0.0
        self.tree_update_throttle = 0.05  # 50ms throttle (reduced from 100ms)
        self.pending_tree_update = False
        
        # Send initial tree update to show starting state
        self._update_tree("Initializing WebParser...")

    async def analyze_requirement(self) -> Dict[str, Any]:
        """
        Analyze user requirement and create extraction plan.
        
        Returns:
            Dictionary containing the extraction plan with steps, required pages,
            data patterns, and validation rules.
        """
        logger.info("📊 Analyzing user requirements...")
        
        pagination_analysis = ""
        if self.requirement.pagination:
            pagination_analysis = """
        PAGINATION ANALYSIS:
        - Analyze the target URL to determine pagination strategy
        - Identify potential pagination patterns (URL-based, JavaScript-based, etc.)
        - Determine appropriate pagination approach (selector-based vs action-based)
        - Set reasonable pagination limits and error handling
        - Include pagination-specific extraction steps
        """
        
        prompt = f"""
        You are an expert web scraping architect. Your task is to analyze a web scraping requirement and create a comprehensive, actionable extraction plan in JSON format.
        
        Here is the user requirement: {self.requirement.additional_instructions}
        Target URL: {self.requirement.target_url}
        Data to Extract: {self.requirement.data_to_extract}
        Max Depth: {self.requirement.max_depth}
        Pagination: {self.requirement.pagination}

        Create a plan in JSON format:
        {{
            "extraction_steps": [],
            "required_pages": [],
            "data_patterns": [],
            "pagination_strategy": "",
            "validation_rules": [],
            "already_extracted_fields": [],
            "to_be_extracted_fields": [],
            "required_data": []
        }}

        Standards instruction:
            - Use standard names for lead and company properties in output like full_name, first_name, last_name, user_linkedin_url, email, organization_linkedin_url, website, job_title, lead_location, primary_domain_of_organization
            - provide proper required data
            - provide proper extraction_steps
            {pagination_analysis}
        """

        try:
            plan = call_openai_sync(
                prompt=prompt,
                response_format={"type": "json_object"},
                client=openai_client
            )
            plan_data = json.loads(plan)
            logger.info("✅ Requirement analysis complete")
            logger.debug(f"Plan: {json.dumps(plan_data, indent=2)}")
            logger.info(f"📋 Extraction steps: {len(plan_data.get('extraction_steps', []))}")
            return plan_data
        except Exception as e:
            logger.error(f"❌ Error analyzing requirements: {str(e)}")
            raise

    async def analyze_page_directly(
        self, 
        html: str, 
        markdown: Optional[str],
        url: str, 
        parent_page: Optional[PageData] = None,
        use_markdown_for_llm: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze HTML or Markdown directly and return comprehensive analysis data.
        Args:
            html: Raw HTML content to analyze
            markdown: Markdown version of the HTML
            url: URL of the page being analyzed
            parent_page: Parent page in the tree (if any)
            use_markdown_for_llm: If True, use markdown for LLM input, else use HTML
        Returns:
            Dictionary containing analysis results including structured data,
            page type, relevance score, and generated code.
        """
        logger.info(f"🔍 Analyzing page directly: {url} (use_markdown_for_llm={use_markdown_for_llm})")
        self.log_update_callback(f"🔍 Analyzing page directly: {url} calling llm (use_markdown_for_llm={use_markdown_for_llm})")
        self._update_tree(f"Analyzing page structure: {url}", url)

        # TODO: To experiment with markdown, set use_markdown_for_llm=True in fetch_and_process_page
        content = markdown if use_markdown_for_llm and markdown else html
        content_type = "markdown" if use_markdown_for_llm and markdown else "html"
        prompt = self._build_page_analysis_prompt(content, url, parent_page, content_type=content_type)

        try:
            # Send update before LLM call
            self._update_tree(f"Calling LLM for analysis: {url}", url)
            analysis = call_openai_sync(
                prompt=prompt,
                response_format={"type": "json_object"},
                client=openai_client
            )
            analysis_data = json.loads(analysis)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            self._update_tree(f"Retrying analysis with different model: {url}", url)
            analysis = call_openai_sync(
                prompt=prompt,
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                client=openai_client
            )
            analysis_data = json.loads(analysis)

        logger.info("✅ Page analysis complete")
        self.log_update_callback("✅ Page analysis complete")
        logger.info(f"📄 Page type: {analysis_data.get('page_type', 'unknown')}")
        logger.info(f"🎯 Relevance score: {analysis_data.get('relevance_score', 0)}")

        # Check page usefulness assessment
        usefulness_assessment = analysis_data.get('page_usefulness_assessment', {})
        is_useful_page = usefulness_assessment.get('is_useful_page', True)
        needs_code_generation = usefulness_assessment.get('needs_code_generation', True)
        skip_processing = usefulness_assessment.get('skip_processing', False)
        skip_reason = usefulness_assessment.get('skip_reason', '')
        
        # Log page usefulness assessment
        logger.info(f"📊 Page usefulness assessment:")
        logger.info(f"   - Is useful page: {is_useful_page}")
        logger.info(f"   - Needs code generation: {needs_code_generation}")
        logger.info(f"   - Skip processing: {skip_processing}")
        if skip_reason:
            logger.info(f"   - Skip reason: {skip_reason}")
        
        # Send real-time update with analysis data (including python_code)
        self._update_tree_with_analysis_data(url, analysis_data, "Page analysis complete")

        # Handle code execution based on page usefulness
        code_execution_result = None
        code_execution_error = None
        
        if skip_processing:
            logger.info(f"⏭️ Skipping code generation and execution for {url}: {skip_reason}")
            self.log_update_callback(f"⏭️ Skipping processing for {url}: {skip_reason}")
            self._update_tree(f"Skipped processing: {skip_reason}", url)
            code_execution_error = f"Page skipped: {skip_reason}"
        elif not needs_code_generation:
            logger.info(f"📝 No code generation needed for {url} (navigation/intermediate page)")
            self.log_update_callback(f"📝 No code generation needed for {url}")
            self._update_tree(f"No code generation needed (navigation page)", url)
            code_execution_error = "No code generation needed for this page type"
        else:
            # Execute and validate generated code only if needed
            logger.info(f"🔧 Executing generated code for {url}")
            self.log_update_callback(f"🔧 Executing generated code for {url}")
            code_execution_result, code_execution_error = await self._execute_generated_code(
                analysis_data, url
            )

        # Update plan with available fields
        self._update_tree(f"Updating extraction plan: {url}", url)
        self._update_plan_with_fields(analysis_data)

        # Filter next pages to visit
        next_pages_to_visit = self._filter_next_pages(analysis_data)

        # Send final update with all data including execution results
        final_result = {
            "structured_data": analysis_data.get("structured_data", {}),
            "main_content_areas": analysis_data.get("main_content_areas", []),
            "navigation_elements": analysis_data.get("navigation_elements", []),
            "patterns_identified": analysis_data.get("patterns_identified", []),
            "next_pages_to_visit": next_pages_to_visit,
            "page_type": analysis_data.get("page_type", "unknown"),
            "relevance_score": analysis_data.get("relevance_score", 0),
            "available_fields": analysis_data.get("available_fields", []),
            "generic_name_of_page": analysis_data.get("generic_name_of_page", ""),
            "python_code": analysis_data.get("python_code"),
            "python_code_function_name": analysis_data.get("python_code_function_name", "extract_data"),
            "exclusive_fields": analysis_data.get("exclusive_fields", []),
            "code_execution_result": code_execution_result,
            "code_execution_error": code_execution_error,
            "summery": analysis_data.get("summery", ""),
            "pagination_info": analysis_data.get("pagination_info", {}),
            "page_usefulness_assessment": usefulness_assessment
        }
        
        # Send real-time update with execution results
        self._update_tree_with_execution_results(url, final_result, "Analysis complete")
        
        return final_result

    def _update_tree_with_analysis_data(self, url: str, analysis_data: Dict[str, Any], message: str) -> None:
        """Send real-time tree update with analysis data (including python_code)."""
        if not self.tree_update_callback:
            return
            
        # Find the page in the tree
        page_data = self.page_tree.get(url)
        if not page_data:
            return
            
        # Update page data with analysis results
        page_data.analysis_data = analysis_data
        page_data.page_type = analysis_data.get("page_type", "unknown")
        page_data.exclusive_fields = analysis_data.get("exclusive_fields", [])
        page_data.generated_code = analysis_data.get("python_code")
        page_data.relevance_score = analysis_data.get("relevance_score", 0)
        
        # Update status based on page usefulness assessment
        usefulness_assessment = analysis_data.get('page_usefulness_assessment', {})
        skip_processing = usefulness_assessment.get('skip_processing', False)
        needs_code_generation = usefulness_assessment.get('needs_code_generation', True)
        
        if skip_processing:
            skip_reason = usefulness_assessment.get('skip_reason', 'No reason provided')
            page_data.processing_status = "skipped"
            page_data.status_message = f"Skipped: {skip_reason}"
            page_data.progress = 100  # Mark as complete since it's skipped
        elif not needs_code_generation:
            page_data.processing_status = "completed"
            page_data.status_message = "No code generation needed (navigation page)"
            page_data.progress = 100  # Mark as complete since no code needed
        else:
            page_data.processing_status = "processing"
            page_data.status_message = message or "Analysis complete, generating code..."
            page_data.progress = 60  # 60% progress after analysis
        
        # Force immediate update for important data
        self._force_tree_update_with_data(url, message, page_data.progress)

    def _update_tree_with_execution_results(self, url: str, final_result: Dict[str, Any], message: str) -> None:
        """Send real-time tree update with execution results."""
        if not self.tree_update_callback:
            return
            
        # Find the page in the tree
        page_data = self.page_tree.get(url)
        if not page_data:
            return
            
        # Update page data with execution results
        page_data.code_execution_result = final_result.get("code_execution_result")
        page_data.code_execution_error = final_result.get("code_execution_error")
        
        # Force immediate update for important data
        self._force_tree_update_with_data(url, message, 100)  # 100% progress after execution

    def _force_tree_update_with_data(self, url: str, message: str, progress: int) -> None:
        """Force an immediate tree update with data, bypassing throttling."""
        if not self.tree_update_callback:
            return
            
        try:
            # Always try to serialize the tree, even if tree_root is None
            tree_data = None
            if self.tree_root:
                tree_data = self._serialize_tree(self.tree_root)
            else:
                # Create a minimal tree structure if no root exists yet
                tree_data = {
                    'url': self.root_url,
                    'page_type': 'initializing',
                    'relevance_score': 0.0,
                    'exclusive_fields': [],
                    'children': [],
                    'parent_url': None,
                    'label': 'Initializing...',
                    'status': 'pending',
                    'status_message': message or 'Initializing parser...',
                    'progress': 0,
                    'processing_time': None,
                    'last_update': None,
                    'error_details': None,
                    'summery': '',
                    'python_code': '',
                    'code_execution_result': '',
                    'code_execution_error': '',
                    'analysis_data': {}
                }
            
            # Update progress and status message for the specific page
            if url and progress is not None:
                self._update_page_progress(tree_data, url, progress)
                
            if url and message:
                self._update_page_status_message(tree_data, url, message)
                
            # Force immediate callback
            self.tree_update_callback(tree_data)
            
        except Exception as e:
            logger.warning(f"Force tree update callback error: {e}")
            # Try to send a minimal error tree update
            try:
                error_tree = {
                    'url': self.root_url,
                    'page_type': 'error',
                    'relevance_score': 0.0,
                    'exclusive_fields': [],
                    'children': [],
                    'parent_url': None,
                    'label': 'Error occurred',
                    'status': 'error',
                    'status_message': f'Force tree update error: {str(e)}',
                    'progress': 0,
                    'processing_time': None,
                    'last_update': None,
                    'error_details': {'error_type': 'TreeUpdateError', 'error_message': str(e)},
                    'summery': '',
                    'python_code': '',
                    'code_execution_result': '',
                    'code_execution_error': '',
                    'analysis_data': {}
                }
                self.tree_update_callback(error_tree)
            except Exception as fallback_error:
                logger.error(f"Failed to send error tree update: {fallback_error}")

    def _build_page_analysis_prompt(
        self, 
        content: str, 
        url: str, 
        parent_page: Optional[PageData],
        content_type: str = "html",
    ) -> str:
        """
        Build the prompt for page analysis, using either HTML or Markdown as input.
        Args:
            content: The HTML or Markdown content to analyze
            url: The page URL
            parent_page: The parent PageData (if any)
            content_type: "html" or "markdown" (for prompt labeling)
        Returns:
            The prompt string for the LLM
        """
        pagination_instructions = ""
        if self.requirement.pagination:
            pagination_instructions = """
        PAGINATION HANDLING:
        - If pagination is enabled, look for pagination elements like:
          * Next/Previous buttons
          * Page numbers
          * "Load more" buttons
          * Infinite scroll indicators
        - Include pagination URLs in next_pages_to_visit with high relevance scores
        - Identify pagination patterns and include them in patterns_identified
        - Add pagination-related fields to available_fields if found
        - Generate pagination-aware Python code that can handle multiple pages
        - Populate pagination_info with detailed pagination analysis:
          * Detect pagination type (url_based, javascript_based, infinite_scroll, load_more, none)
          * Identify CSS selectors for pagination elements
          * Extract URL patterns and parameters for URL-based pagination
          * Determine JavaScript actions needed for dynamic pagination
          * Estimate total pages and items per page
          * Identify current page number if possible
        - **CRITICAL: All pagination_actions must contain valid JavaScript code, NOT natural language descriptions**
        - **JavaScript examples for pagination_actions:**
          * click_next: "document.querySelector('.next-button').click()"
          * scroll_to_load: "window.scrollTo(0, document.body.scrollHeight)"
          * wait_for_load: "new Promise(resolve => setTimeout(resolve, 2000))"
        - **DO NOT use natural language like "scroll down to load more companies" - this will cause JavaScript syntax errors**
        - **CRITICAL: Do NOT use 'await' in JavaScript code - it runs in non-async context in Playwright**
        - **Use Promise-based waiting instead of await:**
          * Correct: "new Promise(resolve => setTimeout(resolve, 2000))"
          * Wrong: "await new Promise(resolve => setTimeout(resolve, 2000))"
        """
        
        label = "Markdown Content:" if content_type == "markdown" else "HTML Content:"
        
        # Build content-type specific instructions
        if content_type == "markdown":
            fetch_instructions = """
        1. For MARKDOWN extraction, use the appropriate fetch method:
           from utils.fetch_html_playwright import _fetch_and_clean, html_to_markdown
           html_code = await _fetch_and_clean(url)
           markdown_code = html_to_markdown(html_code)
        """
            parsing_instructions = """
        4. For MARKDOWN parsing:
           - Use BeautifulSoup for HTML parsing: soup = BeautifulSoup(html_code, 'html.parser')
           - Convert to markdown for analysis: markdown_code = html_to_markdown(html_code)
           - Use markdown parsing libraries or regex for markdown content analysis
           - Focus on markdown structure (headers, links, lists, etc.) rather than HTML tags
        """
            selector_instructions = """
        15. **IMPORTANT for MARKDOWN parsing:** 
           - Use markdown parsing libraries like 'markdown' or 'mistune' for structured markdown analysis
           - Use regex patterns for extracting specific markdown elements (headers, links, lists)
           - Parse markdown headers using patterns like r'^#+\s+(.+)$'
           - Extract markdown links using patterns like r'\[([^\]]+)\]\(([^)]+)\)'
           - Handle markdown lists and other structural elements appropriately
        """
            content_specific_instructions = """
        12. For MARKDOWN extraction, use appropriate parsing methods:
            - Use regex for markdown pattern matching
            - Use markdown parsing libraries for structured analysis
            - Handle markdown-specific elements (headers, links, lists, code blocks)
        """
        else:
            fetch_instructions = """
        1. Always use _fetch_and_clean with url for fetching HTML code: from utils.fetch_html_playwright import _fetch_and_clean
           html_code = await _fetch_and_clean(url) # this using Playwright
        """
            parsing_instructions = """
        4. Use BeautifulSoup for parsing
        """
            selector_instructions = """
        15. **IMPORTANT for BeautifulSoup selectors:** When using BeautifulSoup's select or select_one, always use valid CSS selectors supported by BeautifulSoup's parser. Attribute values must be quoted (e.g., [data-test="post-name-"]), and do NOT use selectors with bracketed class names as these will cause parse errors. If you need to match such classes, use soup.find or soup.find_all with class_ parameter instead.
        """
            content_specific_instructions = """
        12. To match elements that have ALL specified classes (order doesn't matter): soup.find_all('div', class_=['class1', 'class2'])
        13. Attribute Selectors: Always quote attribute values in CSS selectors: soup.find('div', class_='example-class')
        """

        return f"""
        Analyze this {content_type.upper()} content of a webpage and provide comprehensive analysis in one JSON response.

        Context:
        - Target URL: {url}
        - Required Data to Extract: {self.requirement.data_to_extract}
        - Additional Instructions: {self.requirement.additional_instructions}
        - Main Plan: {json.dumps(self.plan, indent=2)}
        - Already Visited Page Types: {self.visited_page_types}
        - Parent Page Type: {parent_page.page_type if parent_page else 'None'}
        - Pagination Enabled: {self.requirement.pagination}

        {label}
        {content[:500_000]}

        Return a JSON object with the following structure:
        {{
            "structured_data": "Convert the {content_type.upper()} to structured JSON format to achieve main plan",
            "main_content_areas": "List of main content areas found",
            "navigation_elements": "List of navigation elements found", 
            "patterns_identified": "Data patterns identified in the page",
            "summery": "summary of the page as per requirement",
            "next_pages_to_visit": [
                {{
                    "url": "full URL",
                    "label": <page label>,
                    "page_type": <page type>,
                    "identifier": <unique identifier>,
                    "relevance_score": <from 0.0 to 1.0>
                    "why": <why this page needed>
                    
                }}
            ],
            "page_type": "page type",
            "relevance_score": <from 0.0 to 1.0>,
            "available_fields": ["list of fields available for extraction"],
            "generic_name_of_page": <generic name for this page>,
            "python_code": <Python code to extract data from this page>,
            "python_code_function_name": <name of the main extraction function>,
            
            "page_usefulness_assessment": {{
                "is_useful_page": <boolean - true if page contains required data or is essential for extraction>,
                "needs_code_generation": <boolean - true if page requires Python code to extract meaningful data>,
                "is_navigation_page": <boolean - true if page is mainly navigation/menu/intermediate>,
                "is_data_page": <boolean - true if page contains actual data to extract>,
                "is_landing_page": <boolean - true if page is a landing/home page>,
                "usefulness_reason": <detailed explanation of why page is useful or not>,
                "skip_processing": <boolean - true if page should be skipped entirely (no code generation, no further processing)>,
                "skip_reason": <explanation for why page should be skipped>
            }},
            
            "pagination_info": {{
                "has_pagination": <boolean indicating if pagination is detected>,
                "pagination_type": <"url_based", "javascript_based", "infinite_scroll", "load_more", "none">,
                "pagination_selectors": {{
                    "next_button": <CSS selector for next button>,
                    "previous_button": <CSS selector for previous button>,
                    "page_numbers": <CSS selector for page number links>,
                    "load_more_button": <CSS selector for load more button>,
                    "pagination_container": <CSS selector for pagination container>
                }},
                "pagination_patterns": {{
                    "url_pattern": <URL pattern for pagination if URL-based>,
                    "page_param": <URL parameter name for page number>,
                    "offset_param": <URL parameter name for offset>,
                    "limit_param": <URL parameter name for limit>
                }},
                "pagination_actions": {{
                    "click_next": <Valid JavaScript code to click next button, e.g., "document.querySelector('.next-button').click()">,
                    "scroll_to_load": <Valid JavaScript code for infinite scroll, e.g., "window.scrollTo(0, document.body.scrollHeight)">,
                    "wait_for_load": <Valid JavaScript code to wait for content, e.g., "new Promise(resolve => setTimeout(resolve, 2000))">
                }},
                "total_pages_estimate": <estimated total number of pages>,
                "items_per_page": <estimated number of items per page>,
                "current_page": <current page number if detectable>
            }}
        }}

        **CRITICAL PAGE USEFULNESS ASSESSMENT RULES:**
        1. **is_useful_page**: Set to true if:
           - Page contains actual data matching required_data_to_extract
           - Page is essential for navigation to data pages
           - Page contains pagination controls for data pages
           - Page is a landing page that leads to data pages
           - Page contains search/filter functionality for data
        
        2. **needs_code_generation**: Set to true if:
           - Page contains structured data that needs extraction
           - Page has forms, lists, tables, or structured content
           - Page contains the actual target data (not just navigation)
           - Page requires parsing logic to extract meaningful information
        
        3. **is_navigation_page**: Set to true if:
           - Page is mainly menus, navigation links, breadcrumbs
           - Page contains only links to other pages
           - Page is a sitemap or directory listing
           - Page has no structured data, only navigation elements
        
        4. **is_data_page**: Set to true if:
           - Page contains actual data records, products, articles, etc.
           - Page has structured content that matches extraction requirements
           - Page contains lists, tables, cards, or other data containers
        
        5. **skip_processing**: Set to true if:
           - Page is completely irrelevant to extraction goals
           - Page is an error page, 404, or broken link
           - Page is a login/authentication page with no public data
           - Page is a terms of service, privacy policy, or legal page
           - Page contains only ads, tracking scripts, or non-content elements
           - Page is a redirect page with no meaningful content
        
        6. **relevance_score**: Score from 0.0 to 1.0 based on:
           - 0.9-1.0: Direct data pages with required information
           - 0.7-0.8: Important navigation pages leading to data
           - 0.5-0.6: Intermediate pages with some relevance
           - 0.3-0.4: Pages with minimal relevance
           - 0.0-0.2: Pages that should be skipped

        Rules for next_pages_to_visit:
        1. Provide one url for each page_type, other urls have same html structure so they can call same html parsing function
        2. Provide only full URLs that actually exist in the HTML
        3. Don't include already visited URLs or page types
        4. Don't provide placeholder URLs
        5. Relevance score should be based on:
           - How likely the page contains required data
           - How unique the page type is
           - How deep the page is in the site structure
        6. DO NOT hallucinate URLs or page types - only use what exists in the HTML
        
        {pagination_instructions}

        Rules for python_code:
        {fetch_instructions}
        2. Write Python code to extract all required information in structured data
        3. The function should be async and take a url parameter
        {parsing_instructions}
        5. Include proper error handling and logging
        6. Use type hints for all functions
        7. Add docstrings for all functions
        8. Follow PEP 8 style guidelines
        9. Handle rate limiting and retries
        10. Include proper exception handling
        11. DO NOT hallucinate data - only extract what exists in the {content_type.upper()}
        12. Validate extracted data against {content_type.upper()} content
        13. Add logging for any assumptions made
        14. Add verification steps for extracted data
        {selector_instructions}
        16. **CRITICAL DEPENDENCY REQUIREMENTS:**
            - Use ONLY basic Pydantic BaseModel with standard field types (str, int, bool, float, List, Dict, Optional)
            - DO NOT use EmailStr, HttpUrl, or any other Pydantic field types that require additional packages
            - DO NOT use pydantic[email] or any optional Pydantic dependencies
            - Use str for email fields, not EmailStr
            - Use str for URL fields, not HttpUrl
            - Use basic validation with Field() if needed, but avoid complex validators
            - Only use standard library imports and basic required packages (asyncio, json, os, argparse, logging, typing, bs4, aiohttp, pydantic)
            - DO NOT import any packages that require additional installation beyond the basic requirements
            - Avoid any imports that might cause "ImportError: package is not installed" errors
        17. **CRITICAL JSON SERIALIZATION REQUIREMENTS:**
            - The function MUST return a dictionary (dict), NOT a Pydantic model object
            - If you use Pydantic models for data validation, convert them to dictionaries before returning
            - Use .model_dump() or .dict() method to convert Pydantic models to dictionaries
            - Example: return model.model_dump() instead of return model
            - All returned data must be JSON serializable (dict, list, str, int, float, bool, None)
            - DO NOT return Pydantic model objects directly as they cause "Object of type X is not JSON serializable" errors
            - Test that your return value can be serialized with json.dumps() before returning
            - EXAMPLE: If you create a Pydantic model like:
              ```python
              class ExtractedData(BaseModel):
                  title: str
                  description: str
                  url: str
              
              # WRONG - returns Pydantic object
              return ExtractedData(title="test", description="test", url="test")
              
              # CORRECT - returns dictionary
              data = ExtractedData(title="test", description="test", url="test")
              return data.model_dump()
              ```

        {f'18. Build upon existing code from parent page: {parent_page.page_type}' if parent_page else ''}
        {f'19. Parent page code: {parent_page.analysis_data["python_code"]}' if parent_page and parent_page.analysis_data else ''}

        IMPORTANT: 
        1. Your response MUST be valid JSON
        2. Ensure all strings are properly quoted and brackets are balanced
        3. All required fields must be present
        4. All values must match their specified types
        5. Relevance scores must be between 0.0 and 1.0
        6. URLs must be absolute and valid
        7. Python code must be valid and follow all specified rules
        8. DO NOT hallucinate any data - only use what exists in the {content_type.upper()}
        9. Verify all extracted data against the {content_type.upper()} content
        10. Add validation steps to ensure data accuracy
        11. {sample_of_playwright_usage}
        {content_specific_instructions}
        """

    async def _execute_generated_code(
        self, 
        analysis_data: Dict[str, Any], 
        url: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Execute and validate the generated code for a page."""
        generated_code = analysis_data.get('python_code')
        function_name = analysis_data.get('python_code_function_name', 'extract_data')

        if not generated_code:
            return None, None

        max_attempts = 4
        current_attempt = 0
        last_error = None

        while current_attempt < max_attempts:
            try:
                current_attempt += 1
                logger.info(f"🔄 Attempt {current_attempt}/{max_attempts} to execute code for {url}")
                self.log_update_callback(f"🔄 Attempt {current_attempt}/{max_attempts} to execute code for {url}")
                self._update_tree(f"Executing code (attempt {current_attempt}/{max_attempts}): {url}", url)

                # Send update before code execution
                self._update_tree(f"Running generated code: {url}", url)

                result = await self._run_code_module(generated_code, function_name, url)
                if result:
                    logger.info(f"✅ Code execution successful for {url}")
                    self.log_update_callback(f"✅ Code execution successful for {url}")
                    logger.debug(f"📊 Result: {json.dumps(result, indent=2)}")
                    
                    # Send real-time update with execution result
                    self._update_tree_with_code_result(url, result, None, "Code execution successful")
                    
                    return result, None
                else:
                    raise Exception("Empty result")

            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Error in attempt {current_attempt}: {last_error}")
                self.log_update_callback(f"❌ Error in attempt {current_attempt}: {last_error}")
                self._update_tree(f"Code execution failed (attempt {current_attempt}): {url}", url)
                
                if current_attempt < max_attempts:
                    self._update_tree(f"Fixing code (attempt {current_attempt}): {url}", url)
                    generated_code = await self._fix_generated_code(
                        generated_code, last_error, function_name, current_attempt
                    )
                else:
                    logger.error(f"❌ Max attempts ({max_attempts}) reached. Could not fix the code.")
                    self.log_update_callback(f"❌ Max attempts ({max_attempts}) reached. Could not fix the code.")
                    
                    # Send real-time update with error
                    self._update_tree_with_code_result(url, None, last_error, f"Failed after {max_attempts} attempts")
                    break

        return None, f"Failed after {current_attempt} attempts. Last error: {last_error}"

    async def _run_code_module(
        self, 
        code: str, 
        function_name: str, 
        url: str
    ) -> Optional[Dict[str, Any]]:
        """Run the generated code in a temporary module."""
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            try:
                f.write(code.encode())
                f.flush()

                spec = importlib.util.spec_from_file_location("page_extractor", f.name)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, function_name):
                    result = await getattr(module, function_name)(url)
                    
                    # Validate that the result is JSON serializable
                    try:
                        json.dumps(result)
                        return result
                    except (TypeError, ValueError) as json_error:
                        logger.warning(f"⚠️ Result is not JSON serializable: {json_error}")
                        logger.warning(f"⚠️ Result type: {type(result)}")
                        
                        # Try to convert Pydantic models to dictionaries
                        if hasattr(result, 'model_dump'):
                            try:
                                converted_result = result.model_dump()
                                json.dumps(converted_result)  # Test serialization
                                logger.info("✅ Converted Pydantic model to dictionary")
                                return converted_result
                            except Exception as convert_error:
                                logger.error(f"❌ Failed to convert Pydantic model: {convert_error}")
                        elif hasattr(result, 'dict'):
                            try:
                                converted_result = result.dict()
                                json.dumps(converted_result)  # Test serialization
                                logger.info("✅ Converted Pydantic model to dictionary using .dict()")
                                return converted_result
                            except Exception as convert_error:
                                logger.error(f"❌ Failed to convert Pydantic model using .dict(): {convert_error}")
                        
                        # If conversion fails, return a basic structure
                        logger.warning("⚠️ Returning basic structure due to serialization issues")
                        return {
                            "error": "Result not JSON serializable",
                            "original_type": str(type(result)),
                            "serialization_error": str(json_error),
                            "data": str(result) if result else None
                        }
                else:
                    raise AttributeError(f"Function '{function_name}' not found in generated code")
            finally:
                try:
                    os.unlink(f.name)
                except OSError:
                    pass

    async def _fix_generated_code(
        self, 
        code: str, 
        error: str, 
        function_name: str, 
        attempt: int
    ) -> str:
        """Attempt to fix the generated code using LLM."""
        fix_prompt = f"""
        Fix the following Python code that failed to execute with error: {error}

        Original code:
        {code}

        Requirements:
        1. The code should extract data from the HTML
        2. It should handle the error: {error}
        3. It should return a dictionary with the extracted data
        4. Use BeautifulSoup for parsing
        5. Previous attempts: {attempt}/4
        6. The function must be named exactly '{function_name}'
        7. Include proper error handling and logging
        8. Use type hints for all functions
        9. Add docstrings for all functions
        10. Follow PEP 8 style guidelines
        11. Handle rate limiting and retries
        12. Include proper exception handling
        13. DO NOT hallucinate data - only extract what exists in the HTML
        14. Add validation steps for extracted data
        15. Add logging for any assumptions made
        16. **CRITICAL JSON SERIALIZATION REQUIREMENTS:**
            - The function MUST return a dictionary (dict), NOT a Pydantic model object
            - If you use Pydantic models for data validation, convert them to dictionaries before returning
            - Use .model_dump() or .dict() method to convert Pydantic models to dictionaries
            - Example: return model.model_dump() instead of return model
            - All returned data must be JSON serializable (dict, list, str, int, float, bool, None)
            - DO NOT return Pydantic model objects directly as they cause "Object of type X is not JSON serializable" errors
            - Test that your return value can be serialized with json.dumps() before returning

        CRITICAL DEPENDENCY REQUIREMENTS:
        17. **Pydantic Usage Restrictions:**
            - Use ONLY basic Pydantic BaseModel with standard field types (str, int, bool, float, List, Dict, Optional)
            - DO NOT use EmailStr, HttpUrl, or any other Pydantic field types that require additional packages
            - DO NOT use pydantic[email] or any optional Pydantic dependencies
            - Use str for email fields, not EmailStr
            - Use str for URL fields, not HttpUrl
            - Use basic validation with Field() if needed, but avoid complex validators
        18. **Import Restrictions:**
            - Only use standard library imports and basic required packages (asyncio, json, os, argparse, logging, typing, bs4, aiohttp, pydantic)
            - DO NOT import any packages that require additional installation beyond the basic requirements
            - Avoid any imports that might cause "ImportError: package is not installed" errors

        Return only the fixed Python code without any explanations.
        IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
        """

        try:
            fixed_code = call_openai_sync(
                prompt=fix_prompt,
                model="gpt-4.1",
                response_format={"type": "text"},
                client=openai_client
            )
            logger.info(f"🔄 Generated fixed code for attempt {attempt + 1}")
            return fixed_code
        except Exception as fix_error:
            logger.error(f"❌ Failed to generate fixed code: {str(fix_error)}")
            return code

    def _update_plan_with_fields(self, analysis_data: Dict[str, Any]) -> None:
        """Update the plan with available fields from the analysis."""
        available_fields = analysis_data.get('available_fields', [])
        exclusive_fields = list(set(available_fields) - set(self.plan.get("already_extracted_fields", [])))
        
        self.plan["already_extracted_fields"] = list(
            set(self.plan.get("already_extracted_fields", [])).union(set(available_fields))
        )
        self.plan['to_be_extracted_fields'] = list(
            set(self.plan.get('to_be_extracted_fields', [])) - set(self.plan["already_extracted_fields"])
        )

    def _filter_next_pages(self, analysis_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter next pages to visit based on relevance, visited status, and page usefulness assessment."""
        next_pages_to_visit = analysis_data.get('next_pages_to_visit', [])
        unvisited_pages = []

        # Parse the root domain
        root_domain = urlparse(self.root_url).netloc.lower()

        for page in next_pages_to_visit:
            page_url = page.get("url", "")
            page_domain = urlparse(page_url).netloc.lower()
            
            # Check if page meets basic criteria
            if (
                page.get("relevance_score", 0) >= 0.8 and
                page.get("page_type") not in self.visited_page_types and
                page_url not in self.visited_urls
                #     and
                # page_domain == root_domain
            ):
                # Additional check: if this page was already analyzed and marked for skipping,
                # don't add it to the visit list
                if page_url in self.page_tree:
                    existing_page = self.page_tree[page_url]
                    usefulness_assessment = existing_page.analysis_data.get('page_usefulness_assessment', {}) if existing_page.analysis_data else {}
                    skip_processing = usefulness_assessment.get('skip_processing', False)
                    
                    if skip_processing:
                        logger.info(f"⏭️ Skipping already analyzed page marked for skipping: {page_url}")
                        continue
                
                unvisited_pages.append(page)
                self.visited_page_types.add(page["page_type"])
                self.visited_urls.add(page["url"])

        logger.debug(f"🔗 Next pages to visit: {json.dumps(dict(next_visit_pages=unvisited_pages), indent=2)}")
        return unvisited_pages

    def _update_tree(self, message: str = None, page_url: str = None, progress: int = None) -> None:
        """
        Helper method to update the tree visualization with throttling.
        
        Args:
            message: Optional status message to display
            page_url: URL of the page being updated
            progress: Optional progress value (0-100)
        """
        if not self.tree_update_callback:
            return
            
        import time
        current_time = time.time()
        
        # Throttle updates to prevent overwhelming the UI
        if current_time - self.last_tree_update < self.tree_update_throttle:
            self.pending_tree_update = True
            return
            
        self.last_tree_update = current_time
        self.pending_tree_update = False
            
        try:
            # Always try to serialize the tree, even if tree_root is None
            tree_data = None
            if self.tree_root:
                tree_data = self._serialize_tree(self.tree_root)
            else:
                # Create a minimal tree structure if no root exists yet
                tree_data = {
                    'url': self.root_url,
                    'page_type': 'initializing',
                    'relevance_score': 0.0,
                    'exclusive_fields': [],
                    'children': [],
                    'parent_url': None,
                    'label': 'Initializing...',
                    'status': 'pending',
                    'status_message': message or 'Initializing parser...',
                    'progress': 0,
                    'processing_time': None,
                    'last_update': None,
                    'error_details': None,
                    'summery': '',
                    'python_code': '',
                    'code_execution_result': '',
                    'code_execution_error': '',
                    'analysis_data': {}
                }
            
            # Only set global status message if no specific page_url is provided
            if message and not page_url:
                tree_data['status_message'] = message
                
            if page_url and progress is not None:
                # Update progress in the tree data for the specific page
                self._update_page_progress(tree_data, page_url, progress)
                
            # If we have a specific page_url and message, update that node's status message
            if page_url and message:
                self._update_page_status_message(tree_data, page_url, message)
                
            self.tree_update_callback(tree_data)
            
        except Exception as e:
            logger.warning(f"Tree update callback error: {e}")
            # Try to send a minimal error tree update
            try:
                error_tree = {
                    'url': self.root_url,
                    'page_type': 'error',
                    'relevance_score': 0.0,
                    'exclusive_fields': [],
                    'children': [],
                    'parent_url': None,
                    'label': 'Error occurred',
                    'status': 'error',
                    'status_message': f'Tree update error: {str(e)}',
                    'progress': 0,
                    'processing_time': None,
                    'last_update': None,
                    'error_details': {'error_type': 'TreeUpdateError', 'error_message': str(e)},
                    'summery': '',
                    'python_code': '',
                    'code_execution_result': '',
                    'code_execution_error': '',
                    'analysis_data': {}
                }
                self.tree_update_callback(error_tree)
            except Exception as fallback_error:
                logger.error(f"Failed to send error tree update: {fallback_error}")
    
    def _update_page_status_message(self, tree_data: Dict[str, Any], page_url: str, message: str) -> None:
        """Update status message for a specific page in the tree data."""
        def update_node(node):
            if node.get('url') == page_url:
                node['status_message'] = message
                return True  # Found and updated, stop searching
            for child in node.get('children', []):
                if update_node(child):
                    return True  # Found in child, stop searching
            return False  # Not found in this branch
        
        update_node(tree_data)

    def _update_page_progress(self, tree_data: Dict[str, Any], page_url: str, progress: int) -> None:
        """Update progress for a specific page in the tree data."""
        def update_node(node):
            if node.get('url') == page_url:
                node['progress'] = progress
                return True  # Found and updated, stop searching
            for child in node.get('children', []):
                if update_node(child):
                    return True  # Found in child, stop searching
            return False  # Not found in this branch
        
        update_node(tree_data)

    def _update_page_status(self, page: PageData, status: str, message: str, progress: int = None, error: Dict[str, Any] = None) -> None:
        """
        Update the status of a page.
        
        Args:
            page: The PageData object to update
            status: New status (pending, processing, completed, error)
            message: Status message
            progress: Optional progress value (0-100)
            error: Optional error details
        """
        import time
        current_time = time.time()
        
        if page.start_time is None:
            page.start_time = current_time
        
        page.processing_status = status
        page.status_message = message
        page.last_update_time = current_time
        
        if progress is not None:
            page.progress = progress
        
        if error:
            page.error_details = error
            page.processing_status = "error"
        
        # Only update tree for this specific page, not parent
        self._update_tree(message, page.url, progress)

    async def fetch_and_process_page(self, url: str, path: Optional[List[str]] = None, parent: PageData|None = None, use_markdown_for_llm: bool = False) -> PageData:
        """
        Fetch and process a page, returning PageData with analysis results.
        
        Args:
            url: URL of the page to fetch and process
            path: Breadcrumb path from root to this page
            
        Returns:
            PageData object containing all analysis and processing results
        """
        logger.info(f"📥 Fetching page: {url}")
        if path is None:
            path = [url]

        # Create initial page data with pending status
        page_data = PageData(
            url=url,
            html="",
            json_data={},
            path=path,
            children=[],
            page_type="pending",
            relevance_score=0.0
        )
        if parent:
            parent.children.append(page_data)
        page_data.parent = parent
        
        # Add to tree immediately to show pending state
        if self.root_url == url:
            self.tree_root = page_data
        self.page_tree[url] = page_data
        self._update_page_status(page_data, "pending", f"Initializing {url}", 0)

        try:
            # Fetch HTML
            self._update_page_status(page_data, "processing", f"Fetching HTML from {url}", 10)
            html = await _fetch_and_clean(url)
            logger.info(f"📄 Fetched HTML content ({len(html)} bytes)")
            page_data.html = html
            # Convert HTML to Markdown for possible LLM use
            page_data.markdown = html_to_markdown(html)
            logger.info(f"HTML length: {len(html)} | Markdown length: {len(page_data.markdown) if page_data.markdown else 0}")
            self._update_page_status(page_data, "processing", f"HTML fetched ({len(html)} bytes)", 20)

            # Analyze page directly
            self._update_page_status(page_data, "processing", f"Analyzing page structure", 30)
            analysis = await self.analyze_page_directly(html=html, markdown=page_data.markdown, url=url, parent_page=parent, use_markdown_for_llm=use_markdown_for_llm)
            page_data.analysis_data = analysis
            self._update_page_status(page_data, "processing", f"Page analysis complete", 60)

            # Ensure proper data types
            structured_data = analysis.get("structured_data", {})
            if not isinstance(structured_data, dict):
                logger.warning(f"⚠️ Warning: structured_data is not a dict, converting: {type(structured_data)}")
                structured_data = {"data": structured_data} if structured_data else {}

            code_execution_result = analysis.get("code_execution_result")
            if code_execution_result is not None and not isinstance(code_execution_result, dict):
                logger.warning(f"⚠️ Warning: code_execution_result is not a dict, converting: {type(code_execution_result)}")
                code_execution_result = {"result": code_execution_result} if code_execution_result else None

            code_execution_error = analysis.get("code_execution_error")
            if code_execution_error is not None and not isinstance(code_execution_error, str):
                logger.warning(f"⚠️ Warning: code_execution_error is not a string, converting: {type(code_execution_error)}")
                code_execution_error = str(code_execution_error) if code_execution_error else None

            # Update page data with results
            self._update_page_status(page_data, "processing", f"Processing analysis results", 80)
            page_data.json_data = structured_data
            page_data.page_type = analysis.get("page_type")
            page_data.exclusive_fields = analysis.get("exclusive_fields", [])
            page_data.generated_code = analysis.get("python_code")
            page_data.code_execution_result = code_execution_result
            page_data.code_execution_error = code_execution_error
            page_data.relevance_score = analysis.get("relevance_score", 0)

            # Send real-time update with all the new data
            self._update_tree_with_page_data(page_data, "Processing analysis results", 80)

            self._update_page_status(page_data, "completed", f"Processing complete", 100)
            
            # Force a final tree update to ensure completion is shown
            self._force_tree_update()
            
            return page_data

        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            }
            self._update_page_status(
                page_data, 
                "error", 
                f"Error processing page: {str(e)}", 
                error=error_details
            )
            raise

    def _serialize_tree(self, node: Optional[PageData]) -> Optional[Dict[str, Any]]:
        """
        Recursively serialize the PageData tree for UI visualization.
        
        Args:
            node: Root node of the tree to serialize
            
        Returns:
            Dictionary representation of the tree for UI consumption
        """
        if not node:
            return None

        import time
        current_time = time.time()
        processing_time = (
            round(current_time - node.start_time, 2)
            if node.start_time is not None
            else None
        )
        last_update = (
            round(current_time - node.last_update_time, 2)
            if node.last_update_time is not None
            else None
        )
        
        return {
            'url': node.url,
            'page_type': node.page_type,
            'relevance_score': node.relevance_score,
            'exclusive_fields': node.exclusive_fields,
            'children': [self._serialize_tree(child) for child in getattr(node, 'children', [])],
            'parent_url': node.parent.url if node.parent else None,
            'label': node.analysis_data.get('generic_name_of_page') if node.analysis_data else node.url,
            'status': node.processing_status,
            'status_message': node.status_message,
            'progress': node.progress,
            'processing_time': processing_time,
            'last_update': last_update,
            'error_details': node.error_details,
            'summery': node.analysis_data.get("summery") if node.analysis_data and "summery" in node.analysis_data else '',
            'python_code': node.generated_code if node.generated_code else '',
            'code_execution_result': node.code_execution_result if node.code_execution_result else '',
            'code_execution_error': node.code_execution_error if node.code_execution_error else '',
            'analysis_data': node.analysis_data if node.analysis_data else {},
            'html': node.html,
            'markdown': node.markdown,
            'page_usefulness_assessment': node.analysis_data.get('page_usefulness_assessment', {}) if node.analysis_data else {},
        }

    async def build_page_tree(
        self, 
        use_markdown_for_llm: bool = False
    ) -> None:
        """
        Build tree of pages starting from root URL.
        
        This method crawls the website starting from the root URL, analyzing
        each page and building a tree structure of relevant pages.
        
        Args:
            log_update_callback: Optional callback for log updates
        """
        self.log_update_callback("🌳 Building page tree...")
        
        if not self.plan:
            plan = await self.analyze_requirement()
            self.plan = plan

        root_page = await self.fetch_and_process_page(self.root_url, use_markdown_for_llm=use_markdown_for_llm)
        self.tree_root = root_page
        self.visited_urls.add(self.root_url)

        async def process_page(page: PageData, depth: int) -> None:
            """Recursively process pages in the tree."""
            if depth >= self.requirement.max_depth:
                msg = f"⏹️ Max Depth Reached: depth={depth} (max_depth={self.requirement.max_depth}). Stopping crawl at {page.url}"
                logger.info(msg)
                if self.log_update_callback:
                    self.log_update_callback(msg)
                # Also send a tree update with a clear status message
                self._update_tree(f"⏹️ Max Depth Reached at {page.url} (depth={depth})", page.url)
                return

            logger.info(f"📑 Processing page at depth {depth}: {page.url} : score: {page.relevance_score}")
            analysis = page.analysis_data
            page.page_type = analysis["page_type"]

            # Emit tree update after processing this node
            self._update_tree(f"Processed page: {page.url} (depth {depth})", page.url)

            next_pages_to_visit = analysis.get('next_pages_to_visit', [])
            if isinstance(next_pages_to_visit, list):
                logger.info(f"🔗 Found {len(next_pages_to_visit)} valid next pages to visit")
                for next_page in next_pages_to_visit:
                    # Prevent fetching child pages if max depth would be exceeded
                    if depth + 1 >= self.requirement.max_depth:
                        msg = f"⏹️ Max Depth Reached: would fetch {next_page['url']} at depth {depth+1} (max_depth={self.requirement.max_depth}), skipping fetch."
                        logger.info(msg)
                        if self.log_update_callback:
                            self.log_update_callback(msg)
                        self._update_tree(msg, page.url)
                        continue
                    logger.info(f"📥 Processing next page: {next_page['label']}::({next_page['relevance_score']}):: {next_page['why']}")
                    child_page = await self.fetch_and_process_page(
                        next_page['url'],
                        path=page.path + [next_page['url']],
                        parent=page,
                        use_markdown_for_llm=use_markdown_for_llm
                    )
                    if child_page.relevance_score >= 0.8:
                        # Send tree update after each child page is processed
                        self._update_tree(f"Added child page: {child_page.url}", child_page.url)
                        await process_page(child_page, depth + 1)
                    else:
                        # Send tree update even for low-relevance pages
                        self._update_tree(f"Skipped low-relevance page: {child_page.url} (score: {child_page.relevance_score})", child_page.url)

        await process_page(root_page, 0)
        logger.info("✅ Page tree building complete")
        logger.info(f"📊 Total pages processed: {len(self.page_tree)}")
        
        # Send final tree update
        self._update_tree(f"Page tree building complete - {len(self.page_tree)} pages processed", self.root_url)

    async def generate_extraction_code(self) -> str:
        """
        Generate Python code for data extraction from all analyzed pages.
        
        This method combines all working code from the page tree and generates
        a comprehensive extraction utility that can be saved and reused.
        
        Returns:
            Generated Python code as a string
            
        Raises:
            ValueError: If no useful pages are found for code generation
        """
        logger.info("💻 Generating extraction code...")
        self.log_update_callback("💻 Generating extraction code...")

        # First, validate that we have useful pages for code generation
        useful_pages = []
        skipped_pages = []
        navigation_pages = []
        
        for url, data in self.page_tree.items():
            usefulness_assessment = data.analysis_data.get('page_usefulness_assessment', {}) if data.analysis_data else {}
            skip_processing = usefulness_assessment.get('skip_processing', False)
            needs_code_generation = usefulness_assessment.get('needs_code_generation', True)
            
            if skip_processing:
                skipped_pages.append({
                    'url': url,
                    'page_type': data.page_type,
                    'reason': usefulness_assessment.get('skip_reason', 'No reason provided')
                })
            elif not needs_code_generation:
                navigation_pages.append({
                    'url': url,
                    'page_type': data.page_type,
                    'reason': 'Navigation/intermediate page - no code generation needed'
                })
            else:
                useful_pages.append({
                    'url': url,
                    'page_type': data.page_type,
                    'has_generated_code': bool(data.generated_code),
                    'has_execution_result': bool(data.code_execution_result),
                    'has_execution_error': bool(data.code_execution_error)
                })
        
        # Log page categorization
        logger.info(f"📊 Page categorization for code generation:")
        logger.info(f"   - Useful pages (need code generation): {len(useful_pages)}")
        logger.info(f"   - Skipped pages: {len(skipped_pages)}")
        logger.info(f"   - Navigation pages: {len(navigation_pages)}")
        
        if useful_pages:
            logger.info(f"   - Useful pages details:")
            for page in useful_pages:
                logger.info(f"     * {page['url']} ({page['page_type']}) - Code: {page['has_generated_code']}, Result: {page['has_execution_result']}, Error: {page['has_execution_error']}")
        
        if skipped_pages:
            logger.info(f"   - Skipped pages details:")
            for page in skipped_pages:
                logger.info(f"     * {page['url']} ({page['page_type']}) - Reason: {page['reason']}")
        
        # Check if we have any pages that actually need code generation
        if not useful_pages:
            error_message = "❌ No useful pages found for code generation. "
            
            if skipped_pages and navigation_pages:
                error_message += f"All {len(skipped_pages) + len(navigation_pages)} pages were either skipped or marked as navigation pages. "
                error_message += f"Skipped pages: {len(skipped_pages)}, Navigation pages: {len(navigation_pages)}. "
                error_message += "Please check the target URL and extraction requirements."
            elif skipped_pages:
                error_message += f"All {len(skipped_pages)} pages were skipped during processing. "
                error_message += "Common reasons: pages are irrelevant, error pages, login required, or no public data available. "
                error_message += "Please verify the target URL and extraction requirements."
            elif navigation_pages:
                error_message += f"All {len(navigation_pages)} pages were marked as navigation/intermediate pages. "
                error_message += "No pages contain actual data that requires code generation. "
                error_message += "Please check if the target URL leads to data pages or adjust extraction requirements."
            else:
                error_message += "No pages were processed. Please check the target URL and extraction requirements."
            
            # Add detailed information for debugging
            error_message += f"\n\nTarget URL: {self.requirement.target_url}"
            error_message += f"\nRequired data to extract: {self.requirement.data_to_extract}"
            error_message += f"\nAdditional instructions: {self.requirement.additional_instructions}"
            
            if skipped_pages:
                error_message += f"\n\nSkipped pages:"
                for page in skipped_pages[:5]:  # Show first 5 skipped pages
                    error_message += f"\n- {page['url']} ({page['page_type']}): {page['reason']}"
                if len(skipped_pages) > 5:
                    error_message += f"\n... and {len(skipped_pages) - 5} more skipped pages"
            
            if navigation_pages:
                error_message += f"\n\nNavigation pages:"
                for page in navigation_pages[:5]:  # Show first 5 navigation pages
                    error_message += f"\n- {page['url']} ({page['page_type']}): {page['reason']}"
                if len(navigation_pages) > 5:
                    error_message += f"\n... and {len(navigation_pages) - 5} more navigation pages"
            
            logger.error(error_message)
            self.log_update_callback(error_message)
            raise ValueError(error_message)

        # Collect all working code and their results
        working_codes = []
        for url, data in self.page_tree.items():
            if (data.generated_code and 
                data.code_execution_result and 
                not data.code_execution_error):
                working_codes.append({
                    'url': url,
                    'code': data.generated_code,
                    'result': self._format_execution_result(data.code_execution_result),
                    'page_type': data.page_type,
                    "children": [child.page_type for child in data.children],
                    'parent': data.parent.page_type if data.parent else None,
                    'page_name': data.analysis_data.get('generic_name_of_page') if data.analysis_data else None,
                    'pagination_info': data.analysis_data.get('pagination_info', {}) if data.analysis_data else {}
                })

        # Check if we have any working code
        if not working_codes:
            error_message = "❌ No working code found for code generation. "
            error_message += f"Found {len(useful_pages)} useful pages but none have successfully generated and executed code. "
            error_message += "This may indicate issues with the page analysis or code generation process. "
            error_message += "Please check the page analysis results and try again."
            
            # Add details about useful pages that failed
            error_message += f"\n\nUseful pages that failed code generation:"
            for page in useful_pages:
                error_message += f"\n- {page['url']} ({page['page_type']}) - Code: {page['has_generated_code']}, Result: {page['has_execution_result']}, Error: {page['has_execution_error']}"
            
            logger.error(error_message)
            self.log_update_callback(error_message)
            raise ValueError(error_message)

        # Load sample utility code for reference
        sample_utility_code = self._load_sample_utility_code()

        prompt = self._build_code_generation_prompt(working_codes, sample_utility_code)

        logger.info(f"prompt len:{len(prompt)}")
        self.log_update_callback(f"llm call final cogen :prompt len:{len(prompt)}")
        
        try:
            code_gen = await call_openai_async(
                prompt=prompt,
                response_format={"type": "json_object"},
                client=openai_async_client
            )
            code_gen = json.loads(code_gen)
            code = code_gen["python_code"]
            
            # Collect extra info for UI
            self.extra_info = {k: v for k, v in code_gen.items() if k != "python_code"}
            for k, v in code_gen.items():
                if k != "python_code":
                    logger.info(f"{k} : {v}")
                    self.log_update_callback(f"{k} : {v}")
            
            self.python_code_function_name = code_gen.get("python_code_function_name", "extract_data")

            # Clean any markdown formatting
            code = code.replace("```python", "").replace("```", "").strip()
            self.generated_code = code
            
            # Validate the generated code
            await self._validate_generated_code(code)
            
            self.log_update_callback("✅ Code generation complete")
            logger.info("✅ Code generation complete")
            logger.info(f"Generated code: entry function is {self.python_code_function_name}")
            logger.debug("=" * 50)
            logger.debug(code)
            logger.debug("=" * 50)
            
            return code
            
        except Exception as e:
            logger.error(f"❌ Error generating extraction code: {str(e)}")
            raise

    def _format_execution_result(self, result: Dict[str, Any]) -> str:
        """Format execution result for inclusion in prompt."""
        result_str = json.dumps(result, indent=2)
        if len(result_str) < 30_000:
            return result_str
        else:
            return (result_str[:10_000] + "....." + result_str[-10_000:])

    def _load_sample_utility_code(self) -> str:
        """Load sample utility code for reference."""
        try:
            sample_path = Path(__file__).parent / "linkedin_search_to_csv.py"
            if sample_path.exists():
                with open(sample_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning("utils/linkedin_search_to_csv.py not found")
                return ""
        except Exception as e:
            logger.warning(f"Failed to load sample utility code: {e}")
            return ""

    def _build_code_generation_prompt(self, working_codes: List[Dict], sample_utility_code: str) -> str:
        """Build the prompt for code generation."""
        pagination_instructions = ""
        if self.requirement.pagination:
            pagination_instructions = """
        PAGINATION HANDLING REQUIREMENTS:
        - The generated code MUST handle pagination when enabled
        - Use the pagination_info from the page analysis to implement appropriate pagination strategy
        - Implement pagination logic to navigate through multiple pages based on pagination_info.pagination_type
        - Use the existing pagination functions from utils.fetch_html_playwright:
          * _fetch_pages_by_selector() for selector-based pagination
          * _fetch_pages_with_actions() for action-based pagination
          * _fetch_pages() for general pagination handling
        - Use pagination_info.pagination_selectors for targeting pagination elements
        - Use pagination_info.pagination_patterns for URL-based pagination
        - Use pagination_info.pagination_actions for JavaScript-based pagination
        - Use pagination_actions.wait_for_load for JavaScript-based page_actions if it is JavaScript-based
        
        - Implement proper pagination state management
        - Add pagination-related CLI arguments if needed
        - Include pagination progress logging
        - Handle pagination errors gracefully
        - Limit pagination to reasonable number of pages (use pagination_info.total_pages_estimate, max 50 by default)
        - Respect pagination_info.items_per_page for batch processing
        """
        
        return f"""
        User wants to build a new GTM utility with the following details:
        
        The utility should accept command line arguments and also provide a *_from_csv* function that reads the same parameters from a CSV file.
        
        The input CSV columns should match the argument names without leading dashes.
        
        Do NOT create a 'mode' argument or any sub-commands. main() should simply parse "output_file" as the first positional argument followed by optional parameters
        
        Provide a <utility_name>_from_csv(input_file, output_file, **kwargs) helper that reads the same parameters from a CSV file.
        
        The input CSV headers must match the argument names (without leading dashes) except for output_file.
        
        The output CSV must keep all original columns and append any new columns produced by the utility.
        
        Please output only the Python code for this utility below, without any markdown fences or additional text
        
        Get fully functional, compiling standalone python script with all the required imports.
        
        arguments to main will be like in example below, output_file is always a parameter. input arguments like --person_title etc are custom parameters that can be passed as input the to script
        "def main() -> None:"
        "    parser = argparse.ArgumentParser(description=\"Search people in Apollo.io\")"
        "    parser.add_argument(\"output_file\", help=\"CSV file to create\")"
        
        Use standard names for lead and company properties in output like full_name, first_name, last_name, user_linkedin_url, email, organization_linkedin_url, website, job_title, lead_location, primary_domain_of_organization
        Use user_linkedin_url property to represent users linkedin url.
        Always write the output to the csv in the output_file specified like below converting the json to csv format.
        fieldnames: List[str] = []
        for row in results:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)

        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
        
        The app passes the output_path implicitly using the tool name and current date_time; do not ask the user for this value.

        Here is python code for multi_pages pages you need to combine the code to achieve user requirement:
        
        {json.dumps(working_codes, indent=2)}
        Here is the Target URL : {self.root_url}
        Here is user requirement: {self.requirement.additional_instructions}
        Pagination Enabled: {self.requirement.pagination}

        { "required_data: " +json.dumps(self.requirement.extraction_spec.get('required_data'), indent=2) if self.requirement.extraction_spec.get('required_data') else "" }
        
        Here is 

        PAGINATION INFORMATION USAGE:
        Each page in the working_codes above contains pagination_info that should be used for pagination handling:
        - If pagination_info.has_pagination is true, implement pagination logic
        - Use pagination_info.pagination_type to determine the pagination strategy:
          * "url_based": Modify URL parameters to navigate pages
          * "javascript_based": Use JavaScript actions to navigate
          * "infinite_scroll": Implement scroll-based loading
          * "load_more": Click "load more" buttons
        - Use pagination_info.pagination_selectors for element targeting
        - Use pagination_info.pagination_patterns for URL construction
        - Use pagination_info.pagination_actions for JavaScript execution
        - Respect pagination_info.total_pages_estimate and items_per_page for limits

        Python coding instructions:
        1. Extract data according to the extraction specification above
        2. Use BeautifulSoup for parsing
        3. The target URL is {self.root_url} - use this URL directly in the code, don't take it as a parameter
        4. make sure main function should start with {self.page_tree[self.root_url].page_type} {self.root_url}. i mean script start with {self.root_url}
        5. make sure script is executable in cli
        6. to get html_code for any url use this code: from utils.fetch_html_playwright import _fetch_and_clean html_code = await _fetch_and_clean(url) # this using Playwright
        6a. to get markdown_code for any url, first fetch HTML using _fetch_and_clean or fetch_multiple_html_pages, then convert to markdown using html_to_markdown: from utils.fetch_html_playwright import html_to_markdown; markdown_code = html_to_markdown(html_code)
        7. For fetching HTML from a list of unrelated URLs, use fetch_multiple_html_pages from utils.fetch_html_playwright.py to efficiently batch-fetch all pages in a single browser session. Do not loop over _fetch_and_clean or fetch_html for each URL separately.
        8. For pagination or infinite scroll, set the default value of max_pages (or similar limit) to a small number (e.g., 2 or 3) for easier validation and testing. Allow this to be overridden by the user via CLI argument or function parameter.
        9. Make sure there are no demo code, make production ready code
        10. Make CLI "output_file" as only one mandatory positional args for main().The first "output_file" positional argument followed by optional parameters
        11. Validate the extracted data according to the validation rules in the specification
        12. Structure the output according to the data_structure in the specification
        13. Include proper error handling and logging
        14. Use type hints for all functions
        15. Add docstrings for all functions
        16. Follow PEP 8 style guidelines
        17. Use async/await consistently throughout the code
        18. Handle rate limiting and retries for HTTP requests
        19. Include proper exception handling for network errors
        20. Add validation for extracted data
        21. Include progress logging
        22. Add proper cleanup in case of errors
        23. **IMPORTANT for BeautifulSoup selectors:** When using BeautifulSoup's select or select_one, always use valid CSS selectors supported by BeautifulSoup's parser. Attribute values must be quoted (e.g., [data-test="post-name-"]), and do NOT use selectors with bracketed class names as these will cause parse errors. If you need to match such classes, use soup.find or soup.find_all with class_ parameter instead.
        24. **CRITICAL JSON SERIALIZATION REQUIREMENTS:**
            - All functions that return data MUST return dictionaries (dict), NOT Pydantic model objects
            - If you use Pydantic models for data validation, convert them to dictionaries before returning
            - Use .model_dump() or .dict() method to convert Pydantic models to dictionaries
            - Example: return model.model_dump() instead of return model
            - All returned data must be JSON serializable (dict, list, str, int, float, bool, None)
            - DO NOT return Pydantic model objects directly as they cause "Object of type X is not JSON serializable" errors
            - Test that your return value can be serialized with json.dumps() before returning
            - EXAMPLE: If you create a Pydantic model like:
              ```python
              class ExtractedData(BaseModel):
                  title: str
                  description: str
                  url: str
              
              # WRONG - returns Pydantic object
              return ExtractedData(title="test", description="test", url="test")
              
              # CORRECT - returns dictionary
              data = ExtractedData(title="test", description="test", url="test")
              return data.model_dump()
              ```
        
        # ... existing code ...
        Required imports:
        - asyncio
        - json
        - os
        - argparse
        - logging
        - typing
        - bs4
        - aiohttp
        - pydantic (basic BaseModel only, no optional dependencies)
        - from utils.fetch_html_playwright import _fetch_and_clean
        - from utils.fetch_html_playwright import fetch_multiple_html_pages
        - from utils.fetch_html_playwright import html_to_markdown
        - from utils.fetch_html_playwright import _fetch_pages, _fetch_pages_by_selector, _fetch_pages_with_actions (for pagination)

        Return a JSON object with the following structure:
        {{
            "python_code_function_name": <name of the main extraction function>,
            "utility_name": <name this utility>,
            "description": <description  of utility>
            "successfully data": <describe what are data successfully parsed >,
            "score": "provide score(0 to 10) for as per user requirement achievement"
            "python_code": <python_code>
        }}

        IMPORTANT: 
        1. The code must be production-ready and handle all edge cases
        2. Include proper error handling and logging
        3. Follow Python best practices
        4. The code must be valid Python that can be compiled
        5. All functions must be properly typed
        6. Include docstrings for all functions
        7. Follow PEP 8 style guidelines
        9. Handle CLI arguments properly
        10. Avoid all deprecated packages and functions
        11. **CRITICAL:** Avoid any imports or field types that require additional packages beyond the basic requirements
         
        Use following below code as example for playwright :
        {sample_of_playwright_usage}
         
        Use following as examples which can help you generate the code required for above GTM utility:
        {sample_utility_code}
        """

    async def _validate_generated_code(self, code: str) -> None:
        """Validate the generated code by attempting to compile it."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
                try:
                    f.write(code.encode())
                    f.flush()

                    spec = importlib.util.spec_from_file_location("page_extractor", f.name)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Check if the required function exists
                    if not hasattr(module, self.python_code_function_name):
                        logger.error(f"Function '{self.python_code_function_name}' not found in generated code")
                        raise AttributeError(f"Function '{self.python_code_function_name}' not found in generated code")

                    logger.info("✅ Code validation successful")
                except Exception as e:
                    self.log_update_callback(f"❌ Generated code validation failed: {str(e)}")
                    logger.error(f"❌ Generated code validation failed: {str(e)}")
                    # Try to fix the code
                    await self._fix_generated_code_validation(code, str(e))
                finally:
                    # Clean up
                    os.unlink(f.name)

        except Exception as e:
            logger.error(f"❌ Error during code validation: {str(e)}")
            raise Exception(e)

    async def _fix_generated_code_validation(self, code: str, error: str) -> None:
        """Attempt to fix code validation errors."""
        fix_prompt = f"""
        Fix the following Python code that failed validation with error: {error}

        Original code:
        {code}

        Requirements:
        1. The code should extract data from the HTML
        2. It should handle the error: {error}
        3. It should return a dictionary with the extracted data
        4. Use BeautifulSoup for parsing
        5. Follow all the requirements from the original prompt
        6. The main function MUST be named '{self.python_code_function_name}'

        CRITICAL REQUIREMENTS TO PREVENT COMMON ISSUES:
        7. **Pydantic Usage Restrictions:**
            - Use ONLY basic Pydantic BaseModel with standard field types (str, int, bool, float, List, Dict, Optional)
            - DO NOT use EmailStr, HttpUrl, or any other Pydantic field types that require additional packages
            - DO NOT use pydantic[email] or any optional Pydantic dependencies
            - Use str for email fields, not EmailStr
            - Use str for URL fields, not HttpUrl
            - Use basic validation with Field() if needed, but avoid complex validators
        8. **Import Restrictions:**
            - Only use standard library imports and the explicitly listed required imports
            - DO NOT import any packages that require additional installation beyond the basic requirements
            - Avoid any imports that might cause "ImportError: package is not installed" errors
        9. **CRITICAL JSON SERIALIZATION REQUIREMENTS:**
            - All functions that return data MUST return dictionaries (dict), NOT Pydantic model objects
            - If you use Pydantic models for data validation, convert them to dictionaries before returning
            - Use .model_dump() or .dict() method to convert Pydantic models to dictionaries
            - Example: return model.model_dump() instead of return model
            - All returned data must be JSON serializable (dict, list, str, int, float, bool, None)
            - DO NOT return Pydantic model objects directly as they cause "Object of type X is not JSON serializable" errors
            - Test that your return value can be serialized with json.dumps() before returning
            - The main extraction function must return a list of dictionaries, not Pydantic model objects
            - EXAMPLE: If you create a Pydantic model like:
              ```python
              class ExtractedData(BaseModel):
                  title: str
                  description: str
                  url: str
              
              # WRONG - returns Pydantic object
              return ExtractedData(title="test", description="test", url="test")
              
              # CORRECT - returns dictionary
              data = ExtractedData(title="test", description="test", url="test")
              return data.model_dump()
              ```
        10. Proper CLI argument handling:
            - Use argparse.ArgumentParser() correctly
            - Define all expected arguments with proper types
            - Handle the case when no arguments are provided
            - Use parser.parse_args() to parse arguments
            - Add proper help text for all arguments
        11. Avoid deprecated packages:
            - DO NOT use pkg_resources (use importlib.metadata instead)
            - DO NOT use any deprecated imports or functions
            - Use modern Python 3.8+ syntax
        12. Proper script structure:
            - Include if __name__ == "__main__": block
            - Handle both direct execution and import scenarios
            - Use asyncio.run() for async main functions
            - Proper error handling in main function

        Return only the fixed Python code without any explanations.
        IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
        """

        try:
            fixed_code = call_openai_sync(
                prompt=fix_prompt,
                model="gpt-4.1",
                response_format={"type": "text"},
                client=openai_client
            )
            self.generated_code = fixed_code
            logger.info("🔄 Generated fixed code")
        except Exception as fix_error:
            logger.error(f"❌ Failed to generate fixed code: {str(fix_error)}")

    async def execute_generated_code(self, url: str) -> Dict[str, Any]:
        """
        Execute the generated code for a specific URL.
        
        Args:
            url: URL to execute the generated code against
            
        Returns:
            Dictionary containing execution results and extracted data
        """
        logger.info(f"▶️ Executing generated code for URL: {url}")
        if not self.generated_code:
            raise ValueError("No code generated yet")

        max_attempts = 2
        current_attempt = 0
        last_error = None
        current_code = self.generated_code

        while current_attempt < max_attempts:
            try:
                current_attempt += 1
                logger.info(f"🔄 Attempt {current_attempt}/{max_attempts} to execute code")
                self.log_update_callback(f"🔄 Attempt {current_attempt}/{max_attempts} to execute code")

                result = await self._execute_code_subprocess(current_code, url)
                if result.get("extracted_data"):
                    self.log_update_callback("✅ Code execution successful with extracted data")
                    logger.info("✅ Code execution successful with extracted data")
                    logger.info(f"📊 Extracted {len(result.get('extracted_data', []))} items")
                    return result
                else:
                    # No data extracted, return subprocess output for debugging
                    logger.info("⚠️ No data extracted")
                    return result

            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Error during execution: {last_error}")
                if current_attempt >= max_attempts:
                    return {
                        "extracted_data": [],
                        "total_items": 0,
                        "execution_success": False,
                        "error": last_error
                    }

        # If we get here, all attempts failed
        error_msg = f"Failed after {current_attempt} attempts. Last error: {last_error}"
        logger.error(f"❌ {error_msg}")
        return {
            "extracted_data": [],
            "total_items": 0,
            "execution_success": False,
            "error": error_msg
        }

    async def _execute_code_subprocess(self, code: str, url: str) -> Dict[str, Any]:
        """Execute the generated code using subprocess."""
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            try:
                f.write(code.encode())
                f.flush()
                script_path = f.name

                out_path = common.make_temp_csv_filename("codegen_barbarika_webparsing")
                
                # Execute the function using subprocess, streaming logs
                env = os.environ.copy()
                root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                env["PYTHONPATH"] = env.get("PYTHONPATH", "") + ":" + root_dir

                cmd = ["python", script_path, out_path]
                self.log_update_callback(f"cmd: {cmd}")

                import threading
                import queue

                def stream_reader(pipe, cb, q):
                    try:
                        for line in iter(pipe.readline, ''):
                            if not line:
                                break
                            cb(line.rstrip())
                            q.put(line)
                    finally:
                        pipe.close()

                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, bufsize=1)
                q_stdout = queue.Queue()
                q_stderr = queue.Queue()
                t_out = threading.Thread(target=stream_reader, args=(proc.stdout, self.log_update_callback, q_stdout))
                t_err = threading.Thread(target=stream_reader, args=(proc.stderr, self.log_update_callback, q_stderr))
                t_out.start()
                t_err.start()
                t_out.join()
                t_err.join()
                proc.wait()

                # Collect all output
                stdout = ''.join(list(q_stdout.queue))
                stderr = ''.join(list(q_stderr.queue))
                status = "SUCCESS" if proc.returncode == 0 else "FAIL"
                output = stdout if proc.returncode == 0 else (stderr or "Error running command")
                logger.info(f"[Subprocess] Status: {status}")
                logger.info(f"[Subprocess] Output: {output}")

                # Try to read the CSV file to get the actual extracted data
                extracted_data = []
                if os.path.exists(out_path):
                    logger.info(f"read the CSV file to get the actual extracted data: {out_path}")
                    import csv
                    try:
                        with open(out_path, 'r', newline='', encoding='utf-8') as csvfile:
                            reader = csv.DictReader(csvfile)
                            extracted_data = list(reader)
                            logger.info(f"✅ Successfully read {len(extracted_data)} rows from CSV")
                    except Exception as csv_error:
                        logger.warning(f"⚠️ Warning: Could not read CSV file: {csv_error}")

                # If subprocess failed, trigger code-fix logic
                if proc.returncode != 0:
                    last_error = f"Subprocess failed with return code {proc.returncode}.\nStdout:\n{stdout}\nStderr:\n{stderr}"
                    logger.error(f"❌ Error in subprocess: {last_error}")
                    self.log_update_callback(f"❌ Error in subprocess: {last_error}")
                    
                    # Try to fix the code
                    fixed_code = await self._fix_subprocess_code(code, last_error, stdout, stderr)
                    if fixed_code != code:
                        return await self._execute_code_subprocess(fixed_code, url)

                # Return results
                if extracted_data:
                    return {
                        "extracted_data": extracted_data,
                        "csv_file": out_path,
                        "total_items": len(extracted_data),
                        "execution_success": proc.returncode == 0,
                        "subprocess_status": status,
                        "subprocess_output": output
                    }
                else:
                    return {
                        "extracted_data": [],
                        "csv_file": out_path,
                        "total_items": 0,
                        "execution_success": proc.returncode == 0,
                        "subprocess_status": status,
                        "subprocess_output": output,
                        "message": "No data found to extract or CSV could not be read"
                    }
            finally:
                # Clean up temporary files
                try:
                    os.unlink(f.name)
                except OSError:
                    pass

    async def _fix_subprocess_code(self, code: str, error: str, stdout: str, stderr: str) -> str:
        """Attempt to fix subprocess execution errors."""
        fix_prompt = f"""
        Fix the following Python code that failed to execute with error: {error}

        Original code:
        {code}

        Subprocess stdout:
        {stdout}

        Subprocess stderr:
        {stderr}

        Requirements:
        1. The code should extract data from the HTML
        2. It should handle the error: {error}
        3. It should return a dictionary with the extracted data
        4. Use BeautifulSoup for parsing
        5. The main function MUST be named '{self.python_code_function_name}'
        6. Include proper error handling and logging
        7. Use type hints for all functions
        8. Add docstrings for all functions
        9. Follow PEP 8 style guidelines
        10. Handle rate limiting and retries
        11. Include proper exception handling
        12. DO NOT hallucinate data - only extract what exists in the HTML
        13. Add validation steps for extracted data
        14. Add logging for any assumptions made
        15. **CRITICAL JSON SERIALIZATION REQUIREMENTS:**
            - All functions that return data MUST return dictionaries (dict), NOT Pydantic model objects
            - If you use Pydantic models for data validation, convert them to dictionaries before returning
            - Use .model_dump() or .dict() method to convert Pydantic models to dictionaries
            - Example: return model.model_dump() instead of return model
            - All returned data must be JSON serializable (dict, list, str, int, float, bool, None)
            - DO NOT return Pydantic model objects directly as they cause "Object of type X is not JSON serializable" errors
            - Test that your return value can be serialized with json.dumps() before returning
            - The main extraction function must return a list of dictionaries, not Pydantic model objects

        CRITICAL DEPENDENCY REQUIREMENTS:
        16. **Pydantic Usage Restrictions:**
            - Use ONLY basic Pydantic BaseModel with standard field types (str, int, bool, float, List, Dict, Optional)
            - DO NOT use EmailStr, HttpUrl, or any other Pydantic field types that require additional packages
            - DO NOT use pydantic[email] or any optional Pydantic dependencies
            - Use str for email fields, not EmailStr
            - Use str for URL fields, not HttpUrl
            - Use basic validation with Field() if needed, but avoid complex validators
        17. **Import Restrictions:**
            - Only use standard library imports and the explicitly listed required imports
            - DO NOT import any packages that require additional installation beyond the basic requirements
            - Avoid any imports that might cause "ImportError: package is not installed" errors

        CRITICAL: Do NOT use asyncio.run() or any event loop management in the generated code. The main function will be called as a script or awaited by the caller.

        Return only the fixed Python code without any explanations.
        IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
        """
        
        try:
            fixed_code = call_openai_sync(
                prompt=fix_prompt,
                model="gpt-4o-mini",
                response_format={"type": "text"},
                client=openai_client
            )
            logger.info("🔄 Generated fixed code for subprocess")
            self.log_update_callback("🔄 Generated fixed code for subprocess")
            return fixed_code
        except Exception as fix_error:
            logger.error(f"❌ Failed to generate fixed code: {str(fix_error)}")
            return code

    def _force_tree_update(self) -> None:
        """Force an immediate tree update, bypassing throttling."""
        if self.pending_tree_update:
            self.pending_tree_update = False
            self._update_tree()

    def _update_tree_with_code_result(self, url: str, result: Optional[Dict[str, Any]], error: Optional[str], message: str) -> None:
        """Send real-time tree update with code execution results."""
        if not self.tree_update_callback:
            return
            
        # Find the page in the tree
        page_data = self.page_tree.get(url)
        if not page_data:
            return
            
        # Update page data with execution results
        page_data.code_execution_result = result
        page_data.code_execution_error = error
        
        # Force immediate update for important data
        self._force_tree_update_with_data(url, message, 90)  # 90% progress after code execution

    def _update_tree_with_page_data(self, page_data: PageData, message: str, progress: int) -> None:
        """Send real-time tree update with page data."""
        if not self.tree_update_callback:
            return
            
        # Update page data with progress
        page_data.progress = progress
        
        # Send tree update with page data
        self._update_tree(message, page_data.url, progress)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def web_parse_to_json(
    url: str,
    data_to_extract: Optional[List[str]] = None,
    max_depth: int = 3,
    pagination: bool = False,
    additional_instructions: str = "",
    output_file: str = "output.json"
) -> Dict[str, Any]:
    """
    Parse a website and save the extracted data to a JSON file.
    
    This is a convenience function that creates a UserRequirement, initializes
    a WebParser, and runs the complete extraction pipeline.
    
    Args:
        url: Target URL to parse
        data_to_extract: List of fields to extract (auto-generated if None)
        max_depth: Maximum crawl depth (default: 3)
        pagination: Whether to handle pagination (default: False)
        additional_instructions: Custom extraction instructions
        output_file: Output JSON file path (default: "output.json")
        
    Returns:
        Dictionary containing extraction results
        
    Raises:
        Exception: If parsing fails
    """
    requirement = UserRequirement(
        target_url=url,
        data_to_extract=data_to_extract,
        max_depth=max_depth,
        pagination=pagination,
        additional_instructions=additional_instructions
    )

    parser = WebParser(requirement)

    try:
        # Build page tree and generate code
        asyncio.run(parser.build_page_tree())
        asyncio.run(parser.generate_extraction_code())

        # Execute the generated code
        result = asyncio.run(parser.execute_generated_code(url))

        # Convert to CSV if specified in the extraction spec
        if (requirement.extraction_spec and 
            requirement.extraction_spec["output_format"]["type"] == "csv"):
            csv_file = output_file.replace(".json", ".csv")
            import pandas as pd
            df = pd.DataFrame(result.get("extracted_data", []))
            df.to_csv(csv_file, index=False)
            logger.info(f"✅ Results saved to CSV: {csv_file}")

        # Save results to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

        logger.info(f"Successfully parsed website and saved results to {output_file}")
        return result
    except Exception as e:
        logger.error(f"Error parsing website: {str(e)}")
        raise


def web_parse_to_json_from_csv(input_file: str, output_file: str) -> None:
    """
    Run web parsing from a CSV and aggregate results.
    
    The input_file must contain these columns:
    - url: Target URL to parse
    - data_to_extract: Comma-separated list of fields to extract (optional)
    - max_depth: Maximum crawl depth (optional)
    - pagination: Whether to enable pagination (optional)
    - additional_instructions: Custom extraction instructions (optional)
    
    Args:
        input_file: Path to input CSV file
        output_file: Path to output JSON file
        
    Raises:
        ValueError: If input CSV is missing required columns
        Exception: If processing fails
    """
    import csv

    with open(input_file, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        if "url" not in fieldnames:
            raise ValueError("Input CSV must contain a 'url' column")
        rows = list(reader)

    aggregated_results = []
    for row in rows:
        url = row.get("url", "").strip()
        if not url:
            continue

        data_to_extract = None
        if "data_to_extract" in row and row["data_to_extract"]:
            data_to_extract = [f.strip() for f in row["data_to_extract"].split(",")]

        max_depth = 3
        if "max_depth" in row and row["max_depth"]:
            try:
                max_depth = int(row["max_depth"])
            except ValueError:
                pass

        pagination = False
        if "pagination" in row and row["pagination"]:
            pagination = row["pagination"].lower() in ("true", "1", "yes")

        additional_instructions = row.get("additional_instructions", "").strip()

        try:
            result = web_parse_to_json(
                url=url,
                data_to_extract=data_to_extract,
                max_depth=max_depth,
                pagination=pagination,
                additional_instructions=additional_instructions,
                output_file=None  # Don't save individual results
            )
            if result:
                aggregated_results.append(result)
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            continue

    # Save aggregated results
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(aggregated_results, f, indent=2)

    logger.info(f"Wrote {len(aggregated_results)} results to {output_file}")


def main() -> None:
    """
    Main entry point for command-line usage.
    
    Parses command line arguments and runs the web parser.
    """
    parser = argparse.ArgumentParser(
        description="Web Parser Tool - Extract structured data from websites using AI-powered analysis"
    )
    parser.add_argument("url", help="Target URL to parse")
    parser.add_argument(
        "-f", "--fields",
        nargs="+",
        help="Specific fields to extract (optional)"
    )
    parser.add_argument(
        "-d", "--max-depth",
        type=int,
        default=3,
        help="Maximum depth for crawling (default: 3)"
    )
    parser.add_argument(
        "-p", "--pagination",
        action="store_true",
        help="Enable pagination support"
    )
    parser.add_argument(
        "-i", "--instructions",
        default="",
        help="Additional instructions for data extraction"
    )
    parser.add_argument(
        "-o", "--output",
        default="output.json",
        help="Output JSON file (default: output.json)"
    )
    args = parser.parse_args()

    web_parse_to_json(
        url=args.url,
        data_to_extract=args.fields,
        max_depth=args.max_depth,
        pagination=args.pagination,
        additional_instructions=args.instructions,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
