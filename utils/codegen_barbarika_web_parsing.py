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
        self.plan: dict = dict()

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
        print(f"🔗 Required pages: {len(plan_data['required_pages'])}")
        return plan_data

    async def html_to_json(self, html: str) -> Dict:
        """Convert HTML to JSON structure using LLM."""
        print("\n🔄 Converting HTML to JSON structure...")

        prompt = f"""
        this HTML content and convert it to a structured JSON format. make sure your are not missing any links.

        HTML Content:
        {html}
        
        Return a JSON object:
        
        \n\nIMPORTANT: Your response MUST be valid JSON. Ensure all strings are properly quoted and brackets are balanced.
        """

        try:
            json_data = call_openai_sync(
                prompt=prompt,
                model="gpt-4.1",
                response_format={"type": "json_object"}
            )
            return json.loads(json_data)
        except Exception as e:
            print(f"❌ Error converting HTML to JSON: {str(e)}")
            # raise Exception(e)
            json_data = call_openai_sync(
                prompt=prompt,
                model="o4-mini",
                response_format={"type": "json_object"}
            )
            return json.loads(json_data)

    async def analyze_page_structure(self, page_data: PageData) -> Dict:
        """Analyze page structure and identify patterns."""
        print(f"\n🔍 Analyzing page structure: {page_data.url}")

        prompt = f"""
        Analyze this structured JSON data of a webpage and identify:
        1. Main content areas
        2. Navigation elements
        3. Data patterns
        4. Potential next pages to visit
        
        Required Data: {self.requirement.data_to_extract}
        
        Additional Instructions: {self.requirement.additional_instructions}
        plan : {self.plan}
        Page Data:
        {json.dumps(page_data.json_data, indent=2)}
        
        Return a JSON object with your analysis. Include:
        - Content areas found
        - Navigation elements
        - patterns_identified
        - next_pages_to_visit (as a list of objects with url, label, page_type, identifier, generic_name  and relevance_score) 
        - Page type
        - Relevance score
        - available fields list for parsing from this page
        - generic_name_of_page 
        - python_code
        
        For next pages to visit:
        1. Provide one url for each page_type, other url have same html structure so they can call sam  html parsing function.
        2. Provide only full url and make sure they real url 
        3. Don't provide placeholder urls
        IMPORTANT: If you're not 100% certain a URL is real and exists in the data, DO NOT include it.
        
        For python code:
        1. to get above html use this code:  from utils.extract_from_webpage import _fetch_and_clean
    html_code = await _fetch_and_clean(url)
        2. write a python code to extract all information in a structure data   
        3. here is sample html_code: {page_data.html} 
        {'4. here is existing python code from previous parent page is' + page_data.parent.page_type +". you need implement further  multi page extration and aggragate. " if page_data.parent else ''}
            {page_data.parent.analysis_data['python_code'] if page_data.parent else ''}

"""

        analysis = call_openai_sync(
            prompt=prompt,
            response_format={"type": "json_object"}
        )
        analysis_data = json.loads(analysis)
        print(f"✅ Page analysis complete")
        print(f"📄 Page type: {analysis_data.get('page_type', 'unknown')}")
        print(f"🎯 Relevance score: {analysis_data.get('relevance_score', 0)}")
        print(f"next_pages_to_visit: {analysis_data.get('next_pages_to_visit', [])}")

        page_data.exclusive_fields = list(set(analysis_data.get('available_fields', [])) - set(self.plan["already_extracted_fields"]))
        self.plan["already_extracted_fields"] = list(
            set(self.plan["already_extracted_fields"]).union(set(analysis_data.get('available_fields', []))))
        self.plan['to_be_extracted_fields'] = list(
            set(self.plan['to_be_extracted_fields']) - set(self.plan["already_extracted_fields"]))

        # Process next pages to visit
        next_pages_to_visit = analysis_data.get('next_pages_to_visit', [])
        if isinstance(next_pages_to_visit, list):
            # Ensure each next page has the required structure
            processed_pages = []
            for page in next_pages_to_visit:
                if isinstance(page, dict) and 'url' in page:
                    if page['url'] not in self.visited_urls:
                        if page["page_type"] not in self.visited_page_types:
                            if page['relevance_score'] > 0.9:
                                processed_page = {
                                    'url': page['url'],
                                    'label': page.get('label', ''),
                                    'relevance_score': page.get('relevance_score', 0),
                                    'page_type': page.get('page_type', '')
                                }

                                if processed_page['url'].startswith(('http://', 'https://')):
                                    self.visited_urls.add(page['url'])
                                    self.visited_page_types.add(page["page_type"])
                                    processed_pages.append(processed_page)

            # Sort by relevance score
            # processed_pages.sort(key=lambda x: x['relevance_score'], reverse=True)
            analysis_data['next_pages_to_visit'] = processed_pages

            print(f"🔗 Found {len(processed_pages)} valid next pages to visit")
            for page in processed_pages[:5]:  # Show top 5 pages
                print(f"  - {page['label']} ({page['relevance_score']}): {page['url']}")

        return analysis_data

    async def fetch_and_process_page(self, url: str, path: List[str] = None) -> PageData:
        """Fetch and process a page."""
        print(f"\n📥 Fetching page: {url}")
        if path is None:
            path = [url]

        # if url in self.visited_urls:
        #     print(f"⏭️ Page already visited: {url}")
        #     return self.page_tree[url]

        # self.visited_urls.add(url)

        # Fetch HTML
        html = await _fetch_and_clean(url)
        print(f"📄 Fetched HTML content ({len(html)} bytes)")

        # Convert HTML to JSON structure
        json_data = await self.html_to_json(html)
        print(f"🔄 Converted HTML to JSON structure")

        # Create page data
        page_data = PageData(
            url=url,
            html=html,
            json_data=json_data,
            path=path,
            children=[]
        )

        # Store in tree
        self.page_tree[url] = page_data

        return page_data

    async def build_page_tree(self):
        """Build tree of pages starting from root."""
        print("\n🌳 Building page tree...")
        # First analyze the requirement
        plan = await self.analyze_requirement()
        self.plan = plan

        root_page = await self.fetch_and_process_page(self.root_url)
        self.visited_urls.add(self.root_url)

        async def process_page(page: PageData, depth: int):
            if depth >= self.requirement.max_depth:
                print(f"⏹️ Reached max depth {depth}, stopping...")
                return

            print(f"\n📑 Processing page at depth {depth}: {page.url}")
            # Analyze page structure
            analysis = await self.analyze_page_structure(page)
            page.analysis_data = analysis
            page.page_type = analysis["page_type"]

            # Process next pages to visit
            next_pages_to_visit = analysis.get('next_pages_to_visit', [])
            if isinstance(next_pages_to_visit, list):
                print(f"🔗 Found {len(next_pages_to_visit)} valid next pages to visit")
                for next_page in next_pages_to_visit:
                    # if next_page['url'] not in self.visited_urls:
                    #     if next_page["page_type"] not in self.visited_page_types:
                    # self.visited_page_types.add(next_page["page_type"])
                    # self.visited_urls.add(next_page['url'])
                    print(f"📥 Processing next page: {next_page['label']} ({next_page['relevance_score']})")
                    child_page = await self.fetch_and_process_page(
                        next_page['url'],
                        path=page.path + [next_page['url']]
                    )
                    page.children.append(child_page)
                    child_page.parent = page
                    await process_page(child_page, depth + 1)

        await process_page(root_page, 0)
        print("\n✅ Page tree building complete")
        print(f"📊 Total pages processed: {len(self.page_tree)}")

    async def generate_extraction_code(self) -> str:
        """Generate Python code for data extraction."""
        print("\n💻 Generating extraction code...")
        prompt = f"""
        Here is python code for multi_pages pages you need to combined the code to achieve uer requirment 
        {json.dumps({url: dict(python_code=data.analysis_data['python_code'] if data.analysis_data else None , 
                               next_pages=[
                                   dict(page_type=chi.page_type,
                                        page_name=chi.analysis_data['generic_name_of_page'] if chi.analysis_data else None,
                                        available_fields_list_for_parsing=chi.analysis_data.get('available_fields_list_for_parsing',
                                                                                                chi.analysis_data.get('available_fields_list',None))) for chi in  data.children if chi.analysis_data]) for url, data in self.page_tree.items()}, indent=2)}
        
        Python coding instructions:
        1. Extract these specific fields: {self.requirement.data_to_extract}
        2. Use BeautifulSoup for parsing
        3. Handle all page types in the tree
        5. This Python script is for {self.root_url} you should make it as hardcoded or default value,
        6. make you implemented main function and this script is executable in cli
        7. to get  html_code for any url use this code:  from utils.extract_from_webpage import _fetch_and_clean
    html_code = await _fetch_and_clean(url)
        
        
        IMPORTANT: Return ONLY the Python code without any markdown formatting or ```python tags.
        The code should start with imports and end with the extraction function.
        
        """

        code = await call_openai_async(
            prompt=prompt,
            response_format={"type": "text"}
        )

        # Clean any markdown formatting
        code = code.replace("```python", "").replace("```", "").strip()

        # Add necessary imports if not present
        if "from bs4 import BeautifulSoup" not in code:
            code = "from bs4 import BeautifulSoup\nimport json\nimport asyncio\n\n" + code

        # Ensure the code has an async extract_data function
        if "async def extract_data" not in code:
            code += "\n\nasync def extract_data(url: str) -> dict:\n    # Implement extraction logic here\n    return {}"

        self.generated_code = code
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

                # Import the module
                spec = importlib.util.spec_from_file_location("extractor", f.name)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Execute the code
                result = await module.extract_data(url)

                print("✅ Code execution complete")
                return result
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
            "lead bio"
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
