import asyncio
import json
import os
import argparse
import logging
import subprocess
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel

from utils import common
from utils.extract_from_webpage import _fetch_and_clean
from utils.common import call_openai_async, call_openai_sync, openai_client_sync, openai_client as openai_client_async

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

dotenv_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path)

with open("utils/fetch_html_playwright.py", 'r', encoding='utf-8') as f:
    sample_of_playwright_usage = f.read()
sample_of_playwright_usage = f"Here is minium edge cases for playwright usage : {sample_of_playwright_usage}"

# Create a single OpenAI client instance for reuse
openai_async_client = openai_client_async()
openai_client = openai_client_sync()
class UserRequirement(BaseModel):
    target_url: str
    data_to_extract: Optional[List[str]] = None
    max_depth: int = 3
    pagination: bool = False
    additional_instructions: str = ""
    extraction_spec: Optional[Dict[str, Any]] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not self.data_to_extract:
            # Use LLM to determine what data to extract based on requirements
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
                logger.info(f"📋 LLM generated extraction specification:")
                logger.info(json.dumps(spec_data, indent=2))
            except Exception as e:
                logger.error(f"❌ Error generating extraction specification: {str(e)}")
                self.data_to_extract = []
                self.extraction_spec = None


class PageData(BaseModel):
    url: str
    html: str
    json_data: Dict
    path: List[str]
    children: List['PageData'] = []
    parent: Optional['PageData'] = None
    analysis_data: Dict = None
    to_be_filled_fields: List[str] = []
    page_type: str = None
    exclusive_fields: List[str] = []
    generated_code: str = None  # Store the generated Python code
    code_execution_result: Optional[Dict] = None  # Store the execution result
    code_execution_error: Optional[str] = None  # Store any execution errors
    relevance_score: float = 0.0


