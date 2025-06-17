import asyncio
import json
import os
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel
from utils.extract_from_webpage import _fetch_and_clean
from utils.common import call_openai_async, call_openai_sync

dotenv_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path)


class UserRequirement(BaseModel):
    target_url: str
    data_to_extract: List[str]
    max_depth: int = 3
    pagination: bool = False
    additional_instructions: str = ""


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
    def __init__(self, requirement: UserRequirement):
        print(f"\n🚀 Initializing WebParser with URL: {requirement.target_url}")
        print(f"📋 Data to extract: {requirement.data_to_extract}")
        print(f"🔍 Max depth: {requirement.max_depth}")
        print(f"📄 Pagination: {requirement.pagination}")
        print(f"📝 Additional instructions: {requirement.additional_instructions}")

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
        print("\n📊 Analyzing user requirements...")
        prompt = f"""
        Analyze this web scraping requirement and create an extraction plan:
        
        Target URL: {self.requirement.target_url}
        Data to Extract: {self.requirement.data_to_extract}
        Max Depth: {self.requirement.max_depth}
        Pagination: {self.requirement.pagination}
        Additional Instructions: {self.requirement.additional_instructions}
        
        Create a plan in JSON format:
        {{
            "extraction_steps": [],
            "required_pages": [],
            "data_patterns": [],
            "pagination_strategy": "",
            "validation_rules": [],
            "already_extracted_fields: []
            "to_be_extracted_fields":[]
        }}
        """

        plan = call_openai_sync(
            prompt=prompt,
            response_format={"type": "json_object"}
        )
        plan_data = json.loads(plan)
        print("✅ Requirement analysis complete")
        print(f"📋 Extraction steps: {len(plan_data['extraction_steps'])}")
        # print(f"🔗 Required pages: {len(plan_data['required_pages'])}")
        return plan_data

    async def analyze_page_directly(self, html: str, url: str, parent_page: PageData = None) -> Dict:
        """Analyze HTML directly and return all analysis data in one call."""
        print(f"\n🔍 Analyzing page directly: {url}")

        prompt = f"""
        Analyze this HTML content of a webpage and provide comprehensive analysis in one JSON response:
        
        HTML Content:
        {html}
        
        Required Data to Extract: {self.requirement.data_to_extract}
        Additional Instructions: {self.requirement.additional_instructions}
        Current Plan: {self.plan}
        
        Already Visited Page Types: {self.visited_page_types}
        
        Return a JSON object with the following structure:
        {{
            "structured_data": "Convert the HTML to structured JSON format, ensuring all links are captured",
            "main_content_areas": "List of main content areas found",
            "navigation_elements": "List of navigation elements found", 
            "patterns_identified": "Data patterns identified in the page",
            "next_pages_to_visit": [
                {{
                    "url": "full URL",
                    "label": <page label>,
                    "page_type": <page type>,
                    "identifier": <unique identifier>,
                    "relevance_score": <from 0.0 to 1.0>
                }}
            ],
            "page_type": "page type",
            "relevance_score": <>,
            "available_fields": ["list of fields available for extraction"],
            "generic_name_of_page": <generic name for this page>,
            "python_code": <Python code to extract data from this page>,
            "python_code_function_name": <name of the main extraction function>
        }}
        
        For next_pages_to_visit:
        1. Provide one url for each page_type, other urls have same html structure so they can call same html parsing function
        2. Provide only full URLs that actually exist in the HTML
        3. Don't include already visited URLs or page types
        4. Don't provide placeholder URLs
        
        For python_code:
        1. Use this code to get HTML: from utils.extract_from_webpage import _fetch_and_clean
           html_code = await _fetch_and_clean(url)
        2. Write Python code to extract all required information in structured data
        3. The function should be async and take a url parameter
        4. Use BeautifulSoup for parsing
        {'5. Build upon existing code from parent page: ' + parent_page.page_type if parent_page else ''}
        {'6. Parent page code: ' + parent_page.analysis_data['python_code'] if parent_page and parent_page.analysis_data else ''}
        
        IMPORTANT: Your response MUST be valid JSON. Ensure all strings are properly quoted and brackets are balanced.
        """

        try:
            analysis = call_openai_sync(
                prompt=prompt,
                response_format={"type": "json_object"}
            )
            analysis_data = json.loads(analysis)
        except json.decoder.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            analysis = call_openai_sync(
                prompt=prompt,
                model="gpt-4o-mini",
                response_format={"type": "json_object"}
            )
            analysis_data = json.loads(analysis)

        print(f"✅ Page analysis complete")
        print(f"📄 Page type: {analysis_data.get('page_type', 'unknown')}")
        print(f"🎯 Relevance score: {analysis_data.get('relevance_score', 0)}")
        print(f"🔗 Next pages to visit: {len(analysis_data.get('next_pages_to_visit', []))}")

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
                    print(f"\n🔄 Attempt {current_attempt}/{max_attempts} to execute code for {url}")

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
                            print(f"✅ Code execution successful for {url}")
                            print(f"📊 Result: {json.dumps(result, indent=2)}")
                            if not result:
                                raise Exception("empty result")
                            break  # Success, exit the loop
                        else:
                            raise AttributeError(f"Function '{function_name}' not found in generated code")

                except Exception as e:
                    last_error = str(e)
                    print(f"❌ Error in attempt {current_attempt}: {last_error}")

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
                        4. The function should be named '{function_name}' and be async
                        5. Use BeautifulSoup for parsing
                        6. Previous attempts: {current_attempt}/{max_attempts}
                        7. The function must be named exactly '{function_name}'
                        
                        Return only the fixed Python code without any explanations.
                        IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
                        """

                        try:
                            fixed_code = call_openai_sync(
                                prompt=fix_prompt,
                                model="gpt-4.1",  # Use a different model for fixing
                                response_format={"type": "text"}
                            )
                            generated_code = fixed_code
                            print(f"🔄 Generated fixed code for attempt {current_attempt + 1}")
                        except Exception as fix_error:
                            print(f"❌ Failed to generate fixed code: {str(fix_error)}")
                            break  # Exit if we can't even generate fixed code
                    else:
                        print(f"❌ Max attempts ({max_attempts}) reached. Could not fix the code.")
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
            if (page.get("relevance_score", 0) >= 0.9 and
                    page.get("page_type") not in self.visited_page_types and
                    page.get("url") not in self.visited_urls):
                un_visited_pages.append(page)
                self.visited_page_types.add(page["page_type"])
                self.visited_urls.add(page["url"])

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
            "code_execution_error": code_execution_error
        }

    async def fetch_and_process_page(self, url: str, path: List[str] = None) -> PageData:
        """Fetch and process a page."""
        print(f"\n📥 Fetching page: {url}")
        if path is None:
            path = [url]

        # Fetch HTML
        html = await _fetch_and_clean(url)
        print(f"📄 Fetched HTML content ({len(html)} bytes)")

        # Analyze page directly (merged html_to_json + analyze_page_structure)
        analysis = await self.analyze_page_directly(html, url)

        # Ensure proper data types
        structured_data = analysis.get("structured_data", {})
        if not isinstance(structured_data, dict):
            print(f"⚠️ Warning: structured_data is not a dict, converting: {type(structured_data)}")
            structured_data = {"data": structured_data} if structured_data else {}

        code_execution_result = analysis.get("code_execution_result")
        if code_execution_result is not None and not isinstance(code_execution_result, dict):
            print(f"⚠️ Warning: code_execution_result is not a dict, converting: {type(code_execution_result)}")
            code_execution_result = {"result": code_execution_result} if code_execution_result else None

        code_execution_error = analysis.get("code_execution_error")
        if code_execution_error is not None and not isinstance(code_execution_error, str):
            print(f"⚠️ Warning: code_execution_error is not a string, converting: {type(code_execution_error)}")
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
        if page_data.relevance_score >= 0.9:
            self.page_tree[url] = page_data

        return page_data

    async def build_page_tree(self):
        """Build tree of pages starting from root."""
        print("\n🌳 Building page tree...")
        # First analyze the requirement
        plan = await self.analyze_requirement()
        self.plan = plan

        root_page = await self.fetch_and_process_page(self.root_url)
        self.tree_root = root_page
        self.visited_urls.add(self.root_url)

        async def process_page(page: PageData, depth: int):
            if depth >= self.requirement.max_depth:
                print(f"⏹️ Reached max depth {depth}, stopping...")
                return

            print(f"\n📑 Processing page at depth {depth}: {page.url}: score: {page.relevance_score}")
            # Analysis is already done in fetch_and_process_page, just use the existing data
            analysis = page.analysis_data
            page.page_type = analysis["page_type"]

            # Process next pages to visit
            next_pages_to_visit = analysis.get('next_pages_to_visit', [])
            if isinstance(next_pages_to_visit, list):
                print(f"🔗 Found {len(next_pages_to_visit)} valid next pages to visit")
                for next_page in next_pages_to_visit:
                    print(f"📥 Processing next page: {next_page['label']} ({next_page['relevance_score']})")
                    child_page = await self.fetch_and_process_page(
                        next_page['url'],
                        path=page.path + [next_page['url']]
                    )
                    if child_page.relevance_score >= 0.9:
                        page.children.append(child_page)
                        child_page.parent = page
                        await process_page(child_page, depth + 1)

        await process_page(root_page, 0)
        print("\n✅ Page tree building complete")
        print(f"📊 Total pages processed: {len(self.page_tree)}")

    async def generate_extraction_code(self) -> str:
        """Generate Python code for data extraction."""
        print("\n💻 Generating extraction code...")

        # Collect all working code and their results
        working_codes = []
        for url, data in self.page_tree.items():
            if data.generated_code and data.code_execution_result and not data.code_execution_error:
                working_codes.append({
                    'url': url,
                    'code': data.generated_code,
                    'result': data.code_execution_result,
                    'page_type': data.page_type,
                    "children": [child.page_type for child in data.children],
                    'parent': data.parent.page_type if data.parent else None,
                    'page_name': data.analysis_data.get('generic_name_of_page') if data.analysis_data else None
                })

        prompt = f"""
        Here is python code for multi_pages pages you need to combined the code to achieve user requirement.
        {json.dumps(working_codes, indent=2)}
        
        Here is user requirement: {self.requirement.additional_instructions}
        
        Python coding instructions:
        1. Extract these data: {self.requirement.data_to_extract}
        2. Use BeautifulSoup for parsing
        3. This Python script main function start with  {self.root_url} 
        4. make sure main function should start with {self.page_tree[self.root_url].page_type} {self.page_tree[self.root_url]}. i mean script start with {self.root_url}
        5. make sure script is executable in cli
        6. to get html_code for any url use this code: from utils.extract_from_webpage import _fetch_and_clean
           html_code = await _fetch_and_clean(url)
        7.make sure there are no demo code, make production ready code
        
        IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
        Return a JSON object with the following structure:
            {{
                "python_code_function_name": <name of the main extraction function>,
                "python_code": <python_code>
            }}
        """

        code_gen = await call_openai_async(
            prompt=prompt,
            response_format={"type": "json_object"}
        )
        code_gen = json.loads(code_gen)
        code = code_gen["python_code"]
        # Clean any markdown formatting
        code = code.replace("```python", "").replace("```", "").strip()

        # Add necessary imports if not present
        if "from bs4 import BeautifulSoup" not in code:
            code = "from bs4 import BeautifulSoup\nimport json\nimport asyncio\n\n" + code

        # Ensure the code has an async extract_data function
        if "async def extract_data" not in code:
            code += "\n\nasync def extract_data(url: str) -> dict:\n    # Implement extraction logic here\n    return {}"

        self.generated_code = code
        self.python_code_function_name = code_gen['python_code_function_name']
        print("✅ Code generation complete")
        print("\nGenerated code preview:")
        print("=" * 50)
        print(code[:500] + "..." if len(code) > 500 else code)
        print("=" * 50)
        return code

    async def execute_generated_code(self, url: str) -> Dict:
        """Execute the generated code for a specific URL."""
        print(f"\n▶️ Executing generated code for URL: {url}")
        if not self.generated_code:
            raise ValueError("No code generated yet")

        # Create a temporary module
        import tempfile
        import importlib.util

        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            try:
                f.write(self.generated_code.encode())
                f.flush()

                spec = importlib.util.spec_from_file_location("page_extractor", f.name)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Execute the code using the specified function name
                if hasattr(module, self.python_code_function_name):
                    result = await getattr(module, self.python_code_function_name)()
                    print("✅ Code execution complete")
                    if not result:
                        raise Exception("empty result")
                    return result

                else:
                    raise AttributeError(f"Function '{self.python_code_function_name}' not found in generated code")
            except Exception as e:
                print(f"❌ Error executing code: {str(e)}")
                print("\nGenerated code that caused the error:")
                print("=" * 50)
                print(self.generated_code)
                print("=" * 50)
                raise
            finally:
                # Clean up
                os.unlink(f.name)


async def main():
    # Example usage with user requirements
    requirement = UserRequirement(
        target_url="https://producthunt.com/",
        data_to_extract=[
            "lead first name",
            "lead last_name",
            "lead job title",
            "lead head line",
            "lead bio",
            "lead email",
            "lead phone",
            "lead linkedin_url",
            "lead link_to_more_information",
            "organization_name",
            "organization_website",
            "primary_domain_of_organization",
            "link_to_more_information",
            "organization_linkedin_url",

        ],
        max_depth=3,
        pagination=True,
        additional_instructions="visit app details page, app makers/team page and profile page, shortlist only founders "
    )

    parser = WebParser(requirement)

    # Build page tree
    await parser.build_page_tree()

    # Generate extraction code
    code = await parser.generate_extraction_code()

    # Execute for specific URL
    result = await parser.execute_generated_code(requirement.target_url)

    print("\n📊 Final Results:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
