import requests
import json
from urllib.parse import urljoin
import sys

def extract_api_urls(base_url):
    """
    Extract all endpoint URLs from an OpenAPI/Swagger documentation.
    
    Args:
        base_url (str): The base URL of the API (e.g., https://elysium-api-tg.onrender.com)
        
    Returns:
        list: A list of complete API URLs
    """
    # Normalize the base URL
    if base_url.endswith('/docs#/'):
        base_url = base_url[:-7]  # Remove '/docs#/' from the end
    if not base_url.endswith('/'):
        base_url += '/'
        
    # Try to fetch the OpenAPI JSON schema
    try:
        # OpenAPI JSON is typically available at /openapi.json
        openapi_url = urljoin(base_url, 'openapi.json')
        response = requests.get(openapi_url)
        response.raise_for_status()
        api_schema = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching OpenAPI schema: {e}")
        # Try alternative URL
        try:
            openapi_url = urljoin(base_url, 'swagger.json')
            response = requests.get(openapi_url)
            response.raise_for_status()
            api_schema = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Swagger schema: {e}")
            return []
    
    # Extract paths and methods
    paths = api_schema.get('paths', {})
    
    # Store all URLs
    all_urls = []
    
    # Process each path and HTTP method
    for path, methods in paths.items():
        for method in methods:
            if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                endpoint_info = methods[method]
                full_url = urljoin(base_url, path)
                
                # Get operation ID or summary as the endpoint name
                endpoint_name = endpoint_info.get('operationId', 
                                                  endpoint_info.get('summary', f"{method.upper()} {path}"))
                
                all_urls.append({
                    'name': endpoint_name,
                    'method': method.upper(),
                    'url': full_url,
                    'description': endpoint_info.get('description', '')
                })
    
    return all_urls

def print_urls(urls):
    """Pretty print the URLs"""
    print(f"Found {len(urls)} API endpoints:\n")
    
    for i, endpoint in enumerate(urls, 1):
        print(f"{i}. {endpoint['name']}")
        print(f"   Method: {endpoint['method']}")
        print(f"   URL: {endpoint['url']}")
        if endpoint['description']:
            print(f"   Description: {endpoint['description']}")
        print()

def export_to_file(urls, format='txt'):
    """Export URLs to a file in the specified format"""
    if format.lower() == 'json':
        with open('elysium_api_urls.json', 'w') as f:
            json.dump(urls, f, indent=2)
        return 'elysium_api_urls.json'
    
    elif format.lower() == 'txt':
        with open('elysium_api_urls.txt', 'w') as f:
            for endpoint in urls:
                f.write(f"Name: {endpoint['name']}\n")
                f.write(f"Method: {endpoint['method']}\n")
                f.write(f"URL: {endpoint['url']}\n")
                if endpoint['description']:
                    f.write(f"Description: {endpoint['description']}\n")
                f.write("\n")
        return 'elysium_api_urls.txt'
    
    else:
        print(f"Unsupported format: {format}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "https://elysium-api-tg.onrender.com/docs#/"
    
    print(f"Extracting API URLs from {base_url}...")
    urls = extract_api_urls(base_url)
    
    if urls:
        print_urls(urls)
        
        export_format = input("Export to file? Enter format (json/txt) or press Enter to skip: ").strip()
        if export_format:
            filename = export_to_file(urls, export_format)
            if filename:
                print(f"Exported to {filename}")
    else:
        print("No API endpoints found. This could happen if:")
        print("1. The API doesn't use OpenAPI/Swagger documentation")
        print("2. The documentation is available at a different URL")
        print("3. The server requires authentication to access the documentation")
        
        print("\nAlternative approaches:")
        print("1. Check if there's API documentation available elsewhere")
        print("2. Use a network monitoring tool like Browser DevTools to capture API requests")
        print("3. Examine the frontend code for API call patterns")