class WebParser:
    def __init__(self, requirement: UserRequirement, log_update_callback=None,tree_update_callback=None):
        logger.info(f"\n🚀 Initializing WebParser with URL: {requirement.target_url}")
        logger.info(f"📋 Data to extract: {requirement.data_to_extract}")
        logger.info(f"🔍 Max depth: {requirement.max_depth}")
        logger.info(f"📄 Pagination: {requirement.pagination}")
        logger.info(f"📝 Additional instructions: {requirement.additional_instructions}")
        self.log_update_callback = log_update_callback
        self.tree_update_callback = tree_update_callback
        self.requirement = requirement
        self.root_url = requirement.target_url
        self.page_tree: Dict[str, PageData] = {}
        self.visited_urls: set = set()
        self.visited_page_types: set = set()
        self.generated_code: str = ""
        self.python_code_function_name: str = ""
        self.plan: dict = dict()
        self.tree_root: PageData | None = None

    async def analyze_requirement(self) -> Dict:
        """Analyze user requirement and create extraction plan."""
        logger.info("\n📊 Analyzing user requirements...")
        prompt = f"""
        You are an expert web scraping architect. Your task is to analyze a web scraping requirement and create a comprehensive, actionable extraction plan in JSON format.
        
        Here is the user requirement : {self.requirement.additional_instructions}
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
            "already_extracted_fields: []
            "to_be_extracted_fields":[],
            "required_data":[]
        }}
        
        
        standards instruction :
            - Use standard names for lead and company properties in output like full_name, first_name, last_name, user_linkedin_url, email, organization_linkedin_url, website, job_tiltle, lead_location, primary_domain_of_organization
            - provide proper required data
            - provide proper extraction_steps

        """

        plan = call_openai_sync(
            prompt=prompt,
            response_format={"type": "json_object"},
            client=openai_client
        )
        plan_data = json.loads(plan)
        logger.info("✅ Requirement analysis complete")
        logger.info(json.dumps(plan_data, indent=2))
        logger.info(f"📋 Extraction steps: {len(plan_data['extraction_steps'])}")
        # print(f"🔗 Required pages: {len(plan_data['required_pages'])}")
        return plan_data

    async def analyze_page_directly(self, html: str, url: str, parent_page: PageData = None) -> Dict:
        """Analyze HTML directly and return all analysis data in one call."""
        logger.info(f"\n🔍 Analyzing page directly: {url}")

        prompt = f"""
        Analyze this HTML content of a webpage and provide comprehensive analysis in one JSON response.

        Context:
        - Target URL: {url}
        - Required Data to Extract: {self.requirement.data_to_extract}
        - Additional Instructions: {self.requirement.additional_instructions}
        - Main Plan: {json.dumps(self.plan, indent=2)}
        - Already Visited Page Types: {self.visited_page_types}
        - Parent Page Type: {parent_page.page_type if parent_page else 'None'}

        HTML Content:
        {html[:500_000]}

        Return a JSON object with the following structure:
        {{
            "structured_data": "Convert the HTML to structured JSON format, ensuring all links are captured",
            "main_content_areas": "List of main content areas found",
            "navigation_elements": "List of navigation elements found", 
            "patterns_identified": "Data patterns identified in the page",
            "summery" : <summery of the page as per requirment>
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
            "relevance_score": <>,
            "available_fields": ["list of fields available for extraction"],
            "generic_name_of_page": <generic name for this page>,
            "python_code": <Python code to extract data from this page>,
            "python_code_function_name": <name of the main extraction function>
        }}

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

        Rules for python_code:
        1. Always use _fetch_and_clean with url for fetching HTML code  : from utils.extract_from_webpage import _fetch_and_clean
           html_code = await _fetch_and_clean(url) # this using Playwright
        2. Write Python code to extract all required information in structured data
        3. The function should be async and take a url parameter
        4. Use BeautifulSoup for parsing
        5. Include proper error handling and logging
        6. Use type hints for all functions
        7. Add docstrings for all functions
        8. Follow PEP 8 style guidelines
        9. Handle rate limiting and retries
        10. Include proper exception handling
        11. DO NOT hallucinate data - only extract what exists in the HTML
        12. Validate extracted data against HTML content
        13. Add logging for any assumptions made
        14. Add verification steps for extracted data
        {'15. Build upon existing code from parent page: ' + parent_page.page_type if parent_page else ''}
        {'16. Parent page code: ' + parent_page.analysis_data['python_code'] if parent_page and parent_page.analysis_data else ''}

        IMPORTANT: 
        1. Your response MUST be valid JSON
        2. Ensure all strings are properly quoted and brackets are balanced
        3. All required fields must be present
        4. All values must match their specified types
        5. Relevance scores must be between 0.0 and 1.0
        6. URLs must be absolute and valid
        7. Python code must be valid and follow all specified rules
        8. DO NOT hallucinate any data - only use what exists in the HTML
        9. Verify all extracted data against the HTML content
        10. Add validation steps to ensure data accuracy
        11. {sample_of_playwright_usage}
        """

        try:
            logger.info(f"calling openai sync")
            self.log_update_callback(f"🔍 Analyzing page directly: {url} calling llm")
            analysis = call_openai_sync(
                prompt=prompt,
                response_format={"type": "json_object"},
                client=openai_client
            )
            analysis_data = json.loads(analysis)

        except json.decoder.JSONDecodeError as e:
            logger.error(f"❌ JSON decode error: {e}")
            analysis = call_openai_sync(
                prompt=prompt,
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                client=openai_client
            )
            analysis_data = json.loads(analysis)

        logger.info(f"✅ Page analysis complete")
        self.log_update_callback(f"✅ Page analysis complete")
        logger.info(f"📄 Page type: {analysis_data.get('page_type', 'unknown')}")
        logger.info(f"🎯 Relevance score: {analysis_data.get('relevance_score', 0)}")
        # Store the generated code and function name
        generated_code = analysis_data.get('python_code')
        function_name = analysis_data.get('python_code_function_name', 'extract_data')

        # Execute and validate the generated code
        code_execution_result = None
        code_execution_error = None

        if generated_code:
            max_attempts = 4
            current_attempt = 0
            last_error = None

            while current_attempt < max_attempts:
                try:
                    current_attempt += 1
                    logger.info(f"\n🔄 Attempt {current_attempt}/{max_attempts} to execute code for {url}")
                    self.log_update_callback(f"\n🔄 Attempt {current_attempt}/{max_attempts} to execute code for {url}")
                    # Create a temporary module for execution
                    import tempfile
                    import importlib.util

                    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
                        f.write(generated_code.encode())
                        f.flush()

                        # Import the module
                        spec = importlib.util.spec_from_file_location("page_extractor", f.name)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Execute the code using the specified function name
                        if hasattr(module, function_name):
                            result = await getattr(module, function_name)(url)
                            code_execution_result = result
                            logger.info(f"✅ Code execution successful for {url}")
                            self.log_update_callback(f"✅ Code execution successful for {url}")
                            logger.info(f"📊 Result: {json.dumps(result, indent=2)}")
                            if not result:
                                raise Exception("empty result")
                            break  # Success, exit the loop
                        else:
                            raise AttributeError(f"Function '{function_name}' not found in generated code")

                except Exception as e:
                    last_error = str(e)
                    logger.error(f"❌ Error in attempt {current_attempt}: {last_error}")
                    self.log_update_callback(f"❌ Error in attempt {current_attempt}: {last_error}")
                    if current_attempt < max_attempts:
                        # Try to fix the code using another LLM
                        fix_prompt = f"""
                        Fix the following Python code that failed to execute with error: {last_error}

                        Original code:
                        {generated_code}

                        Requirements:
                        1. The code should extract data from the HTML
                        2. It should handle the error: {last_error}
                        3. It should return a dictionary with the extracted data
                        4. Use BeautifulSoup for parsing
                        5. Previous attempts: {current_attempt}/{max_attempts}
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

                        Return only the fixed Python code without any explanations.
                        IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
                        """

                        try:
                            fixed_code = call_openai_sync(
                                prompt=fix_prompt,
                                model="gpt-4.1",  # Use a different model for fixing
                                response_format={"type": "text"},
                                client=openai_client
                            )
                            generated_code = fixed_code
                            logger.info(f"🔄 Generated fixed code for attempt {current_attempt + 1}")
                        except Exception as fix_error:
                            logger.error(f"❌ Failed to generate fixed code: {str(fix_error)}")
                            break  # Exit if we can't even generate fixed code
                    else:
                        logger.error(f"❌ Max attempts ({max_attempts}) reached. Could not fix the code.")
                        self.log_update_callback(f"❌ Max attempts ({max_attempts}) reached. Could not fix the code.")
                        break

                finally:
                    # Clean up temporary files
                    try:
                        os.unlink(f.name)
                    except:
                        pass

            # Store the final error if all attempts failed
            if not code_execution_result:
                code_execution_error = f"Failed after {current_attempt} attempts. Last error: {last_error}"
                logger.error(f"python code: \n START{'=' * 30} {generated_code} \nEND{'=' * 30}")

        # Update plan with available fields
        available_fields = analysis_data.get('available_fields', [])
        exclusive_fields = list(set(available_fields) - set(self.plan.get("already_extracted_fields", [])))
        self.plan["already_extracted_fields"] = list(
            set(self.plan.get("already_extracted_fields", [])).union(set(available_fields)))
        self.plan['to_be_extracted_fields'] = list(
            set(self.plan.get('to_be_extracted_fields', [])) - set(self.plan["already_extracted_fields"]))

        # Filter next pages to visit
        next_pages_to_visit = analysis_data.get('next_pages_to_visit', [])
        un_visited_pages = []
        for page in next_pages_to_visit:
            if (page.get("relevance_score", 0) >= 0.8 and
                    page.get("page_type") not in self.visited_page_types and
                    page.get("url") not in self.visited_urls):
                un_visited_pages.append(page)
                self.visited_page_types.add(page["page_type"])
                self.visited_urls.add(page["url"])
        logger.info(f"🔗 Next pages to visit:{json.dumps(dict(next_visit_pages=un_visited_pages), indent=2)}")
        # Return comprehensive analysis data
        return {
            "structured_data": analysis_data.get("structured_data", {}),
            "main_content_areas": analysis_data.get("main_content_areas", []),
            "navigation_elements": analysis_data.get("navigation_elements", []),
            "patterns_identified": analysis_data.get("patterns_identified", []),
            "next_pages_to_visit": un_visited_pages,
            "page_type": analysis_data.get("page_type", "unknown"),
            "relevance_score": analysis_data.get("relevance_score", 0),
            "available_fields": available_fields,
            "generic_name_of_page": analysis_data.get("generic_name_of_page", ""),
            "python_code": generated_code,
            "python_code_function_name": function_name,
            "exclusive_fields": exclusive_fields,
            "code_execution_result": code_execution_result,
            "code_execution_error": code_execution_error,
            "summery": analysis_data.get("summery",'')
        }

    async def fetch_and_process_page(self, url: str, path: List[str] = None) -> PageData:
        """Fetch and process a page."""
        logger.info(f"\n📥 Fetching page: {url}")
        if path is None:
            path = [url]

        # Fetch HTML
        html = await _fetch_and_clean(url)
        logger.info(f"📄 Fetched HTML content ({len(html)} bytes)")

        # Analyze page directly (merged html_to_json + analyze_page_structure)
        analysis = await self.analyze_page_directly(html, url)

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

        # Create page data
        page_data = PageData(
            url=url,
            html=html,
            json_data=structured_data,
            path=path,
            children=[],
            analysis_data=analysis,
            page_type=analysis.get("page_type"),
            exclusive_fields=analysis.get("exclusive_fields", []),
            generated_code=analysis.get("python_code"),
            code_execution_result=code_execution_result,
            code_execution_error=code_execution_error,
            relevance_score=analysis.get("relevance_score", 0)
        )

        # Store in tree
        if page_data.relevance_score >= 0.8 or self.root_url == url:
            self.page_tree[url] = page_data

        return page_data

    def _serialize_tree(self, node):
        """Recursively serialize the PageData tree for UI visualization."""
        if not node:
            return None
        return {
            'url': node.url,
            'page_type': node.page_type,
            'relevance_score': node.relevance_score,
            'exclusive_fields': node.exclusive_fields,
            'children': [self._serialize_tree(child) for child in getattr(node, 'children', [])],
            'parent_url': node.parent.url if node.parent else None,
            'label': node.analysis_data.get('generic_name_of_page') if node.analysis_data else node.url,
            'status': 'done' if node.analysis_data else 'pending',
            'summery': node.analysis_data.get("summery") if node.analysis_data else '',
            'python_code': node.analysis_data.get("python_code") if node.analysis_data else '',
            'code_execution_result': node.analysis_data.get("code_execution_result") if node.analysis_data else '',
            'analysis_data': node.analysis_data if node.analysis_data else {}
        }

    async def build_page_tree(self, tree_update_callback=None, log_update_callback=None):
        """Build tree of pages starting from root. Optionally call tree_update_callback after each node."""
        logger.info("\n🌳 Building page tree...")
        if log_update_callback:
            log_update_callback("\n🌳 Building page tree...")
        plan = await self.analyze_requirement()
        self.plan = plan

        root_page = await self.fetch_and_process_page(self.root_url)
        self.tree_root = root_page
        self.visited_urls.add(self.root_url)

        async def process_page(page: PageData, depth: int):
            if depth >= self.requirement.max_depth:
                logger.info(f"⏹️ Reached max depth {depth}, stopping...")
                if log_update_callback:
                    log_update_callback(f"⏹️ Reached max depth {depth}, stopping...")
                return

            logger.info(f"\n📑 Processing page at depth {depth}: {page.url} : score: {page.relevance_score}")
            analysis = page.analysis_data
            page.page_type = analysis["page_type"]

            # Emit tree update after processing this node
            if tree_update_callback:
                try:
                    tree_update_callback(self._serialize_tree(self.tree_root))
                except Exception as e:
                    logger.warning(f"Tree update callback error: {e}")

            next_pages_to_visit = analysis.get('next_pages_to_visit', [])
            if isinstance(next_pages_to_visit, list):
                logger.info(f"🔗 Found {len(next_pages_to_visit)} valid next pages to visit")
                for next_page in next_pages_to_visit:
                    logger.info(f"📥 Processing next page: {next_page['label']}::({next_page['relevance_score']}):: {next_page['why']}")
                    child_page = await self.fetch_and_process_page(
                        next_page['url'],
                        path=page.path + [next_page['url']]
                    )
                    if child_page.relevance_score >= 0.8:
                        page.children.append(child_page)
                        child_page.parent = page
                        await process_page(child_page, depth + 1)

        await process_page(root_page, 0)
        logger.info("\n✅ Page tree building complete")
        logger.info(f"📊 Total pages processed: {len(self.page_tree)}")

    async def generate_extraction_code(self) -> str:
        """Generate Python code for data extraction."""
        logger.info("\n💻 Generating extraction code...")
        self.log_update_callback("\n💻 Generating extraction code...")

        # Collect all working code and their results
        working_codes = []
        for url, data in self.page_tree.items():
            if data.generated_code and data.code_execution_result and not data.code_execution_error:
                working_codes.append({
                    'url': url,
                    'code': data.generated_code,
                    'result': data.code_execution_result if len(
                        json.dumps(data.code_execution_result, indent=2)) < 30_000 else json.dumps(
                        data.code_execution_result, indent=2)[:10_000] + "....." + json.dumps(data.code_execution_result,
                                                                                             indent=2)[-10_000:],
                    'page_type': data.page_type,
                    "children": [child.page_type for child in data.children],
                    'parent': data.parent.page_type if data.parent else None,
                    'page_name': data.analysis_data.get('generic_name_of_page') if data.analysis_data else None
                })

        with open("utils/linkedin_search_to_csv.py", 'r', encoding='utf-8') as f:
            sample_utility_code = f.read()
        prompt = f"""
        User wants to build a new GTM utility with the following details:
        
        The utility should accept command line arguments and also provide a *_from_csv* function that reads the same parameters from a CSV file.
        
        The input CSV columns should match the argument names without leading dashes.
        
        Do NOT create a 'mode' argument or any sub-commands. main() should simply parse \"output_file\" as the first positional argument followed by optional parameters
        
        Provide a <utility_name>_from_csv(input_file, output_file, **kwargs) helper that reads the same parameters from a CSV file.
        
        The input CSV headers must match the argument names (without leading dashes) except for output_file.
        
        The output CSV must keep all original columns and append any new columns produced by the utility.
        
        Please output only the Python code for this utility below, without any markdown fences or additional text
        
        Get fully functional, compiling standalone python script with all the required imports.
        
        arguments to mail will be like in example below, output_file is always a parameter. input arguments like --person_title etc are custom parameters that can be passed as input the to script\n"
        "def main() -> None:\n"
        "    parser = argparse.ArgumentParser(description=\"Search people in Apollo.io\")\n"
        "    parser.add_argument(\"output_file\", help=\"CSV file to create\")\n"
        
        Use standard names for lead and company properties in output like full_name, first_name, last_name, user_linkedin_url, email, organization_linkedin_url, website, job_tiltle, lead_location, primary_domain_of_organization
        Use user_linkedin_url property to represent ursers linked in url.
        Always write the output to the csv in the output_file specific like below converting the json to csv format. \nfieldnames: List[str] = []\n    for row in results:\n        for key in row:\n            if key not in fieldnames:\n                fieldnames.append(key)\n\n    with out_path.open(\"w\", newline=\"\", encoding=\"utf-8\") as fh:\n        writer = csv.DictWriter(fh, fieldnames=fieldnames)\n        writer.writeheader()\n        for row in results:\n            writer.writerow(row)\n
        The app passes the output_path implicitly using the tool name and current date_time; do not ask the user for this value.
        


        Here is python code for multi_pages pages you need to combined the code to achieve user requirement:
        
        {json.dumps(working_codes, indent=2)}

        Here is user requirement: {self.requirement.additional_instructions}

        Here is the extraction specification:
        {json.dumps(self.requirement.extraction_spec, indent=2)}

        Python coding instructions:
        1. Extract data according to the extraction specification above
        2. Use BeautifulSoup for parsing
        3. The target URL is {self.root_url} - use this URL directly in the code, don't take it as a parameter
        4. make sure main function should start with {self.page_tree[self.root_url].page_type} {self.root_url}. i mean script start with {self.root_url} 5. make sure script is executable in cli 6. to get html_code for any url use this code: from utils.extract_from_webpage import _fetch_and_clean html_code = await _fetch_and_clean(url) #  this is using Playwright 7. Make sure there are no demo code, make production ready code 8. Make CLI \"output_file\" as only one mandatory positional args for main().The first \"output_file\"  positional argument followed by optional parameters 9. Validate the extracted data according to the validation rules in the specification 10. Structure the output according to the data_structure in the specification 11. Include proper error handling and logging 12. Use type hints for all functions 13. Add docstrings for all functions 14. Follow PEP 8 style guidelines 15. Use async/await consistently throughout the code 16. Handle rate limiting and retries for HTTP requests 17. Include proper exception handling for network errors 18. Add validation for extracted data 19. Include progress logging 20. Add proper cleanup in case of errors 

        Required imports:
        - asyncio
        - json
        - os
        - argparse
        - logging
        - typing
        - bs4
        - aiohttp
        - pydantic
        - from utils.extract_from_webpage import _fetch_and_clean

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
         
         use following as example for playwright edge cases:
         {sample_of_playwright_usage}
         
         Use following as examples which can help you generate the code required for above GTM utility:
         {sample_utility_code}
        """
        logger.info(f"prompt len:{len(prompt)}")
        self.log_update_callback(f"llm call final cogen :prompt len:{len(prompt)}")
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
            if not k == "python_code":
                logger.info(f"{k} : {v}")
                self.log_update_callback(f"{k} : {v}")
        self.python_code_function_name = code_gen.get("python_code_function_name", "extract_data")

        # Clean any markdown formatting
        code = code.replace("```python", "").replace("```", "").strip()
        self.generated_code = code
        self.log_update_callback("✅ Code generation complete")
        logger.info("✅ Code generation complete")
        logger.info(f"\nGenerated code: entry function is  {self.python_code_function_name}")
        logger.info("=" * 50)
        logger.info(code)
        logger.info("=" * 50)
        # Validate the generated code by attempting to execute it
        try:
            # Create a temporary module
            import tempfile
            import importlib.util

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
                    fix_prompt = f"""
                    Fix the following Python code that failed validation with error: {str(e)}

                    Original code:
                    {code}

                    Requirements:
                    1. The code should extract data from the HTML
                    2. It should handle the error: {str(e)}
                    3. It should return a dictionary with the extracted data
                    4. Use BeautifulSoup for parsing
                    5. Follow all the requirements from the original prompt
                    6. The main function MUST be named '{self.python_code_function_name}'

                    CRITICAL REQUIREMENTS TO PREVENT COMMON ISSUES:
                    8. Proper CLI argument handling:
                        - Use argparse.ArgumentParser() correctly
                        - Define all expected arguments with proper types
                        - Handle the case when no arguments are provided
                        - Use parser.parse_args() to parse arguments
                        - Add proper help text for all arguments
                    9. Avoid deprecated packages:
                        - DO NOT use pkg_resources (use importlib.metadata instead)
                        - DO NOT use any deprecated imports or functions
                        - Use modern Python 3.8+ syntax
                    10. Proper script structure:
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
                        code = fixed_code
                        logger.info(f"🔄 Generated fixed code")
                    except Exception as fix_error:
                        logger.error(f"❌ Failed to generate fixed code: {str(fix_error)}")
                finally:
                    # Clean up
                    os.unlink(f.name)

        except Exception as e:
            logger.error(f"❌ Error during code validation: {str(e)}")
            raise Exception(e)

        self.generated_code = code
        self.log_update_callback("✅ Code generation complete")
        logger.info("✅ Code generation complete")
        logger.info("\nGenerated code preview:")
        logger.info("=" * 50)
        logger.info(code[:500] + "..." if len(code) > 500 else code)
        logger.info("=" * 50)
        return code

    async def execute_generated_code(self, url: str) -> Dict:
        """Execute the generated code for a specific URL."""
        logger.info(f"\n▶️ Executing generated code for URL: {url}")
        if not self.generated_code:
            raise ValueError("No code generated yet")

        max_attempts = 2
        current_attempt = 0
        last_error = None
        current_code = self.generated_code

        while current_attempt < max_attempts:
            try:
                current_attempt += 1
                logger.info(f"\n🔄 Attempt {current_attempt}/{max_attempts} to execute code")
                self.log_update_callback(f"\n🔄 Attempt {current_attempt}/{max_attempts} to execute code")

                # Create a temporary module
                import tempfile
                import importlib.util

                with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
                    try:
                        f.write(current_code.encode())
                        f.flush()
                        script_path = f.name

                        out_path = common.make_temp_csv_filename("codegen_barbarika_webparsing")
                        # Execute the function using subprocess
                        env = os.environ.copy()
                        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                        env["PYTHONPATH"] = env.get("PYTHONPATH", "") + ":" + root_dir

                        cmd = ["python", script_path, out_path]
                        proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
                        status = "SUCCESS" if proc.returncode == 0 else "FAIL"
                        output = (
                            proc.stdout
                            if proc.returncode == 0
                            else (proc.stderr or "Error running command")
                        )
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
                            last_error = f"Subprocess failed with return code {proc.returncode}.\nStdout:\n{proc.stdout}\nStderr:\n{proc.stderr}"
                            logger.error(f"❌ Error in attempt {current_attempt}: {last_error}")
                            self.log_update_callback(f"❌ Error in attempt {current_attempt}: {last_error}")
                            if current_attempt < max_attempts:
                                fix_prompt = f"""
                                Fix the following Python code that failed to execute with error: {last_error}

                                Original code:
                                {current_code}

                                Subprocess stdout:
                                {proc.stdout}

                                Subprocess stderr:
                                {proc.stderr}

                                Requirements:
                                1. The code should extract data from the HTML
                                2. It should handle the error: {last_error}
                                3. It should return a dictionary with the extracted data
                                4. Use BeautifulSoup for parsing
                                5. Previous attempts: {current_attempt}/{max_attempts}
                                6. The main function MUST be named '{self.python_code_function_name}'
                                7. Include proper error handling and logging
                                8. Use type hints for all functions
                                9. Add docstrings for all functions
                                10. Follow PEP 8 style guidelines
                                11. Handle rate limiting and retries
                                12. Include proper exception handling
                                13. DO NOT hallucinate data - only extract what exists in the HTML
                                14. Add validation steps for extracted data
                                15. Add logging for any assumptions made

                                CRITICAL: Do NOT use asyncio.run() or any event loop management in the generated code. The main function will be called as a script or awaited by the caller.

                                Return only the fixed Python code without any explanations.
                                IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
                                """
                                try:
                                    fixed_code = call_openai_sync(
                                        prompt=fix_prompt,
                                        model="gpt-4o-mini",  # Use a different model for fixing
                                        response_format={"type": "text"},
                                        client=openai_client
                                    )
                                    current_code = fixed_code
                                    logger.info(f"🔄 Generated fixed code for attempt {current_attempt + 1}")
                                    self.log_update_callback(f"🔄 Generated fixed code for attempt {current_attempt + 1}")
                                    continue  # Retry with fixed code
                                except Exception as fix_error:
                                    logger.error(f"❌ Failed to generate fixed code: {str(fix_error)}")
                                    break  # Exit if we can't even generate fixed code
                            else:
                                self.log_update_callback(f"❌ Max attempts ({max_attempts}) reached. Could not fix the code.")
                                logger.error(f"❌ Max attempts ({max_attempts}) reached. Could not fix the code.")
                                break

                        # If we have extracted data, return it
                        if extracted_data:
                            self.log_update_callback("✅ Code execution successful with extracted data")
                            logger.info("✅ Code execution successful with extracted data")
                            logger.info(f"📊 Extracted {len(extracted_data)} items")
                            return {
                                "extracted_data": extracted_data,
                                "csv_file": out_path,
                                "total_items": len(extracted_data),
                                "execution_success": proc.returncode == 0,
                                "subprocess_status": status,
                                "subprocess_output": output
                            }
                        else:
                            # No data extracted, return subprocess output for debugging
                            logger.info("⚠️ No data extracted")
                            return {
                                "extracted_data": [],
                                "csv_file": out_path,
                                "total_items": 0,
                                "execution_success": proc.returncode == 0,
                                "subprocess_status": status,
                                "subprocess_output": output,
                                "message": "No data found to extract or CSV could not be read"
                            }
                    except Exception as e:
                        last_error = str(e)
                        logger.error(f"❌ Error in attempt {current_attempt}: {last_error}")
                        # No code-fix logic here; only handle in proc.returncode != 0
                    finally:
                        # Clean up temporary files
                        try:
                            os.unlink(f.name)
                        except:
                            pass

            except Exception as e:
                last_error = str(e)
                logger.error(f"❌ Error during execution: {last_error}")
                if current_attempt >= max_attempts:
                    return {}

        # If we get here, all attempts failed
        error_msg = f"Failed after {current_attempt} attempts. Last error: {last_error}"
        logger.error(f"❌ {error_msg}")
        return {
            "extracted_data": [],
            "total_items": 0,
            "execution_success": False,
            "error": error_msg
        }


def web_parse_to_json(
        url: str,
        data_to_extract: Optional[List[str]] = None,
        max_depth: int = 3,
        pagination: bool = False,
        additional_instructions: str = "",
        output_file: str = "output.json"
) -> None:
    """Parse a website and save the extracted data to a JSON file."""

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
        if requirement.extraction_spec and requirement.extraction_spec["output_format"]["type"] == "csv":
            csv_file = output_file.replace(".json", ".csv")
            import pandas as pd
            df = pd.DataFrame(result)
            df.to_csv(csv_file, index=False)
            logger.info(f"✅ Results saved to CSV: {csv_file}")

        # Save results to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

        logger.info("Successfully parsed website and saved results to %s", output_file)
        return result
    except Exception as e:
        logger.error("Error parsing website: %s", str(e))
        raise e


def web_parse_to_json_from_csv(input_file: str, output_file: str) -> None:
    """Run web parsing from a CSV and aggregate results.

    The input_file must contain these columns:
    - url: Target URL to parse
    - data_to_extract: Comma-separated list of fields to extract (optional)
    - max_depth: Maximum crawl depth (optional)
    - pagination: Whether to enable pagination (optional)
    - additional_instructions: Custom extraction instructions (optional)
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
            logger.error("Error processing URL %s: %s", url, str(e))
            continue

    # Save aggregated results
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(aggregated_results, f, indent=2)

    logger.info("Wrote %d results to %s", len(aggregated_results), output_file)


def main() -> None:
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
